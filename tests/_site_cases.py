"""Shared offline contract cases; mutations stay in memory, original HTML intact."""

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from src.core.models import GeminiStatus, Notice, NoticeStatus
from src.scrapers._html import StructureError, parse_html
from src.scrapers.khidi_business import KhidiBusinessScraper
from src.scrapers.kised_bid_public import KisedBidPublicScraper
from src.scrapers.rda_bid import RdaBidScraper
from src.scrapers.seoul_rnd_notice import SeoulRndNoticeScraper
from src.scrapers.kipa_bid import KipaBidScraper


ROOT = Path(__file__).resolve().parents[1]
CLOCK = datetime(2026, 10, 30, tzinfo=timezone.utc)
CONFIGS = json.loads((ROOT / 'config/sites.yaml').read_text(encoding='utf-8'))['sites']
SPECS = {
    'khidi_business': (KhidiBusinessScraper, '48951946', 14, '2026-10-29', '지원대상'),
    'kised_bid_public': (KisedBidPublicScraper, '4648', 10, '2026-10-28', '참가자격 등록'),
    'rda_bid': (RdaBidScraper, '100000813836', 10, '2026-10-28', '납품기한'),
    'seoul_rnd_notice': (SeoulRndNoticeScraper, '1129', 10, '2026-09-29', '최종선정 과제'),
    'kipa_bid': (KipaBidScraper, '134746', 10, '2026-10-22', '나라장터'),
}


def fixture_context(source):
    adapter, sample_id, count, published, token = SPECS[source]
    config = {**next(c for c in CONFIGS if c['source_id'] == source), 'enabled': True}
    scraper = adapter(config, clock=lambda: CLOCK, transport=Mock(), logger=Mock())
    folder = ROOT / 'tests/fixtures' / source
    list_html = (folder / 'list.html').read_text(encoding='utf-8')
    detail_html = (folder / 'detail.html').read_text(encoding='utf-8')
    items = scraper.parse_list(list_html)
    sample = next(i for i in items if i.source_notice_id == sample_id)
    return scraper, list_html, detail_html, items, sample


def list_container(scraper, root):
    if scraper.source_id == 'kised_bid_public':
        return root.one('div', id='listView')
    return scraper.list_table(root).one('tbody')


def body_container(scraper, root):
    return {
        'khidi_business': lambda: root.one('div', cls='viewContent'),
        'kised_bid_public': lambda: next(td for td in root.one('table', cls='tbl-basic tbl-row').find('td', cls='left') if td.attrs.get('colspan') == '4'),
        'rda_bid': lambda: root.one('div', cls='g-description-area', id='contents'),
        'seoul_rnd_notice': lambda: root.one('td', cls='view smartOutput'),
        'kipa_bid': lambda: root.one('div', id='article_text'),
    }[scraper.source_id]()


def sample_list_html(scraper, list_html, sample):
    root = parse_html(list_html)
    container = list_container(scraper, root)
    rows = container.elements('ul' if scraper.source_id == 'kised_bid_public' else 'tr')
    selected = [row for row in rows if any(
        parse_qs(urlsplit(a.attrs.get('href', '')).query).get(scraper.id_parameter) == [sample.source_notice_id]
        for a in row.find('a'))]
    assert len(selected) == 1
    container.children = selected
    return root.html()


class SiteCases:
    """Mixin deliberately not a TestCase: each site runs these cases once."""

    def setUp(self):
        guard = patch('src.scrapers.base.urlopen', side_effect=AssertionError('network forbidden'))
        self.network = guard.start()
        self.addCleanup(guard.stop)
        self.scraper, self.list_html, self.detail_html, self.items, self.sample = fixture_context(self.source)

    def test_actual_list_rows_and_identity(self):
        self.assertEqual(len(self.items), SPECS[self.source][2])
        self.assertEqual(len({i.source_notice_id for i in self.items}), len(self.items))
        self.assertTrue(all(i.title and i.url.startswith('https://') for i in self.items))
        self.assertEqual(self.sample.source_notice_id, SPECS[self.source][1])
        if self.source == 'rda_bid':
            self.assertEqual(self.sample.institution, '국립식량과학원')
            self.assertEqual(self.sample.category, '물품구매')
            self.assertEqual(self.sample.apply_end, '2026-11-03')
        if self.source == 'kised_bid_public':
            self.assertEqual((self.sample.apply_start, self.sample.apply_end), ('2026-10-27', '2026-11-10'))
            self.assertNotIn('새글', self.sample.title)

    def test_relative_detail_url_building_and_invalid_links(self):
        parts = urlsplit(self.sample.url)
        relative = parts.path + '?' + parts.query + '#top'
        self.assertEqual(self.scraper.build_detail_url(relative), self.sample.url)
        self.assertEqual(parse_qs(parts.query)[self.scraper.id_parameter], [self.sample.source_notice_id])
        for href in ('https://wrong.test/detail?id=1', parts.path + '?changed=1'):
            with self.subTest(href=href), self.assertRaises(StructureError):
                self.scraper.build_detail_url(href)
        for key, value in self.scraper.detail_query.items():
            changed = self.sample.url.replace(f'{key}={value}', f'{key}=changed', 1)
            with self.subTest(query_key=key), self.assertRaises(StructureError):
                self.scraper.build_detail_url(changed)

    def test_actual_detail_body_and_dates(self):
        parsed = self.scraper.parse_detail(self.detail_html, self.sample)
        self.assertEqual(parsed.link.published_at, SPECS[self.source][3])
        self.assertEqual(parsed.link.title, self.sample.title)
        self.assertIn(SPECS[self.source][4], parsed.content_text)
        self.assertNotIn('<script', parsed.content_text)
        self.assertNotIn('개인정보처리방침', parsed.content_text)
        self.assertNotIn('바로보기', parsed.content_text)
        self.assertNotIn('.hwp', parsed.content_text)
        if self.source == 'seoul_rnd_notice':
            self.assertNotIn('숭실대학교', parsed.content_text)  # neighbouring post, not body

    def test_notice_contract_json_and_stable_identity(self):
        parsed = self.scraper.parse_detail(self.detail_html, self.sample)
        notice = self.scraper.normalize(parsed)
        self.assertIsInstance(notice, Notice)
        self.assertEqual(notice.source_id, self.source)
        self.assertIs(notice.status, NoticeStatus.NEW)
        self.assertIs(notice.gemini.status, GeminiStatus.NOT_ANALYZED)
        self.assertEqual(Notice.from_json(notice.to_json()), notice)
        self.assertEqual(notice.notice_id, self.scraper.normalize(parsed).notice_id)
        self.assertEqual(notice.content_hash, self.scraper.normalize(parsed).content_hash)
        changed = self.scraper.normalize(replace(parsed, content_text=parsed.content_text + ' 변경된 조건'))
        self.assertEqual(notice.notice_id, changed.notice_id)
        self.assertNotEqual(notice.content_hash, changed.content_hash)
        self.assertEqual(notice.first_seen_at, CLOCK.isoformat())

    def test_offline_run_with_real_sample_pair(self):
        listing = sample_list_html(self.scraper, self.list_html, self.sample)
        self.scraper.transport.get.side_effect = [listing, self.detail_html]
        result = self.scraper.run()
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], Notice)
        self.assertEqual(result[0].title, self.sample.title)
        self.assertEqual(self.scraper.transport.get.call_args_list[1].args[0], self.sample.url)
        self.network.assert_not_called()

    def test_empty_list_preserves_actual_headers(self):
        root = parse_html(self.list_html)
        list_container(self.scraper, root).children = []
        self.assertEqual(self.scraper.parse_list(root.html()), [])
        self.scraper.transport.get.return_value = root.html()
        self.assertEqual(self.scraper.run(), [])
        self.assertEqual(self.scraper.transport.get.call_count, 1)

    def test_missing_list_container_is_explicit_failure(self):
        root = parse_html(self.list_html)
        container = list_container(self.scraper, root)
        container.parent.children.remove(container)
        with self.assertRaises(StructureError):
            self.scraper.parse_list(root.html())

    def test_changed_row_link_is_not_reported_as_empty(self):
        root = parse_html(sample_list_html(self.scraper, self.list_html, self.sample))
        for anchor in list_container(self.scraper, root).find('a'):
            if self.scraper.id_parameter in parse_qs(urlsplit(anchor.attrs.get('href', '')).query):
                anchor.attrs['href'] = '#changed'
        with self.assertRaises(StructureError):
            self.scraper.parse_list(root.html())

    def test_missing_body_is_explicit_failure(self):
        root = parse_html(self.detail_html)
        body = body_container(self.scraper, root)
        body.parent.children.remove(body)
        with self.assertRaises(StructureError):
            self.scraper.parse_detail(root.html(), self.sample)

    def test_empty_body_is_explicit_failure(self):
        root = parse_html(self.detail_html)
        body_container(self.scraper, root).children = []
        with self.assertRaises(StructureError):
            self.scraper.parse_detail(root.html(), self.sample)

    def test_wrong_detail_is_explicit_failure(self):
        with self.assertRaises(StructureError):
            self.scraper.parse_detail(self.detail_html, replace(self.sample, title='다른 공고'))
