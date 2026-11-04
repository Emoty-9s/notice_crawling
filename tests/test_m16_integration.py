"""Offline contract integration, not evidence of live RIPC/KISTA DOM support."""

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from _m16_cases import ADAPTERS, CLOCK, CONFIGS, context, without_pager
from src.core.models import NoticeStatus
from src.core.storage import JsonStorage
from src.local_client.dashboard import load_dashboard, notice_rows, recommendation_rows
from src.local_client.performance import Performance, PerformanceStore
from src.local_client.sync import FeedClient
from src.pipeline import PipelineConfigError, load_site_configs, run_pipeline
from src.scrapers.registry import build_registry

# RIPC fixture closes April 2; exercise current eligibility on its last day.
CLOCK = CLOCK.replace(month=4, day=2)


class M16IntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='m16-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.configs = [{**deepcopy(site), 'enabled': site['source_id'] in ADAPTERS} for site in CONFIGS]
        self.config_path = self.root/'sites.yaml'
        self.config_path.write_text(json.dumps({'sites': self.configs}), encoding='utf-8')
        self.store = JsonStorage(self.root/'data')
        self.public = self.root/'public'
        self.client = Mock()
        self.client.generate.return_value = json.dumps({
            'relevant': True, 'category': 'IP-R&D', 'participation_type': '협력기관',
            'reason': '합성 통합 테스트', 'keywords': ['IP-R&D', '특허분석'],
        }, ensure_ascii=False)
        guard = patch('src.scrapers.base.urlopen', side_effect=AssertionError('network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def transports(self, failing=None):
        transports = {}
        for source in ADAPTERS:
            scraper, listing, detail, _ = context(source)
            if source == failing:
                listing = '<html>unverified JS shell</html>'
            transports[source] = Mock()
            transports[source].get.side_effect = ['User-agent: *\nAllow: /', without_pager(listing), detail]
        return lambda source: transports.get(source, Mock())

    def run_pipeline(self, failing=None):
        return run_pipeline(client=self.client, config_path=self.config_path, storage=self.store,
                            public_dir=self.public, clock=lambda: CLOCK, transport_factory=self.transports(failing), logger=Mock())

    def test_registry_runs_both_optional_sources_with_existing_five_disabled(self):
        registry = build_registry(self.configs, transport_factory=self.transports(), clock=lambda: CLOCK, logger=Mock())
        notices = registry.run()
        self.assertEqual({notice.source_id for notice in notices}, set(ADAPTERS))
        self.assertEqual(set(registry.results), set(ADAPTERS))
        self.assertEqual(len(registry.skipped), 5)

    def test_optional_sources_do_not_become_required_or_enabled_implicitly(self):
        configs = [site for site in self.configs if site['source_id'] not in ADAPTERS]
        registry = build_registry(configs, transport_factory=lambda source: Mock(), logger=Mock())
        self.assertEqual(registry.run(), [])
        self.assertEqual(len(registry.skipped), 5)
        self.assertTrue(all(not site['enabled'] for site in CONFIGS))

    def test_pipeline_storage_public_feed_and_m12_readback(self):
        result = self.run_pipeline()
        self.assertFalse(result.degraded)
        self.assertEqual(len(result.notices), 2)
        self.assertEqual(result.feed_count, 2)
        self.assertEqual(self.store.load_notices(), list(result.notices))
        def fetch(url, timeout):
            return (self.public/('metadata.json' if url.endswith('metadata.json') else 'notices.json')).read_bytes()
        client = FeedClient('https://example.test/', cache_dir=self.root/'cache', transport=fetch, clock=lambda: CLOCK)
        self.assertEqual(client.sync().status, 'UPDATED')
        self.assertEqual(client.sync().status, 'UNCHANGED')
        self.assertEqual({row['source_id'] for row in client.load_cache()['feed']['notices']}, set(ADAPTERS))

    def test_repeat_pipeline_has_stable_ids_and_existing_notices_no_new_ai_calls(self):
        first = self.run_pipeline()
        second = self.run_pipeline()
        self.assertEqual([n.notice_id for n in first.notices], [n.notice_id for n in second.notices])
        self.assertTrue(all(n.status == NoticeStatus.EXISTING for n in second.observed))
        self.assertEqual(self.client.generate.call_count, 2)

    def test_failed_source_preserves_last_notice_and_other_source_continues(self):
        first = self.run_pipeline()
        second = self.run_pipeline(failing='ripc_pms')
        self.assertEqual(second.scraper_failures, ('ripc_pms',))
        self.assertEqual(len(second.notices), 2)
        self.assertEqual(second.feed_count, 2)
        self.assertEqual(self.store.load_scraper_status()['ripc_pms']['status'], 'ERROR')
        self.assertEqual({n.notice_id for n in second.notices}, {n.notice_id for n in first.notices})

    def test_existing_dashboard_and_matcher_accept_both_public_notices_unchanged(self):
        self.run_pipeline()
        cache = self.root/'cache'
        client = FeedClient('https://example.test/', cache_dir=cache,
                            clock=lambda: CLOCK,
                            transport=lambda url, timeout: (self.public/url.rsplit('/', 1)[-1]).read_bytes())
        client.sync()
        store = PerformanceStore(self.root/'performance.db')
        store.create(Performance(performance_id='P1', project_name='IP-R&D 특허분석', keywords=['IP-R&D'], year=2025))
        data = load_dashboard(client.cache_path, store.path, clock=lambda: CLOCK)
        rows = notice_rows(data)
        self.assertEqual(len(rows), 2)
        for notice in rows:
            results = recommendation_rows(data, notice['notice_id'], reference_year=2026, top_n=1)
            self.assertEqual(results[0]['performance_id'], 'P1')
            self.assertTrue(results[0]['sum_matches'])

    def test_config_allows_m16_but_still_rejects_unimplemented_sources(self):
        self.assertEqual(len(load_site_configs(self.config_path)), len(CONFIGS))
        settings = deepcopy(self.configs)
        next(site for site in settings if site['source_id'] == 'kautm_tlo_news')['enabled'] = True
        self.config_path.write_text(json.dumps({'sites': settings}), encoding='utf-8')
        with self.assertRaises(PipelineConfigError):
            load_site_configs(self.config_path)
