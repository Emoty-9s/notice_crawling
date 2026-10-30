"""M10 offline end-to-end: real HTML adapters, fake Gemini and temp snapshots."""

import contextlib
import io
import json
import logging
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from _site_cases import (CLOCK, CONFIGS, SPECS, body_container, fixture_context,
                         list_container, sample_list_html)
from src.core.diff import DiffConflictError
from src.core.models import GeminiStatus, NoticeStatus
from src.core.storage import JsonStorage, StorageFormatError, StorageIOError
from src.main import main
from src.pipeline import MVP_SOURCES, PipelineConfigError, load_site_configs, run_pipeline
from src.scrapers._html import parse_html


def decision(relevant=True):
    return json.dumps(dict(relevant=relevant, category='IP-R&D', participation_type='협력기관',
                           reason='테스트용 수행기관 참여 근거', keywords=['특허분석']), ensure_ascii=False)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        tests_root = Path(__file__).resolve().parent
        temp = tempfile.TemporaryDirectory(dir=tests_root, prefix='pipeline-test-')
        self.root = Path(temp.name).resolve()
        if self.root.parent != tests_root or not self.root.name.startswith('pipeline-test-'):
            raise RuntimeError('unexpected cleanup target')
        self.addCleanup(temp.cleanup)
        self.storage = JsonStorage(self.root/'data')
        self.public = self.root/'public'
        self.config_path = self.root/'sites.yaml'
        self.configs = deepcopy(CONFIGS)
        for site in self.configs:
            site['enabled'] = site['source_id'] in MVP_SOURCES
        self.save_config()
        self.client = Mock()
        self.client.generate.return_value = decision()
        self.logger = Mock(spec=logging.Logger)
        self.now = CLOCK
        self.html = {}
        for source in SPECS:
            scraper, listing, detail, _, sample = fixture_context(source)
            self.html[source] = (sample_list_html(scraper, listing, sample), detail)
        for target in ('src.scrapers.base.urlopen', 'urllib.request.OpenerDirector.open'):
            guard = patch(target, side_effect=AssertionError('network forbidden'))
            guard.start()
            self.addCleanup(guard.stop)

    def save_config(self):
        self.config_path.write_text(json.dumps({'sites': self.configs}), encoding='utf-8')

    def run_pipeline(self, **kwargs):
        self.transports = {}
        for source, pair in self.html.items():
            self.transports[source] = Mock()
            self.transports[source].get.side_effect = pair
        return run_pipeline(client=self.client, config_path=self.config_path, storage=self.storage,
                            public_dir=self.public, clock=lambda: self.now,
                            transport_factory=self.transports.__getitem__, logger=self.logger, **kwargs)

    def feed(self):
        return json.loads((self.public/'notices.json').read_text(encoding='utf-8'))

    def test_first_run_new_analyzed_saved_and_public(self):
        result = self.run_pipeline()
        self.assertFalse(result.degraded)
        self.assertEqual(len(result.notices), 5)
        self.assertEqual(result.feed_count, 5)
        self.assertTrue(all(n.status == NoticeStatus.NEW and n.gemini.status == GeminiStatus.SUCCESS for n in result.observed))
        self.assertTrue(all(n.content_hash == n.gemini.analyzed_content_hash for n in result.observed))
        self.assertEqual(self.storage.load_notices(), list(result.notices))
        self.assertEqual(self.client.generate.call_count, 5)
        statuses = self.storage.load_scraper_status()
        self.assertEqual(set(statuses), MVP_SOURCES)
        self.assertTrue(all(s['status'] == 'SUCCESS' and s['notices_found'] == 1 for s in statuses.values()))
        self.assertEqual(len(self.feed()['notices']), 5)
        self.assertNotIn('content_text', json.dumps(self.feed()))

    def test_second_run_existing_no_duplicate_no_gemini_call(self):
        first = self.run_pipeline()
        before_feed = self.feed()['notices']
        self.now += timedelta(days=1)
        second = self.run_pipeline()
        self.assertEqual(self.client.generate.call_count, 5)
        self.assertEqual(len(second.notices), 5)
        self.assertTrue(all(n.status == NoticeStatus.EXISTING for n in second.observed))
        for before, after in zip(first.notices, second.notices):
            self.assertEqual(before.notice_id, after.notice_id)
            self.assertEqual(before.first_seen_at, after.first_seen_at)
            self.assertEqual(before.updated_at, after.updated_at)
            self.assertNotEqual(before.last_seen_at, after.last_seen_at)
            self.assertEqual(before.gemini, after.gemini)
        self.assertEqual(before_feed, self.feed()['notices'])

    def change_kipa(self):
        listing, detail = self.html['kipa_bid']
        scraper = fixture_context('kipa_bid')[0]
        root = parse_html(detail)
        body_container(scraper, root).children.append(' 추가 본문 변경 사항')
        self.html['kipa_bid'] = (listing, root.html())

    def test_changed_body_updated_reanalyzed(self):
        first = self.run_pipeline()
        self.change_kipa()
        self.now += timedelta(days=1)
        second = self.run_pipeline()
        changed = next(n for n in second.observed if n.source_id == 'kipa_bid')
        previous = next(n for n in first.notices if n.source_id == 'kipa_bid')
        self.assertEqual(changed.status, NoticeStatus.UPDATED)
        self.assertNotEqual(changed.content_hash, previous.content_hash)
        self.assertEqual(changed.gemini.analyzed_content_hash, changed.content_hash)
        self.assertEqual(changed.first_seen_at, previous.first_seen_at)
        self.assertEqual(self.client.generate.call_count, 6)
        self.assertEqual(len(second.notices), 5)

    def test_failed_scraper_keeps_old_source_and_other_sites_continue(self):
        first = self.run_pipeline()
        old = next(n for n in first.notices if n.source_id == 'khidi_business')
        last_success = self.storage.load_scraper_status()['khidi_business']['last_success_at']
        self.html['khidi_business'] = ('<html>changed structure</html>', '')
        self.now += timedelta(days=1)
        result = self.run_pipeline()
        self.assertTrue(result.degraded)
        self.assertEqual(result.scraper_failures, ('khidi_business',))
        self.assertEqual(len(result.observed), 4)
        self.assertEqual(next(n for n in result.notices if n.source_id == 'khidi_business'), old)
        self.assertEqual(result.feed_count, 5)
        status = self.storage.load_scraper_status()['khidi_business']
        self.assertEqual(status['status'], 'ERROR')
        self.assertEqual(status['last_success_at'], last_success)
        self.assertNotEqual(status['last_attempt_at'], last_success)

    def test_first_run_one_failed_scraper_still_saves_four(self):
        self.html['rda_bid'] = ('<html>invalid</html>', '')
        result = self.run_pipeline()
        self.assertEqual(len(result.notices), 4)
        self.assertEqual(result.feed_count, 4)
        self.assertEqual(result.scraper_failures, ('rda_bid',))

    def test_gemini_partial_failure_and_irrelevant_excluded(self):
        self.client.generate.side_effect = [TimeoutError('secret-test'), 'malformed', decision(False), decision(), decision()]
        result = self.run_pipeline()
        self.assertTrue(result.degraded)
        self.assertEqual(len(result.notices), 5)
        self.assertEqual(len(result.analysis_failures), 2)
        self.assertEqual(result.feed_count, 2)
        states = [n.gemini.status for n in result.observed]
        self.assertIn(GeminiStatus.PENDING, states)
        self.assertIn(GeminiStatus.FAILED, states)
        self.assertTrue(all(s['status'] == 'SUCCESS' for s in self.storage.load_scraper_status().values()))
        self.assertNotIn('secret-test', repr(self.logger.mock_calls))

    def test_failed_updated_analysis_keeps_history_and_other_feed_records(self):
        first = self.run_pipeline()
        old = next(n for n in first.notices if n.source_id == 'kipa_bid')
        self.change_kipa()
        self.client.generate.side_effect = TimeoutError('secret-test')
        result = self.run_pipeline()
        updated = next(n for n in result.notices if n.source_id == 'kipa_bid')
        self.assertEqual(updated.gemini.status, GeminiStatus.PENDING)
        self.assertEqual(updated.gemini.analyzed_content_hash, old.content_hash)
        self.assertEqual(updated.gemini.reason, old.gemini.reason)
        self.assertEqual(result.feed_count, 4)
        self.assertEqual(len(self.storage.load_notices()), 5)

    def empty_lists(self):
        for source in SPECS:
            scraper = fixture_context(source)[0]
            root = parse_html(self.html[source][0])
            list_container(scraper, root).children = []
            self.html[source] = (root.html(), self.html[source][1])

    def test_empty_successful_lists_generate_empty_feed(self):
        self.empty_lists()
        result = self.run_pipeline()
        self.assertFalse(result.degraded)
        self.assertEqual(result.notices, ())
        self.assertEqual(self.feed()['notices'], [])
        self.client.generate.assert_not_called()
        self.assertTrue(all(s['status'] == 'SUCCESS' and s['notices_found'] == 0
                            for s in self.storage.load_scraper_status().values()))

    def test_empty_successful_lists_preserve_unobserved_history(self):
        first = self.run_pipeline()
        self.empty_lists()
        self.now += timedelta(days=1)
        second = self.run_pipeline()
        self.assertEqual(second.notices, first.notices)
        self.assertEqual(second.observed, ())
        self.assertEqual(second.feed_count, 5)
        self.assertEqual(self.client.generate.call_count, 5)

    def test_all_failed_scrapers_preserve_snapshot_and_feed(self):
        first = self.run_pipeline()
        for source in self.html:
            self.html[source] = ('<html>broken</html>', '')
        result = self.run_pipeline()
        self.assertEqual(result.notices, first.notices)
        self.assertEqual(len(result.scraper_failures), 5)
        self.assertEqual(result.feed_count, 5)

    def test_disabled_source_retains_data_and_health_history(self):
        first = self.run_pipeline()
        old = next(n for n in first.notices if n.source_id == 'kipa_bid')
        for config in self.configs:
            if config['source_id'] == 'kipa_bid':
                config['enabled'] = False
        self.save_config()
        result = self.run_pipeline()
        self.assertEqual(result.skipped, ('kipa_bid',))
        self.transports['kipa_bid'].get.assert_not_called()
        self.assertEqual(next(n for n in result.notices if n.source_id == 'kipa_bid'), old)
        status = self.storage.load_scraper_status()['kipa_bid']
        self.assertEqual(status['status'], 'WARNING')
        self.assertEqual(status['error_type'], 'DISABLED')
        self.assertIsNotNone(status['last_success_at'])

    def test_malformed_storage_fails_before_collection_without_reset(self):
        self.storage.data_dir.mkdir()
        self.storage.notices_path.write_text('broken', encoding='utf-8')
        with patch('src.pipeline.build_mvp_registry') as registry, self.assertRaises(StorageFormatError):
            self.run_pipeline()
        registry.assert_not_called()
        self.assertEqual(self.storage.notices_path.read_text(encoding='utf-8'), 'broken')
        self.assertFalse(self.public.exists())

    def test_public_storage_collision_fails_before_collection(self):
        self.public = self.storage.data_dir
        with patch('src.pipeline.build_mvp_registry') as registry, self.assertRaises(PipelineConfigError):
            self.run_pipeline()
        registry.assert_not_called()
        self.assertFalse(self.storage.data_dir.exists())

    def test_malformed_status_fails_before_collection_without_reset(self):
        self.storage.data_dir.mkdir()
        self.storage.scraper_status_path.write_text('broken', encoding='utf-8')
        with patch('src.pipeline.build_mvp_registry') as registry, self.assertRaises(StorageFormatError):
            self.run_pipeline()
        registry.assert_not_called()
        self.assertEqual(self.storage.scraper_status_path.read_text(encoding='utf-8'), 'broken')

    def test_duplicate_stored_ids_fail_before_collection(self):
        first = self.run_pipeline()
        self.storage.save_notices([first.notices[0], first.notices[0]])
        with patch('src.pipeline.build_mvp_registry') as registry, self.assertRaises(DiffConflictError):
            self.run_pipeline()
        registry.assert_not_called()

    def test_feed_failure_preserves_prior_public_files_and_records_scraper_status(self):
        self.run_pipeline()
        old_feed = (self.public/'notices.json').read_bytes()
        self.now += timedelta(days=1)
        with patch('src.pipeline.write_feed', side_effect=StorageIOError('simulated')), self.assertRaises(StorageIOError):
            self.run_pipeline()
        self.assertEqual((self.public/'notices.json').read_bytes(), old_feed)
        self.assertEqual(len(self.storage.load_notices()), 5)
        self.assertTrue(all(s['last_attempt_at'].startswith('2026-10-31')
                            for s in self.storage.load_scraper_status().values()))

    def test_invalid_configurations_are_safe_errors(self):
        for text in ('broken', '{}', '{"sites":null}', '{"sites":[],"sites":[]}',
                     json.dumps({'sites': self.configs + [self.configs[0]]}),
                     json.dumps({'sites': [{**c, 'enabled': 'true'} for c in self.configs]}),
                     json.dumps({'sites': [{**c, 'enabled': True} for c in self.configs]})):
            self.config_path.write_text(text, encoding='utf-8')
            with self.subTest(text=text[:30]), self.assertRaises(PipelineConfigError):
                load_site_configs(self.config_path)

    def test_cli_no_enabled_sites_and_missing_gemini_config_make_no_request(self):
        console = io.StringIO()
        with patch.dict('os.environ', {}, clear=True), patch('src.main.run_pipeline') as run:
            with contextlib.redirect_stdout(console):
                self.assertEqual(main(['--config', str(self.config_path)]), 2)
            self.assertIn('MISSING_GEMINI_CONFIG', console.getvalue())
            for config in self.configs:
                config['enabled'] = False
            self.save_config()
            with contextlib.redirect_stdout(console):
                self.assertEqual(main(['--config', str(self.config_path)]), 2)
            run.assert_not_called()
            self.assertIn('NO_ENABLED_SITES', console.getvalue())

    def test_cli_success_and_partial_exit_codes(self):
        result = self.run_pipeline()
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-secret', 'GEMINI_MODEL': 'test-model'}), \
             patch('src.main.run_pipeline', return_value=result), contextlib.redirect_stdout(io.StringIO()) as console:
            self.assertEqual(main(['--config', str(self.config_path)]), 0)
            self.assertIn('PIPELINE PASS', console.getvalue())
        partial = replace(result, scraper_failures=('kipa_bid',))
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-secret', 'GEMINI_MODEL': 'test-model'}), \
             patch('src.main.run_pipeline', return_value=partial), contextlib.redirect_stdout(io.StringIO()) as console:
            self.assertEqual(main(['--config', str(self.config_path)]), 1)
            self.assertIn('PIPELINE PARTIAL', console.getvalue())


if __name__ == '__main__':
    unittest.main()
