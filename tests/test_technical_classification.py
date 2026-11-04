"""Offline phrase/broad/tag regressions. Fixtures contain no company records."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_enrichment import MODEL_READY, row
from src.local_client.enrichment import SemanticClassifier, enrich_rows, set_user_value
from src.local_client.technical_classifier import extract_phrases, clean_subject
from src.local_client.upload import UploadPreview
from src.local_client.upload_store import load_enrichment_preview, save_preview, save_enriched_preview


class LocalPhraseExtraction(unittest.TestCase):
    def test_independent_title_phrases_not_one_whole_sentence(self):
        phrases = extract_phrases('전기자동차 배터리팩 열관리 시스템 특허동향조사')
        self.assertIn('전기자동차', phrases)
        self.assertIn('배터리팩', phrases)
        self.assertIn('열관리', phrases)
        self.assertNotIn('특허동향조사', phrases)
        self.assertNotIn('시스템', phrases)

    def test_unseen_detail_phrase_is_kept_without_taxonomy_entry(self):
        self.assertIn('OLED', extract_phrases('OLED 증착장비'))
        self.assertIn('LiDAR', extract_phrases('자율주행 LiDAR 센서'))
        self.assertEqual(clean_subject('특허동향조사 IP-R&D 선행기술조사'), '')


@unittest.skipUnless(MODEL_READY, 'optional local model resources')
class OfflineMultilabel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classifier = SemanticClassifier()

    @classmethod
    def tearDownClass(cls):
        cls.classifier.close()

    def setUp(self):
        for target in ('socket.create_connection', 'urllib.request.OpenerDirector.open',
                       'src.ai.gemini.GeminiClient.generate'):
            guard = patch(target, side_effect=AssertionError('EXTERNAL_CALL_FORBIDDEN'))
            guard.start()
            self.addCleanup(guard.stop)

    def analyze(self, values, **kwargs):
        self.classifier.enrich(values, **kwargs)
        return values

    def test_six_user_requested_multifield_regressions(self):
        cases = json.loads((Path(__file__).parent/'fixtures/performance_enrichment/multilabel.json').read_text(encoding='utf-8'))
        values = self.analyze([row(c['title']) for c in cases])
        for case, value in zip(cases, values):
            with self.subTest(title=case['title']):
                self.assertTrue(set(case['fields']) <= {v['name'] for v in value.technical_fields})
                self.assertTrue(set(case['tags']) <= {v['name'] for v in value.technical_tags})
                self.assertLessEqual(len(value.technical_fields), 3)
                self.assertLessEqual(len(value.technical_tags), 3)
                self.assertNotEqual(value.technical_field, '미분류')
                self.assertNotEqual(value.ai_evidence['technical_field'].get('reason'), 'LOW_MARGIN')
                if case.get('work'):
                    self.assertEqual(value.work_type, case['work'])

    def test_close_categories_are_accepted_without_margin_veto(self):
        value = self.analyze([row('전기자동차 배터리팩')])[0]
        evidence = value.ai_evidence['technical_field']
        self.assertLess(evidence['margin'], .01)
        self.assertTrue(evidence['accepted'])
        self.assertEqual(len(value.technical_fields), 2)

    def test_clear_title_not_diluted_by_administrative_description(self):
        value = row('전기자동차 배터리팩')
        value.description = '회의 일정 안내 서류 작성 출장 경비 정산 ' * 80
        self.analyze([value])
        self.assertEqual({v['name'] for v in value.technical_fields}, {'자동차 / 모빌리티','이차전지 / 에너지저장'})

    def test_nontechnical_or_missing_text_stays_unknown(self):
        values = self.analyze([row(t) for t in ('안녕하세요 감사합니다', '회의 일정과 출장 정산 안내', '서류 정리', '')])
        for value in values:
            self.assertEqual(value.technical_field, '미분류')
            self.assertEqual(value.technical_fields, [])
            self.assertEqual(value.technical_tags, [])
            self.assertIn(value.ai_evidence['technical_field']['reason'], ('NO_TEXT','LOW_SCORE','NO_LABEL_MATCH'))

    def test_industry_manufacturing_does_not_invent_food_category(self):
        value = self.analyze([row('반도체 웨이퍼 제조 공정 특허 분석')])[0]
        self.assertNotIn('식품 / 농업', {v['name'] for v in value.technical_fields})

    def test_two_letter_ai_is_a_meaningful_technical_title(self):
        value = self.analyze([row('AI')])[0]
        self.assertEqual(value.technical_field, 'AI / 소프트웨어')

    def test_user_and_excel_values_remain_untouched_even_on_force(self):
        for source in ('user', 'excel_header', 'header_alias', 'legacy_explicit'):
            value = row('AI 기반 의료영상 분석')
            value.technical_field = '통신 / 네트워크'
            value.field_sources['technical_field'] = source
            value.technical_tags = [{'name':'원본 태그','source':source}]
            self.analyze([value], force=True)
            self.assertEqual(value.technical_field, '통신 / 네트워크')
            self.assertEqual(value.technical_tags, [{'name':'원본 태그','source':source}])

    def test_no_extract_fields_are_hallucinated_and_raw_is_immutable(self):
        value = row('자율주행 LiDAR 센서')
        before = copy.deepcopy(value.raw_source)
        self.analyze([value])
        self.assertEqual(value.raw_source, before)
        for name in ('management_id','client','start_date','end_date','year','amount'):
            self.assertIsNone(getattr(value, name))

    def test_broad_and_tags_survive_save_reload_and_reanalysis(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder)/'private.db'
            value = self.analyze([row('전기자동차 배터리팩')])[0]
            preview = UploadPreview('synthetic.xlsx',1,[value],0,[],{})
            self.assertEqual(save_preview(path,preview).saved,1)
            loaded = load_enrichment_preview(path)
            self.assertEqual(loaded.rows[0].technical_fields, value.technical_fields)
            self.assertEqual(loaded.rows[0].technical_tags, value.technical_tags)
            self.analyze(loaded.rows, force=True)
            self.assertEqual(save_enriched_preview(path,loaded).updated,1)
            again = load_enrichment_preview(path)
            self.assertEqual([v['name'] for v in again.rows[0].technical_tags][:2], ['전기자동차','배터리'])
            set_user_value(again.rows[0], 'technical_field', '통신 / 네트워크 · 소부장')
            self.assertEqual(save_enriched_preview(path,again).updated,1)
            protected = load_enrichment_preview(path)
            self.analyze(protected.rows,force=True)
            self.assertEqual(protected.rows[0].technical_field,'통신 / 네트워크')

    def test_legacy_literal_unknown_can_be_filled_but_user_unknown_cannot(self):
        from src.local_client.performance import Performance, PerformanceStore
        from src.local_client.enrichment import prepare_existing
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            database = Path(folder)/'legacy.db'
            store = PerformanceStore(database)
            store.create(Performance(performance_id='legacy', project_name='전기자동차 배터리팩', technical_field='미분류', keywords=('수동 키워드',)))
            preview = prepare_existing(database)
            self.assertEqual(preview.analysis_stats['explicit_field_changes'],0)
            self.assertEqual(preview.rows[0].technical_field,'자동차 / 모빌리티')
            self.assertEqual(save_enriched_preview(database,preview).updated,1)
            self.assertEqual(store.get('legacy').technical_field,'자동차 / 모빌리티')
            self.assertIn('수동 키워드',store.get('legacy').keywords)
            self.assertIn('배터리',store.get('legacy').keywords)
            self.assertIn('이차전지',store.get('legacy').keywords)
            protected = load_enrichment_preview(database)
            set_user_value(protected.rows[0],'technical_field','미분류')
            self.assertEqual(save_enriched_preview(database,protected).updated,1)
            again = prepare_existing(database,force=True)
            self.assertEqual(again.rows[0].technical_field,'미분류')
            self.assertEqual(again.rows[0].field_sources['technical_field'],'user')

    def test_private_diagnostic_prints_only_counts_and_default_is_readonly(self):
        from tools.diagnose_performance_fields import diagnose
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            database = Path(folder)/'private.db'
            preview = UploadPreview('private.xlsx',1,[row('전기자동차 배터리팩')],0,[],{})
            save_preview(database,preview)
            before = database.read_bytes()
            summary, private = diagnose(database)
            self.assertEqual(summary['before_unclassified'],1)
            self.assertEqual(summary['after_unclassified'],0)
            self.assertEqual(summary['newly_classified'],1)
            self.assertNotIn('전기자동차',json.dumps(summary,ensure_ascii=False))
            self.assertEqual(database.read_bytes(),before)
            self.assertEqual(private[0]['project_name'],'전기자동차 배터리팩')
            self.assertEqual(len(private[0]['legacy_top5']),5)
            self.assertEqual(summary['external_calls'],0)
