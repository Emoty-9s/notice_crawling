"""One authoritative field vocabulary; phrases may only be supporting evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from tests.test_enrichment import MODEL_READY, row
from src.local_client.technical_labels import allowed_technical_fields, selection, validate_row_fields
from src.local_client.enrichment import SemanticClassifier, set_user_value
from src.local_client.upload import UploadPreview
from src.local_client.upload_store import save_preview, load_enrichment_preview, save_enriched_preview
from src.local_client.upload_ui import UploadDialog


class ClosedLabels(unittest.TestCase):
    def test_original_twenty_plus_soboojang_only(self):
        fields = allowed_technical_fields()
        self.assertEqual(len(fields),21)
        self.assertEqual(len(set(fields)),21)
        self.assertIn('소부장',fields)
        for name in ('전기자동차','배터리팩','열관리','센서/광학','기타'):
            self.assertNotIn(name,fields)

    def test_user_selection_only_accepts_one_to_three_allowed_candidates(self):
        value = row()
        for invalid in ('전기자동차','열관리','센서/광학','반도체 · 배터리팩','소부장 · 반도체 · 소재 / 화학 · 전기 / 전자'):
            with self.assertRaises(ValueError):
                set_user_value(value,'technical_field',invalid)
        set_user_value(value,'technical_field','반도체 · 소부장')
        self.assertEqual([v['name'] for v in value.technical_fields],['반도체','소부장'])
        validate_row_fields(value)

    def test_preview_never_shows_title_phrases_as_fields(self):
        value = row('전기자동차 배터리팩 열관리')
        value.technical_field = '자동차 / 모빌리티'
        value.technical_fields = [{'name':'자동차 / 모빌리티'},{'name':'이차전지 / 에너지저장'},{'name':'소부장'}]
        value.technical_tags = [{'name':'열관리'},{'name':'배터리팩'}]
        self.assertEqual(UploadDialog._technical_display(value),'자동차 / 모빌리티 · 이차전지 / 에너지저장 · 소부장')

    def test_insert_and_reanalysis_boundaries_reject_outside_labels(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder)/'private.db'
            value = row()
            value.technical_field = '배터리팩'
            preview = UploadPreview('test.xlsx',1,[value],0,[],{})
            result = save_preview(path,preview)
            self.assertEqual(result.saved,0)
            self.assertEqual(result.failed,1)
            value.technical_field = '반도체'
            value.technical_fields = [{'name':'반도체'}]
            self.assertEqual(save_preview(path,preview).saved,1)
            loaded = load_enrichment_preview(path)
            loaded.rows[0].technical_fields.append({'name':'열관리'})
            self.assertEqual(save_enriched_preview(path,loaded).updated,0)
            self.assertEqual(load_enrichment_preview(path).rows[0].technical_field,'반도체')


@unittest.skipUnless(MODEL_READY,'offline model resources required')
class ClosedSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = SemanticClassifier()

    @classmethod
    def tearDownClass(cls):
        cls.model.close()

    def test_eight_requested_semantic_cases_and_max_three(self):
        cases = json.loads((Path(__file__).parent/'fixtures/performance_enrichment/closed_taxonomy.json').read_text(encoding='utf-8'))
        values = [row(c['title']) for c in cases]
        self.model.enrich(values)
        for case,value in zip(cases,values):
            with self.subTest(title=case['title']):
                names = {v['name'] for v in value.technical_fields}
                self.assertTrue(set(case['fields']) <= names)
                if case.get('only'):
                    self.assertEqual(names,set(case['fields']))
                self.assertLessEqual(len(names),3)
                self.assertTrue(names <= set(allowed_technical_fields()))
                validate_row_fields(value)

    def test_component_solo_and_device_does_not_mean_automatic_component(self):
        values = [row(v) for v in ('특수 너트 구조','방수시트 제조','금속 체결부품','정밀 가공 부품','범용 검사장치','MRI 진단 장치','태양광 모듈용 방수시트')]
        self.model.enrich(values)
        for value in values[:5]:
            self.assertEqual({v['name'] for v in value.technical_fields},{'소부장'},value.project_name)
        self.assertIn('의료 / 의료기기',{v['name'] for v in values[5].technical_fields})
        self.assertEqual({v['name'] for v in values[6].technical_fields},{'에너지 / 환경','소부장'})

    def test_unknown_original_field_is_normalized_without_losing_raw(self):
        value = row('전기자동차 배터리팩')
        value.technical_field = '열관리'
        value.field_sources['technical_field'] = 'excel_header'
        value.raw_source['columns']['기술분야'] = '열관리'
        self.model.enrich([value])
        validate_row_fields(value)
        self.assertEqual(value.raw_source['columns']['기술분야'],'열관리')
