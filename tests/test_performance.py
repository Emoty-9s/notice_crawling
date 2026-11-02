"""M13 local SQLite/CSV acceptance tests; all data is synthetic and temporary."""

import csv
from contextlib import closing
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.local_client.performance import (
    APPLICATION_ID, COLUMNS, CSVImportError, DuplicatePerformanceError, Performance,
    PerformanceDatabaseError, PerformanceNotFoundError, PerformanceStore, PerformanceValidationError,
)


PRIVATE = 'synthetic-private-marker'


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='performance-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root/'private'/'performance.db'
        self.store = PerformanceStore(self.path, timeout=0)
        self.record = Performance(
            performance_id='P001', project_name='반도체 IP 전략', client='가상 고객', year=2025,
            technical_field='반도체', work_type='특허분석', keywords=['IP-R&D', '소재'],
            description='가상 프로젝트 설명\n둘째 줄', attorneys=['변리사 A', '변리사 B'], notes=PRIVATE)
        network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden'))
        network.start()
        self.addCleanup(network.stop)

    def csv_file(self, rows, *, header=COLUMNS, encoding='utf-8-sig'):
        path = self.root/'input.csv'
        with path.open('w', encoding=encoding, newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def row(self, identity='P002', **changes):
        values = dict(zip(COLUMNS, [identity, '수입 프로젝트', '테스트 고객', '2024', '바이오', '용역',
                                    '특허;바이오', '설명, 쉼표\n여러 줄', '담당 A;담당 B', PRIVATE]))
        values.update(changes)
        return [values[name] for name in COLUMNS]

    def test_first_creation_empty_database_and_schema_version(self):
        self.assertTrue(self.path.is_file())
        self.assertEqual(self.store.search(), [])
        with closing(sqlite3.connect(self.path)) as connection, connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 1)
            self.assertEqual(connection.execute('PRAGMA application_id').fetchone()[0], APPLICATION_ID)
            self.assertEqual(tuple(row[1] for row in connection.execute('PRAGMA table_info(performances)')), COLUMNS)

    def test_insert_read_update_delete_full_roundtrip(self):
        self.assertEqual(self.store.create(self.record), self.record)
        self.assertEqual(self.store.get('P001'), self.record)
        changed = replace(self.record, project_name='변경 프로젝트', year=2026, keywords=['새 키워드'], attorneys=[])
        self.assertEqual(self.store.update(changed), changed)
        self.assertEqual(self.store.get('P001'), changed)
        self.assertTrue(self.store.delete('P001'))
        self.assertIsNone(self.store.get('P001'))
        self.assertFalse(self.store.delete('P001'))

    def test_minimal_record_and_nullable_year(self):
        record = Performance(performance_id='  MIN  ', project_name=' 제목 ')
        self.store.create(record)
        self.assertEqual(self.store.get('MIN'), record)
        self.assertEqual((record.performance_id, record.project_name, record.year, record.keywords), ('MIN', '제목', None, ()))

    def test_duplicate_never_overwrites_existing_record(self):
        self.store.create(self.record)
        with self.assertRaisesRegex(DuplicatePerformanceError, '^DUPLICATE_PERFORMANCE_ID$'):
            self.store.create(replace(self.record, notes='changed'))
        self.assertEqual(self.store.get('P001'), self.record)
        self.assertEqual(len(self.store.search()), 1)

    def test_update_missing_does_not_insert(self):
        with self.assertRaises(PerformanceNotFoundError):
            self.store.update(self.record)
        self.assertEqual(self.store.search(), [])

    def test_reopen_store_and_subsequent_writes_preserve_records(self):
        self.store.create(self.record)
        reopened = PerformanceStore(self.path)
        self.assertEqual(reopened.get('P001'), self.record)
        reopened.create(replace(self.record, performance_id='P002'))
        self.assertEqual(len(self.store.search()), 2)

    def test_validation_rejects_invalid_fields_without_changing_database(self):
        self.store.create(self.record)
        invalid = [dict(performance_id=''), dict(project_name=' '), dict(client=None), dict(year=True),
                   dict(year=0), dict(year=10000), dict(year='2025'), dict(year=2025.0),
                   dict(keywords='text'), dict(keywords=[1]), dict(attorneys=[' ']),
                   dict(notes='\x00'), dict(description='\ud800')]
        for changes in invalid:
            with self.subTest(changes=list(changes)), self.assertRaises(PerformanceValidationError):
                replace(self.record, **changes)
        self.assertEqual(self.store.search(), [self.record])
        with self.assertRaises(PerformanceValidationError):
            self.store.create({'project_name': PRIVATE})

    def test_csv_bom_quotes_multiline_lists_and_blank_year(self):
        path = self.csv_file([self.row(), self.row('P003', year='', keywords='', attorneys='')])
        self.assertEqual(self.store.import_csv(path), 2)
        imported = self.store.get('P002')
        self.assertEqual(imported.keywords, ('특허', '바이오'))
        self.assertEqual(imported.attorneys, ('담당 A', '담당 B'))
        self.assertEqual(imported.description, '설명, 쉼표\n여러 줄')
        self.assertIsNone(self.store.get('P003').year)
        self.assertEqual(self.store.get('P003').keywords, ())

    def test_csv_reordered_header_supported(self):
        values = dict(zip(COLUMNS, self.row()))
        header = tuple(reversed(COLUMNS))
        self.assertEqual(self.store.import_csv(self.csv_file([[values[name] for name in header]], header=header)), 1)
        self.assertEqual(self.store.get('P002').project_name, values['project_name'])

    def test_header_only_csv_returns_zero(self):
        self.store.create(self.record)
        self.assertEqual(self.store.import_csv(self.csv_file([])), 0)
        self.assertEqual(self.store.search(), [self.record])

    def test_invalid_csv_headers_never_change_existing_records(self):
        self.store.create(self.record)
        for header in ([], COLUMNS[:-1], COLUMNS+('extra',), COLUMNS[:-1]+('project_name',)):
            with self.subTest(header=header), self.assertRaisesRegex(CSVImportError, 'INVALID_CSV_HEADER'):
                self.store.import_csv(self.csv_file([], header=header))
        self.assertEqual(self.store.search(), [self.record])

    def test_malformed_csv_row_after_valid_row_does_not_partially_import(self):
        self.store.create(self.record)
        invalid = [self.row('P003', project_name=''), self.row('P003', year='202X'),
                   self.row('P003', year='0'), self.row('P003', year='1.0'),
                   self.row('P003')[:-1], self.row('P003')+['extra'], self.row('P003', notes='\x00')]
        for row in invalid:
            with self.subTest(length=len(row)), self.assertRaises(CSVImportError) as error:
                self.store.import_csv(self.csv_file([self.row(), row]))
            self.assertIsNotNone(error.exception.line)
            self.assertNotIn(PRIVATE, str(error.exception))
            self.assertEqual(self.store.search(), [self.record])

    def test_duplicate_within_csv_rejected_without_partial_import(self):
        with self.assertRaisesRegex(CSVImportError, 'DUPLICATE_CSV_ID'):
            self.store.import_csv(self.csv_file([self.row(), self.row()]))
        self.assertEqual(self.store.search(), [])

    def test_duplicate_against_database_rolls_back_preceding_csv_insert(self):
        self.store.create(self.record)
        with self.assertRaisesRegex(CSVImportError, 'DUPLICATE_PERFORMANCE_ID'):
            self.store.import_csv(self.csv_file([self.row(), self.row('P001')]))
        self.assertIsNone(self.store.get('P002'))
        self.assertEqual(self.store.search(), [self.record])

    def test_reimport_same_csv_does_not_duplicate_or_overwrite(self):
        path = self.csv_file([self.row()])
        self.store.import_csv(path)
        before = self.store.search()
        with self.assertRaises(CSVImportError):
            self.store.import_csv(path)
        self.assertEqual(self.store.search(), before)

    def test_malformed_quoting_encoding_and_missing_file_preserve_database(self):
        self.store.create(self.record)
        path = self.root/'broken.csv'
        for raw in (b'\xff', (','.join(COLUMNS)+'\n"unterminated').encode('utf-8')):
            path.write_bytes(raw)
            with self.assertRaises(CSVImportError) as error:
                self.store.import_csv(path)
            self.assertNotIn(PRIVATE, str(error.exception))
        with self.assertRaises(CSVImportError):
            self.store.import_csv(self.root/'absent.csv')
        self.assertEqual(self.store.search(), [self.record])

    def test_sql_failure_mid_import_rolls_back_all_imported_records(self):
        self.store.create(self.record)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TRIGGER deny_insert BEFORE INSERT ON performances "
                               "WHEN new.performance_id='P003' BEGIN SELECT RAISE(ABORT, 'private SQL error'); END")
        with self.assertRaises(PerformanceDatabaseError) as error:
            self.store.import_csv(self.csv_file([self.row(), self.row('P003')]))
        self.assertNotIn('private SQL error', str(error.exception))
        self.assertEqual(self.store.search(), [self.record])

    def test_database_write_error_rolls_back_update_and_delete(self):
        self.store.create(self.record)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            for action in ('UPDATE', 'DELETE'):
                connection.execute(f"CREATE TRIGGER deny_{action} AFTER {action} ON performances "
                                   "BEGIN SELECT RAISE(ABORT, 'private SQL error'); END")
        for operation in (lambda: self.store.update(replace(self.record, notes='changed')), lambda: self.store.delete('P001')):
            with self.assertRaises(PerformanceDatabaseError):
                operation()
            self.assertEqual(self.store.get('P001'), self.record)

    def test_locked_database_returns_error_without_data_loss(self):
        self.store.create(self.record)
        connection = sqlite3.connect(self.path)
        try:
            connection.execute('BEGIN IMMEDIATE')
            with self.assertRaises(PerformanceDatabaseError):
                self.store.create(replace(self.record, performance_id='P002'))
        finally:
            connection.rollback()
            connection.close()
        self.assertEqual(self.store.search(), [self.record])

    def test_corrupt_database_not_reinitialized(self):
        path = self.root/'corrupt.db'
        raw = b'not sqlite '+PRIVATE.encode('utf-8')
        path.write_bytes(raw)
        with self.assertRaises(PerformanceDatabaseError) as error:
            PerformanceStore(path)
        self.assertNotIn(PRIVATE, str(error.exception))
        self.assertEqual(path.read_bytes(), raw)

    def test_unrelated_database_and_unknown_version_preserved(self):
        path = self.root/'unrelated.db'
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute('CREATE TABLE unrelated (value TEXT)')
            connection.execute('INSERT INTO unrelated VALUES (?)', (PRIVATE,))
        before = path.read_bytes()
        with self.assertRaisesRegex(PerformanceDatabaseError, 'UNSUPPORTED_DATABASE_SCHEMA'):
            PerformanceStore(path)
        self.assertEqual(path.read_bytes(), before)
        self.store.create(self.record)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute('PRAGMA user_version = 99')
        before = self.path.read_bytes()
        with self.assertRaises(PerformanceDatabaseError):
            PerformanceStore(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_changed_schema_and_invalid_stored_record_raise_instead_of_resetting(self):
        self.store.create(self.record)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE performances SET keywords = 'not JSON'")
        with self.assertRaisesRegex(PerformanceDatabaseError, 'INVALID_STORED_PERFORMANCE'):
            self.store.get('P001')
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute('ALTER TABLE performances ADD COLUMN unexpected TEXT')
        with self.assertRaisesRegex(PerformanceDatabaseError, 'INVALID_DATABASE_SCHEMA'):
            self.store.search()

    def test_deleted_database_is_not_silently_recreated_by_operations(self):
        self.path.unlink()
        with self.assertRaises(PerformanceDatabaseError):
            self.store.create(self.record)
        self.assertFalse(self.path.exists())

    def test_search_all_fields_unicode_casefold_and_year_filter(self):
        self.store.create(self.record)
        for term in ('P001', '전략', '가상 고객', '2025', '반도체', '특허분석', 'ip-r&d', '둘째 줄', '변리사 B', PRIVATE):
            with self.subTest(term=term):
                self.assertEqual(self.store.search(term), [self.record])
        self.assertEqual(self.store.search(year=2025), [self.record])
        self.assertEqual(self.store.search(year=2024), [])
        self.assertEqual(self.store.search('absent'), [])
        other = replace(self.record, performance_id='P002', project_name='Straße')
        self.store.create(other)
        self.assertEqual(self.store.search('STRASSE'), [other])

    def test_search_literal_wildcards_and_sql_injection_are_data(self):
        self.store.create(self.record)
        other = replace(self.record, performance_id="ID'; DROP TABLE performances;--", project_name='100%_literal')
        self.store.create(other)
        self.assertEqual(self.store.get(other.performance_id), other)
        self.assertEqual(self.store.search('%_'), [other])
        self.assertEqual(self.store.search("' OR 1=1 --"), [])
        self.assertEqual(len(self.store.search()), 2)

    def test_search_deterministic_order_and_pagination(self):
        for identity, year in [('Z', None), ('B', 2025), ('A', 2025), ('C', 2026)]:
            self.store.create(replace(self.record, performance_id=identity, year=year))
        self.assertEqual([p.performance_id for p in self.store.search()], ['C', 'A', 'B', 'Z'])
        self.assertEqual([p.performance_id for p in self.store.search(limit=2, offset=1)], ['A', 'B'])

    def test_search_and_identity_validation(self):
        for arguments in ({'limit': 0}, {'offset': -1}, {'limit': True}, {'query': None}, {'year': True}):
            with self.subTest(arguments=arguments), self.assertRaises(PerformanceValidationError):
                self.store.search(**arguments)
        for operation in (self.store.get, self.store.delete):
            with self.assertRaises(PerformanceValidationError):
                operation(' ')
        with self.assertRaises(PerformanceValidationError):
            PerformanceStore(self.path, timeout=float('nan'))

    def test_local_operations_never_call_feed_or_gemini(self):
        with patch('src.local_client.sync.FeedClient.sync', side_effect=AssertionError('feed sync forbidden')), \
             patch('src.ai.gemini.GeminiClient.generate', side_effect=AssertionError('AI forbidden')):
            self.store.create(self.record)
            self.store.import_csv(self.csv_file([self.row()]))
            self.store.search('특허')
            self.store.update(replace(self.record, notes='local only'))
            self.store.delete('P001')
        self.assertIsNotNone(self.store.get('P002'))


if __name__ == '__main__':
    unittest.main()
