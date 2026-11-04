"""Company-upload acceptance tests. Synthetic files stay under tests only."""
import copy
import csv
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from src.local_client.upload import (UploadError, amount_value, normalize_header, preview_upload)
from src.local_client.upload_store import save_preview
from src.local_client.performance import PerformanceStore, Performance, PerformanceDatabaseError
from src.local_client.dashboard import _load_performances
from src.local_client.matcher import match_notice

try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None


@unittest.skipUnless(Workbook, 'desktop readers require requirements-test-desktop.txt')
class UploadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='upload-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root/'private'/'performance.db'
        # Import must never invoke HTTP, sync or any AI, even when packages exist.
        for target in ('urllib.request.OpenerDirector.open', 'socket.create_connection',
                       'src.local_client.sync.FeedClient.sync', 'src.ai.gemini.GeminiClient.generate'):
            guard = patch(target, side_effect=AssertionError('external call forbidden'))
            guard.start()
            self.addCleanup(guard.stop)

    def xlsx(self, rows, sheets=None):
        book = Workbook()
        active = book.active
        active.title = '실적'
        for row in rows:
            active.append(row)
        for name, values in (sheets or {}).items():
            sheet = book.create_sheet(name)
            for row in values:
                sheet.append(row)
        path = self.root/'company.xlsx'
        book.save(path)
        book.close()
        return path

    def standard(self, extra=None):
        return self.xlsx([['관리번호', '사업명', '고객사', '수행년도', '업무내용', '금액'],
                          ['001245', '반도체 특허분석', '가상 연구원', 2026, '반도체 특허분석 수행', '1,200만원'],
                          *(extra or [])])

    def metadata(self):
        with closing(sqlite3.connect(self.db)) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(r) for r in connection.execute('SELECT * FROM performance_uploads_v1')]

    def test_standard_xlsx_and_no_database_write_during_preview(self):
        preview = preview_upload(self.standard())
        self.assertEqual((preview.sheet_count, len(preview.rows), preview.review_count), (1, 1, 0))
        row = preview.rows[0]
        self.assertEqual((row.project_name, row.client, row.year, row.amount),
                         ('반도체 특허분석', '가상 연구원', 2026, '12000000'))
        self.assertFalse(self.db.exists())

    def test_all_requested_management_aliases_preserve_prefix_slash_and_zero(self):
        from src.local_client.upload import ALIASES
        for alias in ALIASES['management_id']:
            with self.subTest(alias=alias):
                path = self.xlsx([[alias, '프로젝트 명', '발주처'], ['PRJ-2026/001', '특허 분석', '가상기관']])
                self.assertEqual(preview_upload(path).rows[0].management_id, 'PRJ-2026/001')

    def test_numeric_excel_id_with_display_zero_mask(self):
        path = self.xlsx([['관리번호', '용역명'], [1245, '특허 분석']])
        import openpyxl
        book = openpyxl.load_workbook(path)
        book.active['A2'].number_format = '000000'
        book.save(path)
        book.close()
        row = preview_upload(path).rows[0]
        self.assertEqual(row.management_id, '001245')
        self.assertEqual(row.raw_source['columns']['관리번호'], 1245)
        self.assertEqual(row.raw_source['number_formats']['관리번호'], '000000')

    def test_header_normalization_is_not_substring_matching(self):
        self.assertEqual(normalize_header('  프로젝트_명  '), normalize_header('프로젝트 명'))
        self.assertNotEqual(normalize_header('사업명'), normalize_header('사업내용'))
        path = self.xlsx([['프로젝트_명', '계약 금액 (만원)', '실적 관리 번호'], ['분석', 12, '000001']])
        row = preview_upload(path).rows[0]
        self.assertEqual((row.project_name, row.amount, row.management_id), ('분석', '120000', '000001'))

    def test_requested_company_layouts_and_missing_management_id(self):
        examples = [
            (['프로젝트 번호', '프로젝트명', '발주처', '수행기간', '주요업무'],
             ['PRJ-1', '분석', '기관', '2025.01.02 ~ 2025.12.31', '주요 분석']),
            (['과제번호', '과업명', '기관명', '기술분야', '사업내용'], ['R/001', '분석', '기관', '바이오', '내용']),
            (['No', '용역명', '수요기관', '계약일', '완료일', '계약금액', '비고'],
             [1, '분석', '기관', '2025/01/02', '2025/12/31', '1억원', '내용']),
        ]
        for headers, data in examples:
            with self.subTest(headers=headers):
                row = preview_upload(self.xlsx([headers, data])).rows[0]
                self.assertEqual(row.project_name, '분석')
                self.assertEqual(row.client, '기관')
        self.assertIsNone(row.management_id)
        self.assertEqual((row.start_date, row.end_date, row.year), ('2025-01-02', '2025-12-31', 2025))

    def test_titles_merged_cells_nonfirst_header_multi_and_empty_sheets(self):
        path = self.xlsx([['회사명'], ['2026년 실적'], [], ['관리번호', '사업명', '고객사'],
                          ['001', '프로젝트A', '기관'], [], ['합계', None, 10]],
                         {'둘째': [['프로젝트명', '발주처'], ['프로젝트B', '기관']], '빈 sheet': []})
        import openpyxl
        book = openpyxl.load_workbook(path)
        book['실적'].merge_cells('A1:C1')
        book.save(path)
        book.close()
        preview = preview_upload(path)
        self.assertEqual((preview.sheet_count, len(preview.rows), preview.excluded), (2, 2, 1))
        self.assertEqual([r.row_number for r in preview.rows], [5, 2])
        self.assertEqual({r.sheet for r in preview.rows}, {'실적', '둘째'})

    def test_totals_and_repeated_headers_are_excluded(self):
        path = self.xlsx([['사업명', '고객사'], ['정상', '기관'], ['사업명', '고객사'],
                          ['TOTAL', 100], ['총계', 200], ['소계', 300]])
        preview = preview_upload(path)
        self.assertEqual((len(preview.rows), preview.excluded), (1, 4))

    def test_unknown_columns_and_long_description_are_preserved(self):
        description = '반도체 특허 기술 분석을 수행하고 조사 결과를 보고하는 업무입니다. ' * 10
        path = self.xlsx([['사업명', '업무 내용', '아무 열', '아무 열'], ['분석', description, '미분류내용', '둘째 원문']])
        row = preview_upload(path).rows[0]
        self.assertEqual(row.description, description.strip())
        self.assertEqual(len(row.raw_source['columns']), 4)
        self.assertIn('둘째 원문', row.raw_source['columns'].values())
        self.assertIn('미분류내용', row.searchable_text)
        self.assertIn('미분류내용', row.match_text)
        self.assertEqual(row.status, '확인 필요')

    def test_date_year_amount_id_and_description_heuristics_are_flagged(self):
        path = self.xlsx([['사업명', 'A', 'B', 'C', 'D', 'E'],
                          ['프로젝트1', datetime(2025, 1, 2), '1,000,000원', 'PRJ-001', '상세 업무 내용이 충분히 긴 설명입니다. '*5, 2025],
                          ['프로젝트2', datetime(2026, 2, 3), '2,000,000원', 'PRJ-002', '다른 업무 내용이 충분히 긴 설명입니다. '*5, 2026]])
        preview = preview_upload(path)
        self.assertEqual(preview.rows[0].management_id, 'PRJ-001')
        self.assertEqual(preview.rows[0].amount, '1000000')
        self.assertEqual(preview.rows[0].year, 2025)
        self.assertEqual(preview.review_count, 2)
        self.assertEqual(preview.mappings['실적']['A']['field'], 'date_candidate')
        self.assertEqual(preview.mappings['실적']['D']['field'], 'description')

    def test_ambiguous_numeric_columns_are_not_arbitrarily_classified(self):
        path = self.xlsx([['사업명', '미상열'], ['프로젝트1', 12345], ['프로젝트2', 67890]])
        preview = preview_upload(path)
        self.assertNotIn('미상열', preview.mappings['실적'])
        self.assertIsNone(preview.rows[0].amount)
        self.assertIsNone(preview.rows[0].management_id)
        self.assertEqual(preview.rows[0].status, '확인 필요')

    def test_formula_is_not_evaluated_and_original_is_preserved(self):
        path = self.xlsx([['사업명', '비고'], ['분석', '=HYPERLINK("https://example.test/private","값")']])
        row = preview_upload(path).rows[0]
        self.assertTrue(row.raw_source['columns']['비고'].startswith('=HYPERLINK'))
        self.assertNotIn('https://', row.match_text)
        self.assertEqual(row.status, '확인 필요')

    def test_no_project_name_is_reviewable_and_saveable(self):
        path = self.xlsx([['고객사', '업무내용'], ['기관', '특허 분석 업무']])
        preview = preview_upload(path)
        self.assertEqual(preview.review_count, 1)
        result = save_preview(self.db, preview)
        self.assertEqual((result.saved, result.review), (1, 1))
        self.assertTrue(PerformanceStore(self.db).search()[0].project_name.startswith('이름 미확인'))

    def test_unknown_header_uses_review_fallback(self):
        preview = preview_upload(self.xlsx([['항목 A', '항목 B'], ['프로젝트1', '기관'], ['프로젝트2', '기관']]))
        self.assertEqual((len(preview.rows), preview.review_count), (2, 2))
        self.assertIn('header 매핑 확인 필요', preview.rows[0].issues)

    def test_empty_file_missing_header_and_no_valid_rows_errors(self):
        for rows, code in (([], 'NO_SHEET_DATA'), ([['회사명'], ['한 셀 설명']], 'HEADER_NOT_FOUND'),
                           ([['사업명', '고객사']], 'NO_VALID_ROWS')):
            with self.subTest(code=code), self.assertRaisesRegex(UploadError, code):
                preview_upload(self.xlsx(rows))

    def test_unsupported_unreadable_corrupt_file_safe_errors(self):
        with self.assertRaisesRegex(UploadError, 'UNSUPPORTED_EXTENSION'):
            preview_upload(self.root/'secret.xlsx.exe')
        for path in (self.root/'missing.xlsx', self.root/'broken.xlsx'):
            if path.name.startswith('broken'):
                path.write_bytes(b'private corrupted contents')
            with self.assertRaisesRegex(UploadError, '^FILE_READ_FAILED$'):
                preview_upload(path)

    def test_same_file_reupload_is_idempotent_without_source_copy(self):
        path = self.standard()
        before = path.read_bytes()
        preview = preview_upload(path)
        self.assertEqual(save_preview(self.db, preview).saved, 1)
        result = save_preview(self.db, preview)
        self.assertEqual((result.saved, result.duplicates, result.failed), (0, 1, 0))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual({p.name for p in self.db.parent.iterdir()}, {'performance.db'})

    def test_business_duplicate_preserves_existing_record(self):
        store = PerformanceStore(self.db)
        original = Performance(performance_id='legacy', project_name='반도체 특허분석', client='가상 연구원', year=2026,
                               description='기존 설명')
        store.create(original)
        result = save_preview(self.db, preview_upload(self.standard()))
        self.assertEqual((result.saved, result.duplicates), (0, 1))
        self.assertEqual(store.get('legacy'), original)

    def test_same_management_id_different_clients_is_not_duplicate(self):
        path = self.standard([['001245', '반도체 특허분석', '다른 기관', 2026, '같은 제목', 200]])
        result = save_preview(self.db, preview_upload(path))
        self.assertEqual((result.saved, result.duplicates), (2, 0))

    def test_different_management_ids_same_business_are_reported_duplicate(self):
        path = self.standard([['OTHER', '반도체 특허분석', '가상 연구원', 2026, '변경 설명', 200]])
        result = save_preview(self.db, preview_upload(path))
        self.assertEqual((result.saved, result.duplicates), (1, 1))

    def test_management_context_deduplicates_missing_year_without_overwriting(self):
        one = preview_upload(self.xlsx([['관리번호', '사업명', '고객사', '비고'], ['PRJ-1', '분석', '기관A', '기존 설명']]))
        two = preview_upload(self.xlsx([['관리번호', '사업명', '고객사', '비고'], ['PRJ-1', '분석', '기관A', '수정 설명']]))
        save_preview(self.db, one)
        self.assertEqual(save_preview(self.db, two).duplicates, 1)
        self.assertIn('기존 설명', PerformanceStore(self.db).search()[0].description)

    def test_header_order_changes_do_not_create_exact_duplicates(self):
        one = preview_upload(self.xlsx([['사업명', '관리번호'], ['분석', '001']]))
        two = preview_upload(self.xlsx([['관리번호', '사업명'], ['001', '분석']]))
        self.assertEqual(one.rows[0].fingerprint, two.rows[0].fingerprint)
        self.assertEqual(save_preview(self.db, one).saved, 1)
        self.assertEqual(save_preview(self.db, two).duplicates, 1)

    def test_partial_row_failure_preserves_other_rows(self):
        preview = preview_upload(self.standard([['2', '다른 분석', '다른 기관', 2026, '내용', 300]]))
        preview.rows[1].year = 0
        result = save_preview(self.db, preview)
        self.assertEqual((result.saved, result.failed), (1, 1))
        self.assertEqual(len(PerformanceStore(self.db).search()), 1)

    def test_db_failures_do_not_expose_contents_or_reset_database(self):
        self.db.parent.mkdir()
        self.db.write_bytes(b'private contents')
        with self.assertRaises(PerformanceDatabaseError) as error:
            save_preview(self.db, preview_upload(self.standard()))
        self.assertNotIn('private', str(error.exception))
        self.assertEqual(self.db.read_bytes(), b'private contents')

    def test_auxiliary_table_preserves_v1_contract_and_normalized_raw_fields(self):
        save_preview(self.db, preview_upload(self.standard()))
        metadata = self.metadata()[0]
        self.assertEqual(metadata['management_id'], '001245')
        normalized = json.loads(metadata['normalized'])
        self.assertEqual(normalized['description'], '반도체 특허분석 수행')
        raw = json.loads(metadata['raw_source'])
        self.assertEqual(raw['columns']['관리번호'], '001245')
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 1)
        self.assertEqual(len(_load_performances(self.db)), 1)
        self.assertEqual(len(PerformanceStore(self.db).search()), 1)

    def test_matcher_uses_unknown_text_without_management_id_or_amount_bias(self):
        path = self.xlsx([['사업명', '고객사', '연도', '관리번호', '금액', '미분류'],
                          ['분석', '기관', 2026, 'AI-123', '12000000원', '반도체 특허 분석']])
        save_preview(self.db, preview_upload(path))
        records = _load_performances(self.db)
        target = dict(category='기타', participation_type='기관', title='분석', summary='내용', keywords=['반도체', 'AI-123', '12000000원'])
        result = match_notice(target, records, reference_year=2026)[0]
        self.assertIn('반도체', result.matched_terms)
        self.assertNotIn('AI-123', result.matched_terms)
        self.assertNotIn('12000000원', result.matched_terms)
        self.assertIn('AI-123', self.metadata()[0]['searchable_text'])

    def test_empty_production_db_contains_no_demo_rows(self):
        store = PerformanceStore(self.db)
        self.assertEqual(store.search(), [])
        self.assertEqual(_load_performances(self.db), ())

    def test_csv_utf8_cp949_quotes_and_leading_zeros(self):
        for encoding in ('utf-8-sig', 'cp949'):
            path = self.root/'company.csv'
            with path.open('w', encoding=encoding, newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(['관리 번호', '사업명', '고객사', '비고'])
                writer.writerow(['001245', '분석, 조사', '기관', '여러 줄\n설명'])
            row = preview_upload(path).rows[0]
            self.assertEqual(row.management_id, '001245')
            self.assertEqual(row.description, '여러 줄\n설명')

    def test_date_and_amount_units_parse_without_guessing(self):
        self.assertEqual(amount_value('1.5억원'), '150000000.0')
        self.assertEqual(amount_value('12', '계약금액(백만원)'), '12000000')
        self.assertIsNone(amount_value('계약 협의 중'))
        row = preview_upload(self.xlsx([['사업명', '완료일'], ['분석', '2026-02-30']])).rows[0]
        self.assertIsNone(row.end_date)
        self.assertIn('end_date 값 확인 필요', row.issues)

    def test_duplicate_cleanup_follows_existing_dao_delete(self):
        preview = preview_upload(self.standard())
        save_preview(self.db, preview)
        store = PerformanceStore(self.db)
        store.delete(store.search()[0].performance_id)
        self.assertEqual(self.metadata(), [])
        self.assertEqual(save_preview(self.db, preview).saved, 1)

    @unittest.skipUnless(importlib.util.find_spec('xlwt'), 'xls fixture generator is test-only')
    def test_actual_legacy_xls_multi_sheet_and_zero_format(self):
        import xlwt
        book = xlwt.Workbook()
        sheet = book.add_sheet('Legacy')
        for column, value in enumerate(['관리번호', '용역명', '계약일']):
            sheet.write(0, column, value)
        sheet.write(1, 0, 1245, xlwt.easyxf(num_format_str='000000'))
        sheet.write(1, 1, '특허 분석')
        sheet.write(1, 2, datetime(2025, 1, 2), xlwt.easyxf(num_format_str='YYYY-MM-DD'))
        book.add_sheet('빈 sheet')
        path = self.root/'legacy.xls'
        book.save(str(path))
        preview = preview_upload(path)
        self.assertEqual((preview.sheet_count, len(preview.rows)), (1, 1))
        self.assertEqual(preview.rows[0].management_id, '001245')
        self.assertEqual(preview.rows[0].start_date, '2025-01-02')
