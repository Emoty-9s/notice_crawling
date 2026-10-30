"""Offline storage validation, deterministic snapshots and atomic fault injection."""

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.core.models import GeminiResult, GeminiStatus, Notice, NoticeStatus
from src.core.storage import JsonStorage, StorageFormatError, StorageIOError, StorageSchemaError


def notice(number='1'):
    return Notice(
        notice_id=f'id-{number}', source_id='example', institution='예시 기관',
        title=f'협력기관 모집 {number}', url=f'https://example.test/{number}',
        content_text='공개 본문', content_hash=f'hash-{number}',
        first_seen_at='2026-10-30T00:00:00Z', last_seen_at='2026-10-30T00:00:00Z',
        updated_at='2026-10-30T00:00:00Z',
    )


class StorageTests(unittest.TestCase):
    def setUp(self):
        tests_root = Path(__file__).resolve().parent
        temp = tempfile.TemporaryDirectory(dir=tests_root, prefix='storage-test-')
        self.root = Path(temp.name).resolve()
        # Verify the exact target before recursive TemporaryDirectory cleanup.
        if self.root.parent != tests_root or not self.root.name.startswith('storage-test-'):
            raise RuntimeError('unexpected cleanup target')
        self.addCleanup(temp.cleanup)
        self.storage = JsonStorage(self.root / 'data')

    def test_missing_files_start_empty_without_creating_files(self):
        self.assertEqual(self.storage.load_notices(), [])
        self.assertEqual(self.storage.load_scraper_status(), {})
        self.assertFalse(self.storage.data_dir.exists())

    def test_empty_snapshots_round_trip(self):
        self.storage.save_notices([])
        self.storage.save_scraper_status({})
        self.assertEqual(self.storage.load_notices(), [])
        self.assertEqual(self.storage.load_scraper_status(), {})
        self.assertEqual(self.storage.notices_path.read_bytes(), b'[]\n')
        self.assertEqual(self.storage.scraper_status_path.read_bytes(), b'{}\n')

    def test_notice_round_trip_including_gemini_and_null(self):
        first = replace(notice(), status=NoticeStatus.UPDATED, gemini=GeminiResult(
            status=GeminiStatus.SUCCESS, relevant=False, score=0,
            reason='범위 외', analyzed_at='2026-10-30T00:00:00Z', analyzed_content_hash='hash-1'))
        self.storage.save_notices([first])
        self.assertEqual(self.storage.load_notices(), [first])
        text = self.storage.notices_path.read_text(encoding='utf-8')
        self.assertIn('예시 기관', text)
        self.assertIn('"apply_end": null', text)

    def test_multiple_notices_preserve_order(self):
        records = [notice('2'), notice('1'), notice('3')]
        self.storage.save_notices(records)
        self.assertEqual(self.storage.load_notices(), records)

    def test_scraper_status_round_trip(self):
        statuses = {
            'site-a': {'status': 'SUCCESS', 'notices_found': 2, 'last_attempt_at': '2026-10-30T00:00:00Z',
                       'last_success_at': '2026-10-30T00:00:00Z', 'error_type': None, 'error_message': None},
            'site-b': {'status': 'ERROR', 'notices_found': None, 'error_type': 'TimeoutError', 'error_message': 'timeout'},
            'site-c': {'status': 'WARNING', 'notices_found': 0},
        }
        self.storage.save_scraper_status(statuses)
        self.assertEqual(self.storage.load_scraper_status(), statuses)

    def test_deterministic_format_and_status_key_order(self):
        left = {'b': {'notices_found': 0, 'status': 'SUCCESS'}, 'a': {'status': 'WARNING'}}
        right = {'a': {'status': 'WARNING'}, 'b': {'status': 'SUCCESS', 'notices_found': 0}}
        self.storage.save_scraper_status(left)
        first = self.storage.scraper_status_path.read_bytes()
        self.storage.save_scraper_status(right)
        self.assertEqual(self.storage.scraper_status_path.read_bytes(), first)
        self.assertNotIn(b'\r', first)
        self.assertTrue(first.endswith(b'\n'))
        self.storage.save_notices([notice()])
        first = self.storage.notices_path.read_bytes()
        self.storage.save_notices([notice()])
        self.assertEqual(self.storage.notices_path.read_bytes(), first)

    def test_malformed_json_and_nonstandard_constants_raise_without_reset(self):
        self.storage.data_dir.mkdir()
        for path, load in ((self.storage.notices_path, self.storage.load_notices),
                           (self.storage.scraper_status_path, self.storage.load_scraper_status)):
            for payload in (b'', b'{broken', b'NaN', b'Infinity', b'{"x":1,"x":2}', b'\xff'):
                path.write_bytes(payload)
                with self.subTest(path=path.name, payload=payload), self.assertRaises(StorageFormatError):
                    load()
                self.assertEqual(path.read_bytes(), payload)

    def test_wrong_notice_top_level_and_record_schema(self):
        self.storage.data_dir.mkdir()
        good = notice().to_dict()
        invalid = [None, {}, 'text', [None], [{}], [{**good, 'status': 'UNKNOWN'}],
                   [{**good, 'title': 42}], [{**good, 'gemini': None}],
                   [{**good, 'gemini': {**good['gemini'], 'status': 'UNKNOWN'}}],
                   [{**good, 'gemini': {**good['gemini'], 'score': True}}]]
        missing_optional = dict(good)
        del missing_optional['apply_end']
        missing_nested = {**good, 'gemini': dict(good['gemini'])}
        del missing_nested['gemini']['reason']
        invalid += [[missing_optional], [missing_nested], [{**good, 'unexpected': 1}]]
        for data in invalid:
            text = json.dumps(data)
            self.storage.notices_path.write_text(text, encoding='utf-8')
            with self.subTest(data=data), self.assertRaises(StorageSchemaError):
                self.storage.load_notices()
            self.assertEqual(self.storage.notices_path.read_text(encoding='utf-8'), text)

    def test_scraper_status_schema_errors_on_load_and_save(self):
        self.storage.save_scraper_status({'ok': {'status': 'SUCCESS'}})
        old = self.storage.scraper_status_path.read_bytes()
        invalid = [[], None, {'': {'status': 'SUCCESS'}}, {'a': {}}, {'a': []},
                   {'a': {'status': 'NEW'}}, {'a': {'status': []}},
                   {'a': {'status': 'SUCCESS', 'notices_found': True}},
                   {'a': {'status': 'SUCCESS', 'notices_found': -1}},
                   {'a': {'status': 'ERROR', 'error_message': 42}},
                   {'a': {'status': 'ERROR', 'last_attempt_at': ''}},
                   {'a': {'status': 'SUCCESS', 'extra': 1}}]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(StorageSchemaError):
                self.storage.save_scraper_status(data)
            self.assertEqual(self.storage.scraper_status_path.read_bytes(), old)
            self.storage.scraper_status_path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(StorageSchemaError):
                self.storage.load_scraper_status()
            self.storage.scraper_status_path.write_bytes(old)

    def test_invalid_save_input_preserves_existing_notices(self):
        self.storage.save_notices([notice()])
        old = self.storage.notices_path.read_bytes()
        for value in (None, {}, (notice(),), [notice().to_dict()], [notice(), None],
                      [replace(notice(), title='\ud800')]):
            with self.subTest(value=value), self.assertRaises(StorageSchemaError):
                self.storage.save_notices(value)
            self.assertEqual(self.storage.notices_path.read_bytes(), old)

    def test_atomic_replace_sees_old_complete_file_and_new_complete_temp(self):
        self.storage.save_notices([notice('old')])
        old = self.storage.notices_path.read_bytes()
        real_replace = os.replace

        def verify_replace(source, target):
            self.assertEqual(Path(source).parent, self.storage.data_dir)
            self.assertNotEqual(Path(source), Path(target))
            self.assertEqual(Path(target).read_bytes(), old)
            data = json.loads(Path(source).read_text(encoding='utf-8'))
            self.assertEqual(data[0]['notice_id'], 'id-new')
            real_replace(source, target)

        with patch('src.core.storage.os.replace', side_effect=verify_replace) as commit:
            self.storage.save_notices([notice('new')])
        commit.assert_called_once()
        self.assertEqual(self.storage.load_notices(), [notice('new')])
        self.assertEqual(list(self.storage.data_dir.glob('*.tmp')), [])

    def test_partial_write_failure_preserves_old_file_and_cleans_temp(self):
        self.storage.save_notices([notice('old')])
        old = self.storage.notices_path.read_bytes()

        def fail_mid_write(handle, text):
            handle.write(text[:15])
            handle.flush()
            raise OSError('disk full')

        with patch('src.core.storage._write_and_sync', side_effect=fail_mid_write):
            with self.assertRaises(StorageIOError):
                self.storage.save_notices([notice('new')])
        self.assertEqual(self.storage.notices_path.read_bytes(), old)
        self.assertEqual(list(self.storage.data_dir.glob('*.tmp')), [])

    def test_fsync_and_replace_failure_preserve_both_kinds_of_snapshot(self):
        self.storage.save_notices([notice()])
        self.storage.save_scraper_status({'a': {'status': 'SUCCESS'}})
        for patch_target in ('os.fsync', 'os.replace'):
            for path, save, value in (
                (self.storage.notices_path, self.storage.save_notices, [notice('new')]),
                (self.storage.scraper_status_path, self.storage.save_scraper_status, {'a': {'status': 'ERROR'}}),
            ):
                old = path.read_bytes()
                with self.subTest(patch_target=patch_target, path=path.name):
                    with patch('src.core.storage.' + patch_target, side_effect=OSError('injected failure')):
                        with self.assertRaises(StorageIOError):
                            save(value)
                    self.assertEqual(path.read_bytes(), old)
                    self.assertEqual(list(self.storage.data_dir.glob('*.tmp')), [])

    def test_failed_first_save_does_not_publish_partial_file(self):
        with patch('src.core.storage.os.replace', side_effect=OSError('failure')):
            with self.assertRaises(StorageIOError):
                self.storage.save_notices([notice()])
        self.assertFalse(self.storage.notices_path.exists())
        self.assertEqual(self.storage.load_notices(), [])
        self.assertEqual(list(self.storage.data_dir.glob('*.tmp')), [])

    def test_io_error_is_not_treated_as_empty_store(self):
        with patch('pathlib.Path.read_text', side_effect=PermissionError('denied')):
            with self.assertRaises(StorageIOError) as error:
                self.storage.load_notices()
        self.assertIsInstance(error.exception.__cause__, PermissionError)

    def test_default_paths_do_not_depend_on_working_directory(self):
        storage = JsonStorage()
        self.assertEqual(storage.data_dir, Path(__file__).resolve().parents[1] / 'data')
        self.assertEqual(storage.notices_path.name, 'notices.json')
        self.assertEqual(storage.scraper_status_path.name, 'scraper_status.json')


if __name__ == '__main__':
    unittest.main()
