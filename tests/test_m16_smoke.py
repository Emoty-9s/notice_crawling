"""Mocked probe behavior; these tests are not actual HTTP smoke evidence."""

import socket
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from _m16_cases import context, without_pager
from tools.m16_smoke import probe


class M16SmokeTests(unittest.TestCase):
    def test_success_probe_is_bounded_to_robots_list_and_one_detail(self):
        for source in ('ripc_pms', 'kista_ippro'):
            scraper, listing, detail, _ = context(source)
            transport = Mock()
            transport.get.side_effect = ['User-agent: *\nAllow: /', without_pager(listing), detail]
            with self.subTest(source=source), patch('src.scrapers.base.UrllibTransport', return_value=transport):
                report = probe(source, dict(scraper.config))
            self.assertEqual(report['status'], 'SUCCESS')
            self.assertTrue(report['title_nonempty'])
            self.assertEqual(transport.get.call_count, 3)

    def test_dns_failure_safe_report_without_any_retry_or_followup(self):
        scraper, _, _, _ = context('ripc_pms')
        transport = Mock()
        transport.get.side_effect = URLError(socket.gaierror(11001, 'private-marker'))
        with patch('src.scrapers.base.UrllibTransport', return_value=transport):
            report = probe('ripc_pms', dict(scraper.config))
        self.assertEqual((report['status'], report['reason'], report['errno']), ('BLOCKED', 'DNS_ERROR', 11001))
        self.assertNotIn('private-marker', repr(report))
        self.assertEqual(transport.get.call_count, 1)

    def test_http_denial_is_reported_without_bypass(self):
        scraper, _, _, _ = context('kista_ippro')
        transport = Mock()
        transport.get.side_effect = HTTPError('https://example.test', 403, 'private-marker', {}, None)
        with patch('src.scrapers.base.UrllibTransport', return_value=transport):
            report = probe('kista_ippro', dict(scraper.config))
        self.assertEqual(report['reason'], 'HTTP_403')
        self.assertEqual(transport.get.call_count, 1)

    def test_unverified_dom_is_not_a_successful_empty_smoke(self):
        scraper, _, _, _ = context('ripc_pms')
        transport = Mock()
        transport.get.side_effect = ['User-agent: *\nAllow: /', '<html>JS shell</html>']
        with patch('src.scrapers.base.UrllibTransport', return_value=transport):
            report = probe('ripc_pms', dict(scraper.config))
        self.assertEqual((report['status'], report['reason']), ('BLOCKED', 'StructureError'))
