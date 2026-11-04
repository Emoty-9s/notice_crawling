"""M15 offline presenter/data-flow contracts, independent of a GUI display."""

import copy
import json
import socket
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.core.models import GeminiResult, Notice
from src.local_client import matcher
from src.local_client.dashboard import (DashboardError, load_dashboard, notice_details, notice_rows,
                                        recommendation_details, recommendation_rows)
from src.local_client.performance import Performance, PerformanceStore
from src.local_client.ui import main
from src.renderer.feed import build_feed


STAMP = '2026-11-02T01:00:00Z'
PRIVATE = 'synthetic-private-marker'


class DashboardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='dashboard-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db_path = self.root/'performance.db'
        self.cache_path = self.root/'snapshot.json'
        self.store = PerformanceStore(self.db_path)
        self.related = Performance(
            performance_id='P001', project_name='반도체 IP-R&D 특허분석', year=2025,
            technical_field='반도체', work_type='특허분석', keywords=['반도체', 'IP-R&D', '특허분석'],
            client=PRIVATE, notes=PRIVATE, attorneys=[PRIVATE])
        self.store.create(self.related)
        self.store.create(Performance(performance_id='P002', project_name='건축 설계', year=2000))
        first = Notice(
            notice_id='N1', source_id='s1', institution='가상기관', title='반도체 IP-R&D 특허분석 협력기관 모집',
            content_text='특허분석 수행기관 모집', content_hash='hash', url='https://example.test/notice/1',
            first_seen_at=STAMP, last_seen_at=STAMP, updated_at=STAMP,
            gemini=GeminiResult(status='SUCCESS', analysis_policy='patent-firm-participation-v2', relevant=True, category='IP-R&D', participation_type='협력기관',
                                keywords=['반도체', 'IP-R&D', '특허분석'], reason='가상 선별 근거',
                                analyzed_at=STAMP, analyzed_content_hash='hash'))
        second = replace(first, notice_id='N2', source_id='s2', institution='다른기관', title='건축 설계 공고',
                         gemini=replace(first.gemini, category='건축', keywords=['건축']))
        self.snapshot = {'base_url': 'https://example.test/', 'feed': build_feed([first, second], generated_at=STAMP),
                         'metadata': {'schema_version': 2, 'generated_at': STAMP, 'notice_count': 2}}
        self.write_cache()
        for target in ('urllib.request.OpenerDirector.open', 'socket.create_connection',
                       'src.ai.gemini.GeminiClient.generate', 'src.local_client.sync.FeedClient.sync',
                       'src.local_client.performance.PerformanceStore.__init__'):
            blocker = patch(target, side_effect=AssertionError('forbidden UI side effect'))
            blocker.start()
            self.addCleanup(blocker.stop)
        self.data = load_dashboard(self.cache_path, self.db_path)

    def write_cache(self):
        self.cache_path.write_text(json.dumps(self.snapshot, ensure_ascii=False), encoding='utf-8')

    def recommendations(self, **kwargs):
        return recommendation_rows(self.data, 'N1', reference_year='2026', **kwargs)

    def test_notice_area_displays_all_required_fields_and_korean(self):
        notice = notice_rows(self.data)[0]
        details = notice_details(notice)
        for value in ('공고 ID: N1', notice['title'], 'category: IP-R&D', 'participation_type: 협력기관',
                      'keywords:', '반도체', 'summary:', notice['summary'], '가상 선별 근거', notice['url']):
            self.assertIn(value, details)

    def test_presenter_calls_public_matcher_with_explicit_inputs(self):
        with patch('src.local_client.dashboard.matcher.match_notice', wraps=matcher.match_notice) as match:
            rows = self.recommendations(top_n='1')
        self.assertEqual(len(rows), 1)
        match.assert_called_once_with(self.snapshot['feed']['notices'][0], self.data.performances, reference_year=2026, top_n=1)

    def test_ranking_project_name_and_total_score_are_displayed(self):
        row = self.recommendations()[0]
        self.assertEqual((row['ranking'], row['performance_id'], row['project_name'], row['total_score']),
                         (1, 'P001', self.related.project_name, 22))
        text = recommendation_details(row)
        for value in ('1위', 'P001', '반도체 IP-R&D 특허분석', 'total_score', '22점'):
            self.assertIn(value, text)

    def test_all_rule_names_points_and_evidence_are_displayed(self):
        text = recommendation_details(self.recommendations()[0])
        for value in ('technical_field', 'work_type', 'keyword', 'category', 'title', 'recent',
                      '+5점', '+6점', '+3점', '+2점', '+1점', '근거:', '반도체', 'ip-r&d', '2025'):
            self.assertIn(value, text)

    def test_total_score_equals_visible_rule_sum(self):
        row = self.recommendations()[0]
        self.assertEqual(row['total_score'], row['rule_total'])
        self.assertTrue(row['sum_matches'])
        self.assertEqual(row['rule_total'], sum(reason['points'] for reason in row['reasons']))
        self.assertIn('규칙별 합계: 22점 | 일치', recommendation_details(row))

    def test_inconsistent_matcher_result_is_visibly_marked_not_repaired(self):
        result = matcher.match_notice(self.snapshot['feed']['notices'][0], self.data.performances, reference_year=2026)[0]
        with patch('src.local_client.dashboard.matcher.match_notice', return_value=[replace(result, score=999)]):
            row = self.recommendations()[0]
        self.assertEqual(row['total_score'], 999)
        self.assertEqual(row['rule_total'], 22)
        self.assertFalse(row['sum_matches'])
        self.assertIn('불일치', recommendation_details(row))

    def test_top_n_default_custom_zero_and_larger_than_database(self):
        self.assertEqual(len(self.recommendations()), 2)
        self.assertEqual(len(self.recommendations(top_n='1')), 1)
        self.assertEqual(self.recommendations(top_n='0'), [])
        self.assertEqual(len(self.recommendations(top_n=100)), 2)

    def test_empty_database_has_no_recommendations(self):
        self.store.delete('P001')
        self.store.delete('P002')
        data = load_dashboard(self.cache_path, self.db_path)
        self.assertEqual(recommendation_rows(data, 'N1', reference_year=2026), [])

    def test_empty_feed_and_no_selection_are_handled(self):
        self.snapshot['feed']['notices'] = []
        self.snapshot['metadata']['notice_count'] = 0
        self.write_cache()
        data = load_dashboard(self.cache_path, self.db_path)
        self.assertEqual(notice_rows(data), [])
        with self.assertRaisesRegex(DashboardError, 'SELECT_NOTICE'):
            recommendation_rows(data, None, reference_year=2026)

    def test_invalid_year_is_not_replaced_with_current_date(self):
        for value in ('', 'today', '-1', '2026.0', 0, 10000, None, True, '２０２６'):
            with self.subTest(value=value), self.assertRaisesRegex(DashboardError, 'INVALID_REFERENCE_YEAR'):
                recommendation_rows(self.data, 'N1', reference_year=value)

    def test_invalid_top_n_and_unknown_notice_are_safe_errors(self):
        for value in ('', '-1', '1.0', None, True):
            with self.subTest(value=value), self.assertRaisesRegex(DashboardError, 'INVALID_TOP_N'):
                self.recommendations(top_n=value)
        with self.assertRaisesRegex(DashboardError, 'SELECT_NOTICE'):
            recommendation_rows(self.data, 'private-secret-id', reference_year=2026)

    def test_same_input_and_display_details_are_deterministic(self):
        first, second = self.recommendations(), self.recommendations()
        self.assertEqual(first, second)
        self.assertEqual(recommendation_details(first[0]), recommendation_details(second[0]))
        self.assertEqual(first, recommendation_rows(self.data, 'N1', reference_year=' 2026 '))

    def test_filters_search_korean_casefold_and_empty_results(self):
        self.assertEqual([row['notice_id'] for row in notice_rows(self.data, query='반도체')], ['N1'])
        self.assertEqual([row['notice_id'] for row in notice_rows(self.data, institution='다른기관')], ['N2'])
        self.assertEqual([row['notice_id'] for row in notice_rows(self.data, category='IP-R&D', query='ip-r&d')], ['N1'])
        self.assertEqual(notice_rows(self.data, query='없는 문구'), [])
        with self.assertRaises(DashboardError):
            notice_rows(self.data, query=None)

    def test_display_operations_never_mutate_original_inputs(self):
        before_snapshot, before_records = copy.deepcopy(self.data.snapshot), self.data.performances
        rows = notice_rows(self.data)
        rows[0]['title'] = 'display copy edit'
        rows[0]['keywords'].append('display only')
        result = self.recommendations()[0]
        result['reasons'][0]['terms'].append('display only')
        self.assertEqual(self.data.snapshot, before_snapshot)
        self.assertEqual(self.data.performances, before_records)

    def test_database_and_cache_bytes_unchanged_after_all_ui_data_operations(self):
        before_db, before_cache = self.db_path.read_bytes(), self.cache_path.read_bytes()
        for _ in range(2):
            data = load_dashboard(self.cache_path, self.db_path)
            notice_details(notice_rows(data)[0])
            rows = recommendation_rows(data, 'N1', reference_year=2026, top_n=1)
            recommendation_details(rows[0])
        self.assertEqual(self.db_path.read_bytes(), before_db)
        self.assertEqual(self.cache_path.read_bytes(), before_cache)

    def test_database_connection_is_read_only_and_contains_no_write_statements(self):
        connect = sqlite3.connect
        statements = []
        def readonly(*args, **kwargs):
            self.assertTrue(args[0].endswith('?mode=ro'))
            self.assertTrue(kwargs['uri'])
            connection = connect(*args, **kwargs)
            connection.set_trace_callback(statements.append)
            return connection
        with patch('src.local_client.dashboard.sqlite3.connect', side_effect=readonly):
            data = load_dashboard(self.cache_path, self.db_path)
        self.assertEqual(len(data.performances), 2)
        self.assertFalse(any(statement.upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'REPLACE'))
                             for statement in statements))

    def test_missing_database_is_not_created(self):
        missing = self.root/'absent'/'performance.db'
        with self.assertRaisesRegex(DashboardError, 'INVALID_OR_MISSING_DATABASE'):
            load_dashboard(self.cache_path, missing)
        self.assertFalse(missing.parent.exists())

    def test_missing_cache_is_not_created(self):
        missing = self.root/'absent'/'snapshot.json'
        with self.assertRaisesRegex(DashboardError, 'INVALID_OR_MISSING_CACHE'):
            load_dashboard(missing, self.db_path)
        self.assertFalse(missing.parent.exists())

    def test_corrupt_database_and_schema_error_are_not_empty_success(self):
        path = self.root/'corrupt.db'
        path.write_bytes(PRIVATE.encode())
        with self.assertRaises(DashboardError) as error:
            load_dashboard(self.cache_path, path)
        self.assertNotIn(PRIVATE, str(error.exception))
        self.assertEqual(path.read_bytes(), PRIVATE.encode())
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            connection.execute('PRAGMA user_version = 99')
        before = self.db_path.read_bytes()
        with self.assertRaises(DashboardError):
            load_dashboard(self.cache_path, self.db_path)
        self.assertEqual(self.db_path.read_bytes(), before)

    def test_malformed_and_unsupported_cache_is_not_rewritten(self):
        cases = [b'{', b'\xff', b'NaN', b'{"base_url":"a","base_url":"b"}']
        unsupported = copy.deepcopy(self.snapshot)
        unsupported['metadata']['schema_version'] = 99
        cases.append(json.dumps(unsupported).encode())
        mismatch = copy.deepcopy(self.snapshot)
        mismatch['metadata']['notice_count'] = 99
        cases.append(json.dumps(mismatch).encode())
        for raw in cases:
            self.cache_path.write_bytes(raw)
            with self.assertRaisesRegex(DashboardError, 'INVALID_OR_MISSING_CACHE'):
                load_dashboard(self.cache_path, self.db_path)
            self.assertEqual(self.cache_path.read_bytes(), raw)

    def test_zero_point_record_displays_no_bonus_and_matching_sum(self):
        row = self.recommendations()[1]
        self.assertEqual((row['total_score'], row['rule_total']), (0, 0))
        self.assertIn('적용된 가점 규칙 없음', recommendation_details(row))

    def test_display_payload_does_not_include_private_client_notes_or_attorneys(self):
        self.assertNotIn(PRIVATE, json.dumps(self.recommendations(), ensure_ascii=False))

    def test_untrusted_text_is_plain_text_not_html_or_code(self):
        notice = notice_rows(self.data)[0]
        notice['title'] = '<script>do_not_execute()</script>'
        self.assertIn(notice['title'], notice_details(notice))

    def test_ui_help_does_not_start_gui_or_load_files(self):
        import contextlib
        import io
        with patch('src.local_client.ui.DashboardWindow', side_effect=AssertionError('GUI forbidden')), \
             contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as exit_error:
            main(['--help'])
        self.assertEqual(exit_error.exception.code, 0)
        self.assertIn('--reference-year', output.getvalue())


if __name__ == '__main__':
    unittest.main()
