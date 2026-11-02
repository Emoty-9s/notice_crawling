"""Provisional RIPC contract tests; raw HTTP fixtures remain a blocker."""
import unittest
from _m16_cases import M16ContractCases
from src.scrapers._html import StructureError, parse_html


class RipcContractTests(M16ContractCases, unittest.TestCase):
    source = 'ripc_pms'

    def test_active_config_uses_partner_tender_paths_and_remains_disabled(self):
        config = self.scraper.config
        expected = 'https://pms.ripc.org/pms/biz/partner/tenderNotice/list.do'
        self.assertEqual(config['list_url'], expected)
        self.assertEqual(config['fallback']['url'], expected)
        self.assertEqual(config['m16_validation']['requested_list_url'], expected)
        self.assertIn('/partner/tenderNotice/info.do?', config['detail_url_pattern'])
        from _m16_cases import CONFIGS
        self.assertFalse(next(c for c in CONFIGS if c['source_id'] == self.source)['enabled'])

    def test_applicant_detail_and_pagination_paths_are_rejected(self):
        wrong = self.item.url.replace('/partner/tenderNotice/', '/applicant/notice/')
        with self.assertRaises(StructureError):
            self.scraper.build_detail_url(wrong)
        with self.assertRaises(StructureError):
            self.scraper.parse_list(self.listing.replace('/partner/tenderNotice/info.do', '/applicant/notice/info.do'))
        with self.assertRaises(StructureError):
            self.scraper.page_links(self.listing.replace('/partner/tenderNotice/list.do', '/applicant/notice/list.do'))

    def test_seven_columns_required_including_budget(self):
        root = parse_html(self.listing)
        row = root.one('thead').one('tr')
        row.children.remove(row.elements('th')[5])
        body = root.one('tbody').one('tr')
        body.children.remove(body.elements('td')[5])
        with self.assertRaises(StructureError):
            self.scraper.parse_list(root.html())

    def test_budget_is_not_confused_with_other_fields_or_added_to_notice(self):
        self.assertEqual(self.scraper.parse_list(self.listing.replace('80991900', '-'))[0], self.item)
        self.assertEqual(self.item.institution, '경기 센터')
        self.assertEqual(self.item.category, '소상공인 IP창출 지원')
        notice = self.scraper.normalize(self.scraper.parse_detail(self.detail, self.item))
        self.assertNotIn('80991900', notice.content_text)
        self.assertNotIn('budget', notice.to_dict())

    def test_tender_detail_reads_period_and_unit_business_labels(self):
        html = self.detail.replace('2026-03-19 18:20', '2026-03-20 09:00')
        html = html.replace('소상공인 IP창출 지원', '합성 단위사업')
        parsed = self.scraper.parse_detail(html, self.item)
        self.assertEqual(parsed.link.apply_start, '2026-03-20')
        self.assertEqual(parsed.link.apply_end, '2026-04-02')
        self.assertEqual(parsed.link.category, '합성 단위사업')
