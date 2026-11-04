"""Local AI safeguards, provenance, migration and real offline ONNX checks."""
import copy
import importlib.util
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from src.local_client.upload import UploadRow, preview_upload
from src.local_client.enrichment import (MODEL_FIELDS, can_infer, enrich_rows, keyword_candidates,
                                         set_user_value, SemanticClassifier)
from src.local_client.local_model import LocalEncoder, ModelError, model_directory
from src.local_client.upload_store import (save_preview, save_enriched_preview, load_enrichment_preview,
                                           restore_saved_enrichment)
from src.local_client.performance import Performance, PerformanceStore


def row(text='반도체 웨이퍼 제조 공정 특허 분석'):
    return UploadRow('실적', 2, None, text, None, None, None, None, '', '', text, (), None,
                     {'columns': {'사업명': text}}, text, text, 'synthetic-only', [],
                     field_sources={'project_name':'excel_header', 'technical_field':'unknown', 'work_type':'unknown', 'keywords':'unknown'})


class EnrichmentGuards(unittest.TestCase):
    def test_explicit_ev_battery_tags_do_not_depend_on_model_margin(self):
        for title in ('전기자동차 배터리팩', '전기자동차배터리팩 특허동향조사', 'EV battery pack'):
            with self.subTest(title=title):
                value = row(title)
                enrich_rows([value], encoder_factory=Mock(side_effect=ModelError('OFFLINE_MODEL_FAILURE')))
                self.assertEqual(value.technical_field, '자동차 / 모빌리티')
                self.assertEqual([v['name'] for v in value.technical_fields], ['자동차 / 모빌리티', '이차전지 / 에너지저장'])
                self.assertEqual([v['name'] for v in value.technical_tags], ['전기자동차', '배터리'])
                self.assertEqual(value.field_sources['technical_field'], 'deterministic_mapping')
                self.assertIsNone(value.field_confidence['technical_field'])
                self.assertIn('배터리', value.searchable_text)

    def test_tag_order_follows_source_and_english_alias_has_boundaries(self):
        value = row('배터리팩 전기자동차 적용')
        enrich_rows([value], encoder_factory=Mock(side_effect=ModelError('UNAVAILABLE')))
        self.assertEqual([v['name'] for v in value.technical_tags], ['배터리', '전기자동차'])
        other = row('review meeting overview')
        enrich_rows([other], encoder_factory=Mock(side_effect=ModelError('UNAVAILABLE')))
        self.assertEqual(other.technical_field, '미분류')
        self.assertEqual(other.technical_fields, [])

    def test_explicit_tag_mapping_protects_user_and_excel_fields(self):
        for source in ('user', 'excel_header', 'header_alias', 'legacy_explicit'):
            value = row('전기자동차 배터리팩')
            value.technical_field = '전기 / 전자'
            value.field_sources['technical_field'] = source
            enrich_rows([value], force=True, encoder_factory=Mock(side_effect=ModelError('UNAVAILABLE')))
            self.assertEqual(value.technical_field, '전기 / 전자')

    def test_user_can_replace_multiple_tags_without_stale_ai_tags(self):
        value = row('전기자동차 배터리팩')
        enrich_rows([value], encoder_factory=Mock(side_effect=ModelError('UNAVAILABLE')))
        set_user_value(value, 'technical_field', '반도체 · AI / 소프트웨어')
        self.assertEqual(value.technical_field, '반도체')
        self.assertEqual([v['name'] for v in value.technical_fields], ['반도체', 'AI / 소프트웨어'])
        self.assertNotIn('technical_field', value.ai_evidence)

    def test_preview_values_have_only_requested_columns_and_all_tags(self):
        from src.local_client.upload_ui import UploadDialog
        value = row('전기자동차 배터리팩')
        value.year, value.management_id = 2026, '001245'
        enrich_rows([value], encoder_factory=Mock(side_effect=ModelError('UNAVAILABLE')))
        from src.local_client.preview_selection import PreviewSelection
        dialog = UploadDialog.__new__(UploadDialog)
        dialog.selection = PreviewSelection(5)
        values = dialog._row_values(value, 4)
        self.assertEqual(values, ('☑',5, 2026, '001245', '전기자동차 배터리팩', '', '자동차 / 모빌리티 · 이차전지 / 에너지저장', '미분류'))

    def test_only_four_fields_are_model_writable(self):
        value = row()
        for name in ('management_id', 'client', 'start_date', 'end_date', 'year', 'amount', 'raw_source', 'description'):
            self.assertFalse(can_infer(value, name, True))
        self.assertEqual(MODEL_FIELDS, {'project_name', 'technical_field', 'work_type', 'keywords'})

    def test_explicit_and_user_values_win_even_on_force(self):
        value = row()
        for source in ('user', 'excel_header', 'header_alias', 'deterministic_parser', 'legacy_explicit'):
            value.technical_field = '원본 기술'
            value.field_sources['technical_field'] = source
            self.assertFalse(can_infer(value, 'technical_field', True))
        value.technical_field = '미분류'
        value.field_sources['technical_field'] = 'excel_header'
        self.assertFalse(can_infer(value, 'technical_field', True))

    def test_existing_model_value_only_reanalyzes_on_explicit_force(self):
        value = row()
        value.technical_field = '반도체'
        value.field_sources['technical_field'] = 'local_model'
        self.assertFalse(can_infer(value, 'technical_field'))
        self.assertTrue(can_infer(value, 'technical_field', True))

    def test_short_explicit_title_is_never_replaced(self):
        value = row('A')
        self.assertFalse(can_infer(value, 'project_name', True))
        factory = Mock(side_effect=AssertionError('short row should not load model'))
        enrich_rows([value], encoder_factory=factory)
        self.assertEqual(value.project_name, 'A')
        factory.assert_not_called()

    def test_user_edit_keeps_raw_and_is_not_a_fake_probability(self):
        value = row()
        original = copy.deepcopy(value.raw_source)
        set_user_value(value, 'technical_field', '의료 / 의료기기')
        self.assertEqual(value.field_sources['technical_field'], 'user')
        self.assertIsNone(value.field_confidence['technical_field'])
        self.assertEqual(value.raw_source, original)

    def test_no_meaningful_text_does_not_load_model(self):
        value = row('')
        value.project_name = None
        value.management_id = 'PRJ-001'
        factory = Mock(side_effect=AssertionError('must stay unloaded'))
        self.assertIsNone(enrich_rows([value], encoder_factory=factory))
        factory.assert_not_called()
        self.assertEqual(value.technical_field, '미분류')

    def test_failure_falls_back_without_partial_inferences_or_hallucinations(self):
        value = row()
        original = copy.deepcopy(value)
        factory = Mock(side_effect=ModelError('LOCAL_MODEL_UNAVAILABLE'))
        warning = enrich_rows([value], encoder_factory=factory)
        self.assertIn('로컬 분석 모델을 사용할 수 없어', warning)
        for name in ('management_id', 'client', 'start_date', 'end_date', 'year', 'amount', 'raw_source'):
            self.assertEqual(getattr(value, name), getattr(original, name))
        self.assertEqual(value.technical_field, '미분류')

    def test_failed_batch_does_not_leave_a_partial_ai_result(self):
        value = row()
        encoder = Mock()
        with patch('src.local_client.enrichment.SemanticClassifier') as classifier:
            def fail(values, **kwargs):
                values[0].technical_field = '부분 결과'
                raise ModelError('LOCAL_INFERENCE_FAILED')
            classifier.return_value.enrich.side_effect = fail
            enrich_rows([value], encoder_factory=lambda: encoder)
        self.assertEqual(value.technical_field, '미분류')
        classifier.return_value.close.assert_called_once()

    def test_keyword_candidates_exclude_ids_dates_and_amounts(self):
        values = keyword_candidates('PRJ-2026-001 2026년 5월 1000만원 반도체 AI 바이오 분석')
        self.assertNotIn('PRJ-2026-001', values)
        self.assertNotIn('1000만원', values)
        self.assertNotIn('2026년', values)
        self.assertIn('반도체', values)

    def test_pre_cancelled_job_does_not_load_model_or_change_original(self):
        value = row()
        original = copy.deepcopy(value)
        event = threading.Event()
        event.set()
        factory = Mock(side_effect=AssertionError('model should stay unloaded'))
        with self.assertRaisesRegex(ModelError, 'CANCELLED'):
            enrich_rows([value], encoder_factory=factory, cancel=event)
        factory.assert_not_called()
        self.assertEqual(value, original)


MODEL_READY = (importlib.util.find_spec('onnxruntime') is not None
               and importlib.util.find_spec('tokenizers') is not None
               and (model_directory()/'model.onnx').is_file())


@unittest.skipUnless(MODEL_READY, 'build-time model resources are not available in stdlib-only central CI')
class RealOfflineEnrichment(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='local-model-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root/'private.db'
        for target in ('urllib.request.OpenerDirector.open', 'socket.create_connection',
                       'src.ai.gemini.GeminiClient.generate', 'src.local_client.sync.FeedClient.sync'):
            guard = patch(target, side_effect=AssertionError('external call forbidden'))
            guard.start()
            self.addCleanup(guard.stop)

    def workbook(self, explicit=False):
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.append(['관리번호', '사업명', '고객사', '수행년도', '기술분야', '업무유형', '주요업무', '금액'])
        sheet.append(['001245', '반도체 웨이퍼 제조 공정 특허 분석', None, None,
                      '전기 / 전자' if explicit else None, '원본 업무' if explicit else None,
                      '메모리 반도체 제조 장비에 대한 특허동향 분석', None])
        path = self.root/'upload.xlsx'
        book.save(path)
        book.close()
        return path

    def test_real_cpu_inference_and_provenance_while_http_is_blocked(self):
        value = row()
        raw = copy.deepcopy(value.raw_source)
        self.assertIsNone(enrich_rows([value]))
        self.assertEqual(value.technical_field, '반도체')
        self.assertEqual(value.field_sources['technical_field'], 'local_model')
        self.assertGreater(value.field_confidence['technical_field'], .79)
        self.assertIn('margin', value.ai_evidence['technical_field'])
        self.assertTrue(value.ai_model_version.startswith('intfloat/multilingual-e5-small@'))
        self.assertEqual(value.raw_source, raw)
        self.assertEqual(LocalEncoder.active_sessions, 0)

    def test_protected_extract_fields_remain_absent_hallucinations_zero(self):
        values = [row('AI based clinical image diagnosis patent analysis'), row('항체 신약 특허 분석')]
        enrich_rows(values)
        for value in values:
            for field in ('management_id', 'client', 'start_date', 'end_date', 'year', 'amount'):
                self.assertIsNone(getattr(value, field))

    def test_explicit_original_technology_and_work_are_not_overwritten(self):
        preview = preview_upload(self.workbook(explicit=True))
        original = copy.deepcopy(preview.rows[0])
        enrich_rows(preview.rows, force=True)
        self.assertEqual(preview.rows[0].technical_field, '전기 / 전자')
        self.assertEqual(preview.rows[0].work_type, '원본 업무')
        self.assertEqual(preview.rows[0].project_name, original.project_name)
        self.assertEqual(preview.rows[0].raw_source, original.raw_source)

    def test_keywords_are_extractive_capped_and_deduplicated(self):
        value = row('AI 인공지능 반도체 웨이퍼 특허동향 분석 프로젝트')
        enrich_rows([value])
        self.assertGreater(len(value.keywords), 0)
        self.assertLessEqual(len(value.keywords), 15)
        self.assertEqual(len(value.keywords), len(set(value.keywords)))
        self.assertTrue(all(word in value.match_text for word in value.keywords))

    def test_ambiguous_and_incomplete_rows_abstain(self):
        values = [row('안녕하세요 감사합니다'), row('회의 일정과 출장 정산 안내')]
        enrich_rows(values)
        self.assertTrue(all(v.technical_field == '미분류' and v.work_type == '미분류' and v.review_required for v in values))

    def test_multiple_technical_fields_are_preserved(self):
        value = row('AI enabled medical imaging diagnosis 특허 분석')
        enrich_rows([value])
        self.assertGreaterEqual(len(value.technical_fields), 2)

    def test_ev_battery_tags_persist_reanalysis_and_reach_matcher(self):
        value = row('전기자동차 배터리팩 특허동향조사')
        enrich_rows([value])
        # Reuse a parsed preview so storage fields/mappings follow production.
        preview = preview_upload(self.workbook())
        preview.rows[:] = [value]
        raw = copy.deepcopy(value.raw_source)
        self.assertEqual(save_preview(self.db, preview).saved, 1)
        loaded = load_enrichment_preview(self.db)
        enrich_rows(loaded.rows, force=True)
        self.assertEqual([v['name'] for v in loaded.rows[0].technical_fields], ['자동차 / 모빌리티', '이차전지 / 에너지저장'])
        self.assertEqual([v['name'] for v in loaded.rows[0].technical_tags][:2], ['전기자동차', '배터리'])
        self.assertEqual(loaded.rows[0].raw_source, raw)
        record = PerformanceStore(self.db).search()[0]
        self.assertEqual(record.technical_field, '자동차 / 모빌리티')
        for keyword in ('전기자동차', '배터리', '자동차', '이차전지'):
            self.assertIn(keyword, record.keywords)

    def test_preview_save_and_migration_never_modify_raw_source(self):
        preview = preview_upload(self.workbook())
        save_preview(self.db, preview)  # Simulate previously uploaded, empty AI fields.
        with closing(sqlite3.connect(self.db)) as conn:
            before = conn.execute('SELECT raw_source FROM performance_uploads_v1').fetchone()[0]
        pending = load_enrichment_preview(self.db)
        enrich_rows(pending.rows)
        result = save_enriched_preview(self.db, pending)
        self.assertEqual(result.updated, 1)
        self.assertEqual(PerformanceStore(self.db).search()[0].technical_field, '반도체')
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('SELECT raw_source FROM performance_uploads_v1').fetchone()[0], before)
            meta = json.loads(conn.execute('SELECT data FROM performance_enrichment_v1').fetchone()[0])
        self.assertEqual(meta['field_sources']['technical_field'], 'local_model')

    def test_user_override_survives_save_restart_force_reanalysis_and_reupload(self):
        path = self.workbook()
        preview = preview_upload(path)
        enrich_rows(preview.rows)
        set_user_value(preview.rows[0], 'technical_field', '통신 / 네트워크')
        set_user_value(preview.rows[0], 'work_type', '사용자 선택 업무')
        save_preview(self.db, preview)
        pending = load_enrichment_preview(self.db)
        enrich_rows(pending.rows, force=True)
        self.assertEqual(pending.rows[0].technical_field, '통신 / 네트워크')
        save_enriched_preview(self.db, pending)
        self.assertEqual(PerformanceStore(self.db).search()[0].work_type, '사용자 선택 업무')
        again = preview_upload(path)
        restore_saved_enrichment(again, self.db)
        self.assertEqual(again.rows[0].technical_field, '통신 / 네트워크')
        self.assertEqual(again.rows[0].field_sources['technical_field'], 'user')

    def test_reimport_uses_saved_model_results_without_loading_again(self):
        path = self.workbook()
        preview = preview_upload(path)
        enrich_rows(preview.rows)
        # Lock ambiguous/missing outputs so this case isolates cached analysis.
        for name in ('technical_field', 'work_type'):
            if getattr(preview.rows[0], name) == '미분류':
                set_user_value(preview.rows[0], name, '반도체' if name == 'technical_field' else '사용자 확인 값')
        save_preview(self.db, preview)
        again = preview_upload(path)
        restore_saved_enrichment(again, self.db)
        factory = Mock(side_effect=AssertionError('cached results must not be re-inferred'))
        enrich_rows(again.rows, encoder_factory=factory)
        factory.assert_not_called()

    def test_user_override_on_duplicate_is_saved_and_protected(self):
        path = self.workbook()
        original = preview_upload(path)
        save_preview(self.db, original)
        again = preview_upload(path)
        set_user_value(again.rows[0], 'technical_field', '통신 / 네트워크')
        result = save_preview(self.db, again)
        self.assertEqual((result.duplicates, result.updated), (1, 1))
        loaded = load_enrichment_preview(self.db)
        self.assertEqual(loaded.rows[0].technical_field, '통신 / 네트워크')
        self.assertEqual(loaded.rows[0].field_sources['technical_field'], 'user')

    def test_cached_user_value_is_not_silently_written_back_on_duplicate(self):
        path = self.workbook()
        original = preview_upload(path)
        set_user_value(original.rows[0], 'technical_field', '반도체')
        save_preview(self.db, original)
        again = preview_upload(path)
        restore_saved_enrichment(again, self.db)
        store = PerformanceStore(self.db)
        record = store.search()[0]
        store.update(replace(record, technical_field='이후 수정 값'))
        result = save_preview(self.db, again)
        self.assertEqual(result.updated, 0)
        self.assertEqual(store.get(record.performance_id).technical_field, '이후 수정 값')

    def test_enrichment_improves_existing_matcher_inputs_without_new_rules(self):
        from src.local_client.matcher import match_notice
        from src.local_client.dashboard import _load_performances
        preview = preview_upload(self.workbook())
        save_preview(self.db, preview)
        notice = dict(category='IP-R&D', participation_type='협력기관', title='반도체 특허 분석',
                      summary='반도체 분석 업무', keywords=['반도체', '특허분석'])
        before = match_notice(notice, _load_performances(self.db), reference_year=2026)[0]
        pending = load_enrichment_preview(self.db)
        enrich_rows(pending.rows)
        save_enriched_preview(self.db, pending)
        after = match_notice(notice, _load_performances(self.db), reference_year=2026)[0]
        self.assertGreater(after.score, before.score)
        self.assertEqual(after.score, sum(reason.points for reason in after.reasons))

    def test_legacy_nonempty_fields_are_preserved(self):
        store = PerformanceStore(self.db)
        store.create(Performance(performance_id='legacy', project_name='반도체 웨이퍼 특허 분석',
                                 technical_field='통신 / 네트워크', description='메모리 반도체 특허 분석'))
        preview = load_enrichment_preview(self.db)
        enrich_rows(preview.rows, force=True)
        save_enriched_preview(self.db, preview)
        self.assertEqual(store.get('legacy').technical_field, '통신 / 네트워크')

    def test_legacy_title_only_row_uses_project_name_for_enrichment(self):
        store = PerformanceStore(self.db)
        store.create(Performance(performance_id='legacy-title', project_name='메모리 반도체 웨이퍼 제조 공정 특허 분석'))
        pending = load_enrichment_preview(self.db)
        enrich_rows(pending.rows)
        save_enriched_preview(self.db, pending)
        self.assertEqual(store.get('legacy-title').technical_field, '반도체')

    def test_concurrent_edit_blocks_stale_reanalysis(self):
        store = PerformanceStore(self.db)
        store.create(Performance(performance_id='legacy', project_name='반도체 특허 분석'))
        pending = load_enrichment_preview(self.db)
        store.update(replace(store.get('legacy'), technical_field='다른 창에서 사용자 수정'))
        enrich_rows(pending.rows)
        result = save_enriched_preview(self.db, pending)
        self.assertEqual(result.failed, 1)
        self.assertEqual(store.get('legacy').technical_field, '다른 창에서 사용자 수정')

    def test_model_integrity_failure_is_local_fallback(self):
        directory = self.root/'invalid-model'
        directory.mkdir()
        (directory/'manifest.json').write_text('{"license":"mit","artifacts":{}}')
        value = row()
        warning = enrich_rows([value], encoder_factory=lambda: LocalEncoder(directory))
        self.assertIn('로컬 분석 모델을 사용할 수 없어', warning)
        self.assertEqual(LocalEncoder.active_sessions, 0)
