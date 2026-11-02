"""Provisional M16 contract samples, explicitly NOT live HTML capture tests."""

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from src.core.models import GeminiStatus, Notice, NoticeStatus
from src.core.normalizer import generate_content_hash, generate_notice_id
from src.scrapers._html import StructureError, parse_html
from src.scrapers.base import ScraperError
from src.scrapers.kista_ippro import KistaScraper
from src.scrapers.ripc_pms import RipcScraper


ROOT = Path(__file__).resolve().parents[1]
CLOCK = datetime(2026, 11, 2, tzinfo=timezone.utc)
CONFIGS = json.loads((ROOT/'config/sites.yaml').read_text(encoding='utf-8'))['sites']
ADAPTERS = {'ripc_pms': RipcScraper, 'kista_ippro': KistaScraper}


def context(source):
    config = {**next(c for c in CONFIGS if c['source_id'] == source), 'enabled': True,
              'max_pages': 3, 'http': {'max_retries': 0}}
    transport, logger = Mock(), Mock()
    scraper = ADAPTERS[source](config, transport=transport, clock=lambda: CLOCK, logger=logger)
    folder = ROOT/'tests/fixtures/m16_contract'/source
    listing = (folder/'list.contract.html').read_text(encoding='utf-8')
    detail = (folder/'detail.contract.html').read_text(encoding='utf-8')
    page2 = (folder/'page2.contract.html').read_text(encoding='utf-8')
    return scraper, listing, detail, page2


def without_pager(html):
    root = parse_html(html)
    for nav in root.find('nav'):
        nav.parent.children.remove(nav)
    return root.html()


class M16ContractCases:
    def setUp(self):
        guard = patch('src.scrapers.base.urlopen', side_effect=AssertionError('network forbidden'))
        self.network = guard.start()
        self.addCleanup(guard.stop)
        self.scraper, self.listing, self.detail, self.page2 = context(self.source)
        self.item = self.scraper.parse_list(self.listing)[0]

    def test_list_title_category_dates_and_stable_detail_url(self):
        self.assertTrue(self.item.title)
        self.assertTrue(self.item.category)
        self.assertTrue(self.item.url.startswith('https://'))
        expected = ('2026-03-19', '2026-04-02') if self.source == 'ripc_pms' else ('2026-01-12', '2026-12-31')
        self.assertEqual((self.item.apply_start, self.item.apply_end), expected)
        self.assertNotIn('접수중', self.item.title)

    def test_detail_metadata_body_and_explicit_year_dates(self):
        parsed = self.scraper.parse_detail(self.detail, self.item)
        self.assertEqual((parsed.link.apply_start, parsed.link.apply_end), (self.item.apply_start, self.item.apply_end))
        self.assertIsNone(parsed.link.published_at)
        self.assertNotIn('합성 첨부파일', parsed.content_text)
        if self.source == 'ripc_pms':
            self.assertIn('상표출원 대리', parsed.content_text)
        else:
            self.assertEqual(parsed.content_text, '')

    def test_attachments_absolute_unique_not_downloaded_or_added_to_notice(self):
        attachments = self.scraper.parse_attachments(self.detail)
        self.assertEqual(attachments, (f'https://{urlsplit(self.item.url).netloc}/m16-contract/sample.hwp',))
        notice = self.scraper.normalize(self.scraper.parse_detail(self.detail, self.item))
        self.assertNotIn('attachments', notice.to_dict())
        self.scraper.transport.get.assert_not_called()

    def test_notice_model_enum_roundtrip_hash_and_existing_m03_url_identity(self):
        notice = self.scraper.normalize(self.scraper.parse_detail(self.detail, self.item))
        self.assertEqual(Notice.from_json(notice.to_json()), notice)
        self.assertIs(notice.status, NoticeStatus.NEW)
        self.assertIs(notice.gemini.status, GeminiStatus.NOT_ANALYZED)
        self.assertEqual(notice.notice_id, generate_notice_id(source_id=self.source, title=notice.title, url=notice.url))
        self.assertEqual(notice.content_hash, generate_content_hash(content_text=notice.content_text))

    def test_same_input_same_notice_and_title_change_does_not_change_id(self):
        parsed = self.scraper.parse_detail(self.detail, self.item)
        first = self.scraper.normalize(parsed)
        self.assertEqual(first, self.scraper.normalize(parsed))
        other = self.scraper.normalize(replace(parsed, link=replace(parsed.link, title=parsed.link.title+' 제목 수정')))
        self.assertEqual(first.notice_id, other.notice_id)

    def test_business_year_is_part_of_identity(self):
        first = self.scraper.normalize(self.scraper.parse_detail(self.detail, self.item))
        key = 'bizYear=2026' if self.source == 'ripc_pms' else 'annYy=2026'
        item = replace(self.item, url=self.item.url.replace(key, key.replace('2026', '2025')))
        parsed = self.scraper.parse_detail(self.detail, item)
        self.assertNotEqual(first.notice_id, self.scraper.normalize(parsed).notice_id)

    def test_html_entity_whitespace_and_body_change_use_existing_normalizers(self):
        root = parse_html(self.listing)
        anchor = self.scraper._table(root).find('a')[0]
        anchor.children = ['  '+self.item.title.replace(' ', '\n  ')+'  ']
        changed_item = self.scraper.parse_list(root.html())[0]
        self.assertEqual(changed_item, self.item)
        parsed = self.scraper.parse_detail(self.detail, self.item)
        notice = self.scraper.normalize(parsed)
        changed = self.scraper.normalize(replace(parsed, content_text=parsed.content_text+' 조건 변경'))
        self.assertEqual(notice.notice_id, changed.notice_id)
        self.assertNotEqual(notice.content_hash, changed.content_hash)

    def test_empty_optional_fields_map_to_none(self):
        item = self.scraper.parse_list(self.page2)[0]
        self.assertIsNone(item.category)
        self.assertIsNone(item.apply_start)
        self.assertIsNone(item.apply_end)
        self.assertIsNone(item.published_at)

    def test_empty_detail_category_uses_existing_nullable_contract(self):
        root = parse_html(self.detail)
        for heading in root.find('th'):
            if heading.text() == self.scraper.detail_category_label:
                heading.parent.elements('td')[0].children = ['-']
        parsed = self.scraper.parse_detail(root.html(), self.item)
        self.assertIsNone(self.scraper.normalize(parsed).category)

    def test_bare_ajax_shell_is_error_not_an_empty_success(self):
        root = parse_html(self.listing)
        root.one('tbody').children = []
        with self.assertRaisesRegex(StructureError, 'UNVERIFIED_DYNAMIC_LIST'):
            self.scraper.parse_list(root.html())

    def test_explicit_empty_message_is_empty(self):
        root = parse_html(self.listing)
        body = root.one('tbody')
        body.children = parse_html('<tr><td colspan="9">등록된 공고가 없습니다.</td></tr>').children
        self.assertEqual(self.scraper.parse_list(root.html()), [])

    def test_changed_html_and_detail_title_fail(self):
        with self.assertRaises(StructureError):
            self.scraper.parse_list('<html>changed/login</html>')
        with self.assertRaises(StructureError):
            self.scraper.parse_detail('<html>changed/login</html>', self.item)

    def test_detail_url_rejects_wrong_host_board_identity_and_canonicalizes_navigation(self):
        canonical = self.item.url
        self.assertEqual(self.scraper.build_detail_url(canonical+'&contractPage=9#top'), canonical)
        self.assertEqual(self.scraper.build_detail_url(urlsplit(canonical).path+'?'+urlsplit(canonical).query), canonical)
        for href in (canonical.replace(urlsplit(canonical).netloc, 'wrong.test'), canonical.split('?')[0],
                     canonical.replace(self.scraper.identity_parameters[-1]+'=', 'wrong=')):
            with self.assertRaises((StructureError, ValueError)):
                self.scraper.build_detail_url(href)

    def test_pagination_collects_two_pages_via_only_observed_links(self):
        self.scraper.transport.get.side_effect = ['User-agent: *\nAllow: /', self.listing, self.page2]
        pages = self.scraper.fetch_list()
        self.assertEqual(len(pages), 2)
        self.assertEqual(len(self.scraper.parse_list(pages)), 2)
        self.assertEqual(self.scraper.transport.get.call_args_list[2].args[0], self.scraper.page_links(self.listing)[0])

    def test_page_window_is_bounded_and_warns(self):
        self.scraper.max_pages = 1
        self.scraper.transport.get.side_effect = ['User-agent: *\nAllow: /', self.listing]
        self.assertEqual(len(self.scraper.fetch_list()), 1)
        self.scraper.logger.warning.assert_called_once()
        self.assertEqual(self.scraper.transport.get.call_count, 2)

    def test_js_pagination_is_explicit_error_not_first_page_only(self):
        root = parse_html(self.listing)
        root.one('nav').one('a').attrs['href'] = 'javascript:unverified(2)'
        with self.assertRaisesRegex(StructureError, 'UNVERIFIED_JAVASCRIPT_PAGINATION'):
            self.scraper.page_links(root.html())

    def test_pagination_does_not_follow_other_origin(self):
        root = parse_html(self.listing)
        root.one('nav').one('a').attrs['href'] = 'https://wrong.test/list?page=2'
        with self.assertRaises(StructureError):
            self.scraper.page_links(root.html())

    def test_duplicate_pages_do_not_duplicate_notices(self):
        self.assertEqual(self.scraper.parse_list([self.listing, self.listing]), [self.item])
        root = parse_html(self.listing)
        root.one('nav').one('a').attrs['href'] = self.scraper.config['list_url']
        self.scraper.transport.get.side_effect = ['User-agent: *\nAllow: /', root.html()]
        self.assertEqual(len(self.scraper.fetch_list()), 1)

    def test_robots_denial_stops_before_list_request(self):
        self.scraper.transport.get.return_value = 'User-agent: *\nDisallow: /'
        with self.assertRaises(ScraperError):
            self.scraper.run()
        self.assertEqual(self.scraper.transport.get.call_count, 1)

    def test_robots_404_allowed_but_403_or_dns_not_bypassed(self):
        self.scraper.transport.get.side_effect = [HTTPError('https://example.test', 404, 'absent', {}, None), without_pager(self.listing)]
        self.assertEqual(len(self.scraper.fetch_list()), 1)
        for error in (HTTPError('https://example.test', 403, 'blocked', {}, None), URLError('DNS')):
            self.scraper.transport.get.reset_mock()
            self.scraper.transport.get.side_effect = error
            with self.assertRaises((HTTPError, URLError)):
                self.scraper.fetch_list()
            self.assertEqual(self.scraper.transport.get.call_count, 1)

    def test_disabled_scraper_makes_no_http_requests(self):
        self.scraper.enabled = False
        self.assertEqual(self.scraper.run(), [])
        self.scraper.transport.get.assert_not_called()

    def test_all_requests_use_base_timeout_and_user_agent(self):
        self.scraper.transport.get.side_effect = ['User-agent: *\nAllow: /', without_pager(self.listing), self.detail]
        notices = self.scraper.run()
        self.assertEqual(len(notices), 1)
        for call in self.scraper.transport.get.call_args_list:
            self.assertEqual(call.kwargs['timeout'], self.scraper.http_settings.timeout_seconds)
            self.assertEqual(call.kwargs['headers']['User-Agent'], self.scraper.http_settings.user_agent)

    def test_malformed_period_never_creates_dates(self):
        changed = self.listing.replace('2026-03-19 18:20 ~ 2026-04-02 11:00', 'unknown').replace('2026-01-12<br>~ 2026-12-31', 'unknown')
        with self.assertRaises(StructureError):
            self.scraper.parse_list(changed)
