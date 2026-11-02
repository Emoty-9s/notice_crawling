"""User-saved HTML regressions. No captured RIPC AJAX/page-2/HAR is supplied.

Derived JSON and changed pageIndex responses below are explicitly mock data,
not evidence of a successful live request or a captured second page.
"""

import json
import re
import socket
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from src.core.models import Notice
from src.core.normalizer import generate_notice_id
from src.core.storage import JsonStorage
from src.local_client.dashboard import load_dashboard, notice_rows, recommendation_rows
from src.local_client.performance import Performance, PerformanceStore
from src.local_client.sync import FeedClient
from src.pipeline import run_pipeline
from src.scrapers._board import NoticeLink
from src.scrapers._html import StructureError, parse_html
from src.scrapers._portal import metadata
from src.scrapers.kista_ippro import KistaScraper
from src.scrapers.ripc_pms import RipcScraper
from tools.m16_smoke import probe


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/m16_live'
CONFIGS = json.loads((ROOT / 'config/sites.yaml').read_text(encoding='utf-8'))['sites']
CLOCK = datetime(2026, 11, 2, tzinfo=timezone.utc)


def html(site, name):
    return (FIXTURES / site / f'{site}_{name}.html').read_text(encoding='utf-8')


def config(source):
    return {**deepcopy(next(c for c in CONFIGS if c['source_id'] == source)),
            'enabled': True, 'max_pages': 1, 'http': {'max_retries': 0}}


def ripc_detail_link(scraper):
    """Bootstrap only from real detail hidden identity and metadata, not a list."""
    root = parse_html(html('ripc', 'detail_1'))
    form = root.one('form', id='frmParams')
    identity = {key: form.one('input', attr={'name': key}).attrs['value'] for key in ('bizYear', 'noticeSeq')}
    url = scraper.build_detail_url(scraper.detail_path + '?bizYear=' + identity['bizYear'] + '&noticeSeq=' + identity['noticeSeq'])
    return NoticeLink(url, metadata(root, '공고명').text(), url)


def derived_ripc_json(scraper):
    """Synthetic AJAX response from real detail values + actual JS field names."""
    item = ripc_detail_link(scraper)
    root = parse_html(html('ripc', 'detail_1'))
    fields = parse_qs(urlsplit(item.url).query)
    return {'result': {'currentPageNo': 1, 'recordCountPerPage': 10, 'totalRecordCount': 1,
                       'noticeList': [{'bizYear': fields['bizYear'][0], 'noticeSeq': fields['noticeSeq'][0],
                                       'noticeTitle': item.title, 'centerName': metadata(root, '수요기관').text(),
                                       'bizCategory1Name': metadata(root, '단위사업').text(),
                                       'startDateStr': '2026-03-19 18:20', 'endDateStr': '2026-04-02 11:00',
                                       'noticeCode': 'NST003'}]}}


def kista_one_row():
    """Subset of the actual 20-row DOM for the single available detail file."""
    listing = html('kista', 'list_page1')
    def subset(match):
        rows = re.findall(r'<tr>.*?</tr>', match[2], flags=re.S)
        chosen = [row for row in rows if "javascript:view('2026','76');" in row]
        if len(chosen) != 1:
            raise AssertionError('expected one real detail row')
        return match[1] + chosen[0] + match[3]
    return re.sub(r'(<tbody>)(.*?)(</tbody>)', subset, listing, flags=re.S)


class LiveFixtureTests(unittest.TestCase):
    def setUp(self):
        guard = patch('src.scrapers.base.urlopen', side_effect=AssertionError('network forbidden'))
        self.network = guard.start()
        self.addCleanup(guard.stop)
        self.ripc = RipcScraper(config('ripc_pms'), transport=Mock(), clock=lambda: CLOCK, logger=Mock())
        self.kista = KistaScraper(config('kista_ippro'), transport=Mock(), clock=lambda: CLOCK, logger=Mock())

    def test_saved_ripc_list_is_ajax_shell_not_a_notice_or_empty_success(self):
        listing = html('ripc', 'list_page1')
        table = self.ripc._table(parse_html(listing))
        self.assertEqual(len(table.find('th')), 7)
        self.assertEqual(table.find('td'), [])
        with self.assertRaisesRegex(StructureError, 'UNVERIFIED_DYNAMIC_LIST'):
            self.ripc.parse_list(listing)

    def test_ripc_observed_post_endpoint_fields_defaults_and_page(self):
        endpoint, data = self.ripc.ajax_request(html('ripc', 'list_page1'), 2)
        self.assertEqual(endpoint, 'https://pms.ripc.org/pms/biz/partner/tenderNotice/getNoticeList.do')
        self.assertEqual(data, {'searchKeyword': '', 'bizYear': '2026', 'recordCountPerPage': '10',
                                'currentPageNo': '2', 'noticeGroupCode': 'NGR002', 'noticeCode': 'NST000'})

    def test_ripc_changed_script_or_endpoint_fails_before_post(self):
        for old, new in [('getNoticeList.do', 'unverified.do'), ('NGR002', 'unknown'), ('"POST"', '"GET"')]:
            with self.subTest(old=old), self.assertRaises(StructureError):
                self.ripc.ajax_request(html('ripc', 'list_page1').replace(old, new))
        self.ripc.transport.post.assert_not_called()

    def test_ripc_year_uses_supplied_clock_or_explicit_configuration(self):
        first = self.ripc.ajax_request(html('ripc', 'list_page1'))
        other = RipcScraper({**config('ripc_pms'), 'business_year': 2025}, clock=lambda: CLOCK)
        self.assertEqual(first[1]['bizYear'], '2026')
        self.assertEqual(other.ajax_request(html('ripc', 'list_page1'))[1]['bizYear'], '2025')

    def test_ripc_actual_detail_hidden_identity_body_dates_and_notice(self):
        item = ripc_detail_link(self.ripc)
        notice = self.ripc.normalize(self.ripc.parse_detail(html('ripc', 'detail_1'), item))
        self.assertIn('noticeSeq=553', notice.url)
        self.assertIn('bizYear=2026', notice.url)
        self.assertEqual((notice.apply_start, notice.apply_end), ('2026-03-19', '2026-04-02'))
        self.assertEqual(notice.institution, '경기 센터')
        self.assertEqual(notice.category, '소상공인 IP창출 지원')
        self.assertIn('변리업체', notice.content_text)
        self.assertIn('용역 입찰 공고', notice.content_text)
        self.assertNotIn('COPYRIGHT', notice.content_text)
        self.assertNotIn('도움말', notice.content_text)
        self.assertEqual(Notice.from_json(notice.to_json()), notice)
        self.assertEqual(notice.notice_id, generate_notice_id(source_id='ripc_pms', title=notice.title, url=notice.url))

    def test_ripc_detail_rejects_wrong_sequence(self):
        item = ripc_detail_link(self.ripc)
        wrong = html('ripc', 'detail_1').replace('name="noticeSeq" value="553"', 'name="noticeSeq" value="999"')
        with self.assertRaisesRegex(StructureError, 'IDENTITY_MISMATCH'):
            self.ripc.parse_detail(wrong, item)

    def test_ripc_actual_two_attachments_and_session_removal(self):
        detail = html('ripc', 'detail_1')
        expected = tuple(f'https://pms.ripc.org/kms/tenderNotice/attachFileDown.do?attachSeq={value}' for value in (1722, 1723))
        self.assertEqual(self.ripc.parse_attachments(detail), expected)
        self.assertEqual(self.ripc.parse_attachments(detail.replace('attachFileDown.do?', 'attachFileDown.do;jsessionid=TEST_ONLY?')), expected)
        self.ripc.transport.get.assert_not_called()

    def test_ripc_derived_json_matches_detail_but_is_not_a_captured_response(self):
        response = json.dumps(derived_ripc_json(self.ripc), ensure_ascii=False)
        items = self.ripc.parse_list(response)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, ripc_detail_link(self.ripc).url)
        one = self.ripc.normalize(self.ripc.parse_detail(html('ripc', 'detail_1'), items[0]))
        self.assertEqual(one, self.ripc.normalize(self.ripc.parse_detail(html('ripc', 'detail_1'), items[0])))

    def test_ripc_derived_json_nullable_dates_and_draft_exclusion(self):
        data = derived_ripc_json(self.ripc)
        row = data['result']['noticeList'][0]
        row.update(startDateStr=None, endDateStr=None, centerName=None, bizCategory1Name=None)
        item = self.ripc.parse_list(json.dumps(data))[0]
        self.assertIsNone(item.apply_start)
        self.assertIsNone(item.category)
        row.update(centerName='-', bizCategory1Name='-')
        item = self.ripc.parse_list(json.dumps(data))[0]
        self.assertIsNone(item.category)
        self.assertIsNone(item.institution)
        row['noticeCode'] = 'NST002'
        self.assertEqual(self.ripc.parse_list(json.dumps(data)), [])

    def test_ripc_derived_json_invalid_rows_and_duplicate_keys_fail(self):
        for text in ('{bad', '{"result":{}}', '{"result":{},"result":{}}'):
            with self.subTest(text=text), self.assertRaises(StructureError):
                self.ripc.parse_list(text)
        data = derived_ripc_json(self.ripc)
        data['result']['noticeList'][0]['noticeSeq'] = 'not-an-id'
        with self.assertRaises(StructureError):
            self.ripc.parse_list(json.dumps(data))

    def test_ripc_two_mock_json_pages_follow_observed_post_parameters(self):
        self.ripc.max_pages = 3
        first = derived_ripc_json(self.ripc)
        first['result']['totalRecordCount'] = 11
        second = deepcopy(first)
        second['result']['currentPageNo'] = 2
        second['result']['noticeList'][0]['noticeSeq'] = '554'
        self.ripc.transport.get.side_effect = ['User-agent: *\nAllow: /', html('ripc', 'list_page1')]
        self.ripc.transport.post.side_effect = [json.dumps(first), json.dumps(second)]
        pages = self.ripc.fetch_list()
        self.assertEqual(len(self.ripc.parse_list(pages)), 2)
        self.assertEqual([c.kwargs['data']['currentPageNo'] for c in self.ripc.transport.post.call_args_list], ['1', '2'])

    def test_ripc_post_page_mismatch_and_robots_denial_fail(self):
        data = derived_ripc_json(self.ripc)
        data['result']['currentPageNo'] = 2
        self.ripc.transport.get.side_effect = ['User-agent: *\nAllow: /', html('ripc', 'list_page1')]
        self.ripc.transport.post.return_value = json.dumps(data)
        with self.assertRaisesRegex(StructureError, 'PAGE_RESPONSE_MISMATCH'):
            self.ripc.fetch_list()
        self.ripc.transport.post.reset_mock()
        self.ripc.transport.get.side_effect = ['User-agent: *\nDisallow: /pms/biz/partner/tenderNotice/getNoticeList.do', html('ripc', 'list_page1')]
        with self.assertRaisesRegex(StructureError, 'ROBOTS_DISALLOWED'):
            self.ripc.fetch_list()
        self.ripc.transport.post.assert_not_called()

    def test_kista_actual_twenty_rows_js_identity_and_dates(self):
        items = self.kista.parse_list(html('kista', 'list_page1'))
        self.assertEqual(len(items), 20)
        self.assertEqual(items[0].title, '2026년 IP-R&D 전략지원 사업 협력기관 풀(POOL) 상시 모집 공고')
        self.assertEqual((items[0].apply_start, items[0].apply_end), ('2026-01-12', '2026-12-31'))
        self.assertEqual(items[0].category, '협력기관 풀(POOL)')
        self.assertEqual(items[0].url, 'https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceView.do?annYy=2026&annId=3&bbsType=ac')
        self.assertNotIn('접수중', items[0].title)

    def test_kista_actual_detail_matches_76_and_image_only_body(self):
        items = self.kista.parse_list(html('kista', 'list_page1'))
        item = next(item for item in items if 'annId=76&' in item.url)
        notice = self.kista.normalize(self.kista.parse_detail(html('kista', 'detail_1'), item))
        self.assertEqual((notice.apply_start, notice.apply_end), ('2026-09-28', '2026-10-02'))
        self.assertEqual(notice.category, 'R&D전주기 IP솔루션지원 사업')
        self.assertEqual(notice.content_text, '')
        self.assertEqual(Notice.from_json(notice.to_json()), notice)
        with self.assertRaisesRegex(StructureError, 'DETAIL_TITLE_MISMATCH'):
            self.kista.parse_detail(html('kista', 'detail_1'), items[0])

    def test_kista_hidden_body_html_entity_decoding_without_script_execution(self):
        root = parse_html(html('kista', 'detail_1'))
        root.one('input', attr={'name': 'contents'}).attrs['value'] = '<p>한글 &amp; 특허</p><script>forbidden()</script>'
        self.assertEqual(self.kista.detail_content(self.kista.detail_scope(root.html())), '한글 & 특허')

    def test_kista_detail_ignores_nested_project_category_headers(self):
        detail = html('kista', 'detail_1')
        scope = self.kista.detail_scope(detail)
        self.assertEqual(sum(node.text() == '사업구분' for node in scope.find('th')), 2)
        self.assertEqual(metadata(scope, '사업구분').text(), 'R&D전주기 IP솔루션지원 사업')

    def test_kista_actual_dext5_three_file_paths_not_download_handler_claim(self):
        links = self.kista.parse_attachments(html('kista', 'detail_1'))
        self.assertEqual(links, tuple('https://biz.kista.re.kr/iprnd_data/RND-IP2_DATA/AN/FILE_' + value for value in ('000000001295795', '000000001295794', '000000001295793')))
        self.kista.transport.get.assert_not_called()

    def test_kista_changed_dext5_path_is_not_guessed(self):
        with self.assertRaisesRegex(StructureError, 'UNEXPECTED_DEXT5_FILE_PATH'):
            self.kista.parse_attachments(html('kista', 'detail_1').replace('/iprnd_data/RND-IP2_DATA/AN', '/unknown'))

    def test_kista_actual_pager_has_post_indices_2_through_39(self):
        pages = self.kista.pagination_pages(html('kista', 'list_page1'))
        self.assertEqual(pages[:3], [1, 2, 3])
        self.assertEqual(pages[-2:], [21, 39])
        fields = self.kista.list_form(parse_html(html('kista', 'list_page1')))
        self.assertEqual(fields['pageIndex'], '1')
        self.assertEqual(fields['bbsType'], 'ac')
        self.assertEqual(fields['searchWrd'], '')

    def test_kista_mock_page_two_posts_form_not_guessed_get_query(self):
        self.kista.max_pages = 2
        listing = html('kista', 'list_page1')
        # Page-2 response derived from page 1; NOT a real page-2 fixture.
        second = listing.replace('name="pageIndex" type="hidden" value="1"', 'name="pageIndex" type="hidden" value="2"')
        self.kista.transport.get.side_effect = ['User-agent: *\nAllow: /', listing]
        self.kista.transport.post.return_value = second
        pages = self.kista.fetch_list()
        self.assertEqual(len(pages), 2)
        self.assertEqual(self.kista.transport.post.call_count, 1)
        call = self.kista.transport.post.call_args
        self.assertEqual(call.args[0], 'https://biz.kista.re.kr/ippro/com/iprndMain/selectBusinessAnnounceList.do')
        self.assertEqual(call.kwargs['data']['pageIndex'], '2')
        self.assertEqual(len(self.kista.parse_list(pages)), 20)

    def test_kista_repeated_first_page_is_explicit_failure(self):
        self.kista.max_pages = 2
        listing = html('kista', 'list_page1')
        self.kista.transport.get.side_effect = ['User-agent: *\nAllow: /', listing]
        self.kista.transport.post.return_value = listing
        with self.assertRaisesRegex(StructureError, 'PAGE_RESPONSE_MISMATCH'):
            self.kista.fetch_list()

    def test_kista_actual_detail_fetch_uses_posted_identity(self):
        item = self.kista.parse_list(html('kista', 'list_page1'))[2]
        self.kista.transport.post.return_value = html('kista', 'detail_1')
        self.kista.fetch_detail(item)
        call = self.kista.transport.post.call_args
        self.assertEqual(call.kwargs['data']['annId'], '76')
        self.assertEqual(call.kwargs['data']['annYy'], '2026')
        self.assertEqual(call.kwargs['data']['bbsType'], 'ac')
        self.assertNotIn('?', call.args[0])
        self.kista.transport.get.assert_not_called()

    def test_kista_unknown_js_call_changed_script_and_foreign_board_fail(self):
        listing = html('kista', 'list_page1')
        for old, new in [("javascript:view('2026','3');", "javascript:other('2026','3');"),
                         ('selectBusinessAnnounceView.do', 'unverified.do'),
                         ('name="bbsType" value="ac"', 'name="bbsType" value="bs"')]:
            with self.subTest(old=old), self.assertRaises(StructureError):
                self.kista.parse_list(listing.replace(old, new))

    def test_real_fixtures_no_session_tokens_or_contract_page_parameters(self):
        for path in FIXTURES.rglob('*.html'):
            data = path.read_text(encoding='utf-8')
            self.assertNotIn(';jsessionid=', data.lower())
            self.assertNotIn('contractPage', data)

    def test_post_preserves_ua_timeout_and_retries_transient_only(self):
        settings = {**config('ripc_pms'), 'http': {'max_retries': 1, 'timeout_seconds': 3}}
        transport, sleep = Mock(), Mock()
        scraper = RipcScraper(settings, transport=transport, sleep=sleep, logger=Mock())
        transport.post.side_effect = [URLError(socket.gaierror(11001, 'test')), 'ok']
        self.assertEqual(scraper.request_form('https://pms.ripc.org/test', {'a': '한글'}), 'ok')
        self.assertEqual(transport.post.call_count, 2)
        self.assertEqual(transport.post.call_args.kwargs['timeout'], 3)
        self.assertEqual(transport.post.call_args.kwargs['headers']['User-Agent'], scraper.http_settings.user_agent)
        self.assertEqual(transport.post.call_args.kwargs['headers']['Content-Type'], 'application/x-www-form-urlencoded')
        transport.post.reset_mock()
        transport.post.side_effect = HTTPError('https://example.test', 403, 'denied', {}, None)
        with self.assertRaises(HTTPError):
            scraper.request_form('https://pms.ripc.org/test', {})
        self.assertEqual(transport.post.call_count, 1)

    def test_urllib_form_transport_encodes_korean_and_declares_post(self):
        from src.scrapers.base import UrllibTransport
        response = Mock()
        response.headers.get_content_charset.return_value = 'utf-8'
        response.read.return_value = b'ok'
        manager = Mock()
        manager.__enter__ = Mock(return_value=response)
        manager.__exit__ = Mock(return_value=False)
        with patch('src.scrapers.base.urlopen', return_value=manager) as network:
            self.assertEqual(UrllibTransport().post('https://example.test/', data={'q': '한글'}, timeout=3,
                                                  headers={'Content-Type': 'application/x-www-form-urlencoded'}), 'ok')
        request = network.call_args.args[0]
        self.assertEqual(request.method, 'POST')
        self.assertEqual(parse_qs(request.data.decode('ascii')), {'q': ['한글']})

    def test_fixture_probe_creates_one_notice_each_without_real_network(self):
        for source, listing, detail in [('ripc_pms', html('ripc', 'list_page1'), html('ripc', 'detail_1')),
                                         ('kista_ippro', kista_one_row(), html('kista', 'detail_1'))]:
            transport = Mock()
            if source == 'ripc_pms':
                transport.get.side_effect = ['User-agent: *\nAllow: /', listing, detail]
                transport.post.return_value = json.dumps(derived_ripc_json(self.ripc))
            else:
                transport.get.side_effect = ['User-agent: *\nAllow: /', listing]
                transport.post.return_value = detail
            with self.subTest(source=source), patch('src.scrapers.base.UrllibTransport', return_value=transport):
                report = probe(source, config(source))
            self.assertEqual(report['status'], 'SUCCESS')
            self.assertEqual(report['notice_count'], 1)
        self.network.assert_not_called()

    def test_real_details_pipeline_with_derived_ripc_json_and_kista_subset(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests', prefix='m16-live-test-') as folder:
            root = Path(folder)
            settings = [{**deepcopy(c), 'enabled': c['source_id'] in ('ripc_pms', 'kista_ippro'), 'max_pages': 1} for c in CONFIGS]
            path = root / 'sites.yaml'
            path.write_text(json.dumps({'sites': settings}, ensure_ascii=False), encoding='utf-8')
            ripc, kista = Mock(), Mock()
            ripc.get.side_effect = ['User-agent: *\nAllow: /', html('ripc', 'list_page1'), html('ripc', 'detail_1')]
            ripc.post.return_value = json.dumps(derived_ripc_json(self.ripc))
            kista.get.side_effect = ['User-agent: *\nAllow: /', kista_one_row()]
            kista.post.return_value = html('kista', 'detail_1')
            client = Mock()
            client.generate.return_value = json.dumps({'relevant': True, 'category': 'IP-R&D',
                                                       'participation_type': '협력기관', 'reason': 'fixture test', 'keywords': ['특허']})
            store = JsonStorage(root / 'data')
            result = run_pipeline(config_path=path, storage=store, public_dir=root / 'public', client=client,
                                  transport_factory=lambda source: {'ripc_pms': ripc, 'kista_ippro': kista}.get(source, Mock()),
                                  clock=lambda: CLOCK, logger=Mock())
            self.assertFalse(result.degraded)
            self.assertEqual(result.feed_count, 2)
            self.assertEqual(store.load_notices(), list(result.notices))
            sync = FeedClient('https://example.test/', cache_dir=root / 'cache',
                              transport=lambda url, timeout: (root / 'public' / url.rsplit('/', 1)[-1]).read_bytes())
            self.assertEqual(sync.sync().status, 'UPDATED')
            performances = PerformanceStore(root / 'performance.db')
            performances.create(Performance(performance_id='p1', project_name='한글 특허', keywords=['특허'], year=2025))
            cache_bytes, db_bytes = sync.cache_path.read_bytes(), performances.path.read_bytes()
            data = load_dashboard(sync.cache_path, performances.path)
            rows = notice_rows(data)
            self.assertEqual(len(rows), 2)
            for row in rows:
                matches = recommendation_rows(data, row['notice_id'], reference_year=2026, top_n=1)
                self.assertEqual(matches[0]['performance_id'], 'p1')
                self.assertTrue(matches[0]['sum_matches'])
            self.assertEqual(sync.cache_path.read_bytes(), cache_bytes)
            self.assertEqual(performances.path.read_bytes(), db_bytes)
        self.network.assert_not_called()
