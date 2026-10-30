"""Real adapter registration and aggregate fake-transport regression."""

import logging
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from _site_cases import CLOCK, CONFIGS, SPECS, fixture_context, sample_list_html
from src.scrapers.registry import build_mvp_registry


class MvpRegistryTests(unittest.TestCase):
    def build(self, *, bad=None, enabled=True):
        configs = [{**c, 'enabled': enabled} for c in CONFIGS]
        original = deepcopy(configs)
        transports = {}
        for source in SPECS:
            scraper, listing, detail, items, sample = fixture_context(source)
            transport = Mock()
            transport.get.side_effect = ['<html>changed</html>' if source == bad else sample_list_html(scraper, listing, sample), detail]
            transports[source] = transport
        registry = build_mvp_registry(configs, transport_factory=transports.__getitem__,
                                      clock=lambda: CLOCK, logger=Mock(spec=logging.Logger))
        self.assertEqual(configs, original)
        return registry, transports

    def test_five_real_adapters_run_without_network(self):
        with patch('src.scrapers.base.urlopen', side_effect=AssertionError('network forbidden')) as network:
            registry, transports = self.build()
            notices = registry.run()
        self.assertEqual([n.source_id for n in notices], list(SPECS))
        self.assertEqual(registry.errors, {})
        self.assertEqual(len(registry.results), 5)
        self.assertEqual(len({n.notice_id for n in notices}), 5)
        network.assert_not_called()

    def test_real_site_parse_failure_is_isolated(self):
        registry, transports = self.build(bad='khidi_business')
        self.assertEqual(len(registry.run()), 4)
        self.assertEqual(set(registry.errors), {'khidi_business'})
        self.assertEqual(registry.errors['khidi_business'].stage, 'parse_list')

    def test_disabled_config_is_preserved(self):
        registry, transports = self.build(enabled=False)
        self.assertEqual(registry.run(), [])
        self.assertEqual(set(registry.skipped), set(SPECS))
        for transport in transports.values():
            transport.get.assert_not_called()

    def test_missing_or_duplicate_configs_are_errors(self):
        with self.assertRaises(ValueError):
            build_mvp_registry([])
        with self.assertRaises(ValueError):
            build_mvp_registry(CONFIGS + [CONFIGS[0]])
