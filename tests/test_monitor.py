import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import URLError

from _night_fixtures import create_demo, BASE, STAMP
from src.local_client.monitor import (notice_badge, ordered_notices, read_local, read_sources,
                                     safe_original_url, sync_monitor)
from src.renderer.source_status import SOURCES, public_source_status, validate_source_status


class MonitorTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='night-test-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.snapshot, self.cache, self.db, self.health = create_demo(self.root)
        self.network = Mock(side_effect=lambda url, timeout: json.dumps(
            self.snapshot['metadata'] if url.endswith('metadata.json') else self.snapshot['feed']).encode())

    def test_feed_sync_does_not_require_database_and_respects_explicit_cache_name(self):
        cache = self.root / 'custom-name.json'
        missing_db = self.root / 'missing.db'
        result = sync_monitor(BASE, cache, missing_db, transport=self.network)
        self.assertEqual(result.connection, 'UPDATED')
        self.assertEqual(len(result.data.snapshot['feed']['notices']), 2)
        self.assertTrue(result.database_error)
        self.assertFalse(missing_db.exists())
        self.assertTrue(cache.exists())
        self.assertEqual(sync_monitor(BASE, cache, missing_db, transport=self.network).connection, 'UNCHANGED')

    def test_failed_sync_uses_valid_cache_and_never_mutates_database(self):
        before = self.db.read_bytes()
        result = sync_monitor(BASE, self.cache, self.db, transport=Mock(side_effect=URLError('private-error')))
        self.assertEqual(result.connection, 'FALLBACK')
        self.assertEqual(len(result.data.performances), 2)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertNotIn('private-error', repr(result))

    def test_connection_failure_without_cache_is_error_not_empty_success(self):
        result = sync_monitor(BASE, self.root/'missing.json', self.db, transport=Mock(side_effect=URLError('private')))
        self.assertEqual(result.connection, 'ERROR')
        self.assertIsNone(result.data)

    def test_wrong_origin_cache_is_not_displayed(self):
        self.assertIsNone(read_local(self.cache, self.db, 'https://different.test/'))

    def test_cache_database_collision_fails_before_network_or_file_write(self):
        before = self.db.read_bytes()
        result = sync_monitor(BASE, self.db, self.db, transport=self.network)
        self.assertEqual(result.error_code, 'PATH_COLLISION')
        self.network.assert_not_called()
        self.assertEqual(self.db.read_bytes(), before)

    def test_analysis_cache_database_collision_preserves_private_database(self):
        for suffix in ('.work.json','.technical.json'):
            database=Path(str(self.cache)+suffix)
            database.write_bytes(self.db.read_bytes());before=database.read_bytes()
            result=sync_monitor(BASE,self.cache,database,transport=self.network)
            self.assertEqual(result.error_code,'PATH_COLLISION')
            self.assertIsNone(read_local(self.cache,database,BASE))
            self.network.assert_not_called()
            self.assertEqual(database.read_bytes(),before)

    def test_optional_health_missing_does_not_fabricate_success(self):
        self.assertEqual(read_sources(BASE, self.cache, transport=Mock(side_effect=URLError('404'))), (None, False))

    def test_validated_health_falls_back_with_origin_binding(self):
        transport = Mock(return_value=json.dumps(self.health).encode())
        self.assertEqual(read_sources(BASE, self.cache, transport=transport), (self.health, False))
        transport.side_effect = URLError('offline')
        self.assertEqual(read_sources(BASE, self.cache, transport=transport), (self.health, True))
        self.assertEqual(read_sources('https://other.test/', self.cache, transport=transport), (None, False))

    def test_health_rejects_private_fields_and_oversized_payload(self):
        bad = copy.deepcopy(self.health)
        bad['sources'][0]['error_message'] = 'PRIVATE'
        for payload in (json.dumps(bad).encode(), b'x'*65537, b'{"schema_version":1,"schema_version":1}'):
            self.assertEqual(read_sources(BASE, self.cache, transport=Mock(return_value=payload)), (None, False))

    def test_public_health_projection_has_only_allowlisted_sources_and_fields(self):
        statuses = {source: dict(status='ERROR', last_attempt_at=STAMP, error_message='PRIVATE',
                                 error_type='PRIVATE', notices_found=0) for source in SOURCES}
        statuses['private-source'] = dict(status='SUCCESS', error_message='PRIVATE')
        document = validate_source_status(public_source_status(statuses, STAMP))
        self.assertEqual(len(document['sources']), len(SOURCES))
        self.assertNotIn('PRIVATE', json.dumps(document))
        self.assertNotIn('private-source', json.dumps(document))
        self.assertTrue(all(set(row) == {'source_id', 'status', 'checked_at', 'notices_found'} for row in document['sources']))

    def test_missing_central_attempt_is_unknown(self):
        doc = public_source_status({'kipa_bid': dict(status='SUCCESS', notices_found=10)}, STAMP)
        validate_source_status(doc)
        self.assertTrue(all(r['status'] == 'UNKNOWN' for r in doc['sources']))

    def test_new_then_updated_then_existing_without_mutating_feed(self):
        rows = copy.deepcopy(self.snapshot['feed']['notices'])
        new = copy.deepcopy(rows[0]); new['notice_id'] = 'NEW'
        existing = rows[0]; existing['is_new'] = False
        updated = rows[1]; updated['is_new'] = False
        baseline = {existing['notice_id']: existing['updated_at'], updated['notice_id']: '2026-10-01T00:00:00Z'}
        inputs = [existing, updated, new]
        before = copy.deepcopy(inputs)
        result = ordered_notices(inputs, baseline)
        self.assertEqual([notice_badge(row, baseline) for row in result], ['NEW', 'EXISTING', 'EXISTING'])
        self.assertEqual(inputs, before)

    def test_original_link_accepts_only_http_without_credentials(self):
        self.assertTrue(safe_original_url('https://example.test/notice/1'))
        for url in ('javascript:alert(1)', 'file:///C:/private', 'https://user:secret@example.test/', 'https://exa\nmple.test/'):
            self.assertFalse(safe_original_url(url))
