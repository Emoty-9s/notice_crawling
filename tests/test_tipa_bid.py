import unittest
from pathlib import Path
from unittest.mock import Mock

from src.scrapers._html import StructureError
from src.scrapers.registry import ScraperRegistry
from src.scrapers.tipa_legacy_bid import TipaBidScraper
from src.core.extraction import discover

ROOT = Path(__file__).parent / 'fixtures/tipa_legacy_bid'


def html(name):
    return (ROOT / name).read_text(encoding='utf-8')


def scraper(**options):
    return TipaBidScraper(dict(source_id='tipa_legacy_bid', enabled=True,
        institution='중소기업기술정보진흥원', list_url='https://www.tipa.or.kr/s040305'), **options)


class TipaBidTests(unittest.TestCase):
    def test_real_pages_stable_ids_badges_and_dates(self):
        s = scraper()
        first, second = s.parse_list(html('list1.html')), s.parse_list(html('list2.html'))
        self.assertEqual((len(first), len(second)), (10, 10))
        self.assertEqual(first[0].source_notice_id, '17890')
        self.assertTrue(first[0].title.startswith('[자체입찰공고]'))
        self.assertEqual(first[0].published_at, '2026-11-09')
        self.assertNotEqual({n.source_notice_id for n in first}, {n.source_notice_id for n in second})
        notice = s.normalize(s.parse_detail(html('detail1.html'), first[0]))
        self.assertEqual(s.notice_id_for(first[0]), notice.notice_id)
        self.assertIsNone(notice.apply_end)  # no invented tender deadline from title
        resources = discover(html('detail2.html'), first[1].url)
        self.assertEqual(len(resources), 2)
        self.assertTrue(any(r.name.endswith('.hwpx') for r in resources))

    def test_three_page_limit_and_literal_path_pager(self):
        transport = Mock()
        transport.get.side_effect = [html('list1.html'), html('list2.html'), html('list3.html')]
        s = scraper(transport=transport)
        pages = s.fetch_list()
        self.assertEqual(len(pages), 3)
        self.assertEqual(transport.get.call_args_list[1].args[0], 'https://www.tipa.or.kr/s040305/index/page/2')
        self.assertEqual(len(s._parse_items(pages)), 30)
        self.assertEqual(s.page_links('<a href="https://other.test/s040305/index/page/2">2</a>'), [])

    def test_changed_or_empty_board_and_wrong_detail_fail_closed(self):
        s = scraper()
        with self.assertRaises(StructureError):
            s.parse_list('<table></table>')
        with self.assertRaises(StructureError):
            s.parse_list(html('list1.html').replace('/s040305/view/id/', '/other/id/'))
        with self.assertRaises(StructureError):
            s.parse_detail(html('detail2.html'), s.parse_list(html('list1.html'))[0])

    def test_disabled_source_never_requests_network_and_failure_is_isolated(self):
        bad, good = scraper(transport=Mock()), scraper(transport=Mock())
        bad.transport.get.return_value = '<html>unrecognized</html>'
        good.source_id = 'fixture_other'
        good.run = Mock(return_value=[])
        registry = ScraperRegistry(logger=Mock())
        registry.register(bad)
        registry.register(good)
        self.assertEqual(registry.run(), [])
        self.assertIn('tipa_legacy_bid', registry.errors)
        self.assertIn('fixture_other', registry.results)
        bad.enabled = False
        bad.transport.reset_mock()
        bad.run()
        bad.transport.get.assert_not_called()
