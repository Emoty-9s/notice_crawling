"""Local selection/CRUD integrity and matcher integration, no real company rows."""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dataclasses import replace
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock

from src.local_client.upload import UploadPreview
from src.local_client.preview_selection import PreviewSelection, save_selected
from src.local_client.upload_store import load_enrichment_preview
from src.local_client.performance_management import PerformanceManagement, technical_names
from src.local_client.performance import PerformanceStore, Performance, PerformanceError
from src.local_client.matcher import match_notice
from tests.test_enrichment import row


class SelectionAndManagement(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)/'local.db'
        self.service = PerformanceManagement(self.path)
        values = []
        for i in range(5):
            value = row(f'전기자동차 배터리 {i+1}')
            value.management_id,value.year,value.client = f'{i+1:04d}',2025,'합성 고객'
            value.fingerprint = f'selection-fixture-{i}'
            value.technical_field,value.work_type = '자동차 / 모빌리티','특허분석'
            value.technical_fields = [{'name':'자동차 / 모빌리티','source':'excel_header'}]
            value.field_sources.update(technical_field='excel_header',work_type='excel_header')
            values.append(value)
        self.preview = UploadPreview('fixture.xlsx',1,values,0,[],{})
        for name in ('urllib.request.OpenerDirector.open','socket.create_connection','src.ai.gemini.GeminiClient.generate'):
            guard = patch(name,side_effect=AssertionError('NO_EXTERNAL_CALLS'))
            guard.start()
            self.addCleanup(guard.stop)

    def save(self):
        return save_selected(self.path,self.preview,set(range(5)))

    def change(self,value,**overrides):
        data = dict(year=value.year,management_id=value.management_id,project_name=value.project_name,
                    client=value.client or '',technical_fields=technical_names(value),work_type=value.work_type or '미분류')
        data.update(overrides)
        return self.service.update(value,**data)

    def test_default_all_toggle_clear_invert_and_selected_three_of_five(self):
        state = PreviewSelection(5)
        self.assertEqual(state.checked,set(range(5)))
        state.toggle(1)
        state.toggle(3)
        result = save_selected(self.path,self.preview,state.checked)
        self.assertEqual((result.selected,result.excluded_by_user,result.saved,result.failed),(3,2,3,0))
        self.assertEqual({r.management_id for r in self.service.list()},{'0001','0003','0005'})
        state.set_all(False)
        self.assertEqual(state.checked,set())
        state.invert()
        self.assertEqual(state.checked,set(range(5)))
        state.set_all(True)
        self.assertEqual(len(state.checked),5)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            self.assertNotIn('selected',[v[1] for v in connection.execute('PRAGMA table_info(performances)')])
            self.assertNotIn('selected',connection.execute('SELECT data FROM performance_enrichment_v1 LIMIT 1').fetchone()[0])

    def test_no_selection_does_not_create_or_change_database(self):
        from src.local_client.upload import UploadError
        with self.assertRaises(UploadError):
            save_selected(self.path,self.preview,set())
        self.assertFalse(self.path.exists())
        self.save()
        before = self.path.read_bytes()
        with self.assertRaises(UploadError):
            save_selected(self.path,self.preview,set())
        self.assertEqual(self.path.read_bytes(),before)

    def test_selection_only_updates_checked_reanalysis_row(self):
        from src.local_client.enrichment import set_user_value
        self.save()
        pending = load_enrichment_preview(self.path)
        for value in pending.rows:
            set_user_value(value,'technical_field','이차전지 / 에너지저장')
        result = save_selected(self.path,pending,{0,2},existing=True)
        self.assertEqual((result.updated,result.excluded_by_user,result.failed),(2,3,0))
        self.assertEqual(sum(r.technical_field == '이차전지 / 에너지저장' for r in self.service.list()),2)

    def test_empty_list_read_only_search_order_and_refresh_after_upload(self):
        self.assertEqual(self.service.list(),[])
        self.assertFalse(self.path.exists())
        self.save()
        self.assertEqual(len(self.service.list()),5)
        self.assertEqual(len(self.service.list('배터리')),5)
        self.assertEqual([r.management_id for r in self.service.list('0003')],['0003'])
        value = self.service.list()[2]
        self.change(value,year=2029)
        self.assertEqual(self.service.list()[0].performance_id,value.performance_id)

    def test_six_fields_user_provenance_identity_raw_and_leading_zero(self):
        self.save()
        before = self.service.list()[0]
        raw = copy.deepcopy(before.raw_source)
        edited = self.change(before,year=2028,management_id='000007/PRJ-02',project_name='수정된 배터리 실적',
                             client='수정 고객',technical_fields=['자동차 / 모빌리티','이차전지 / 에너지저장'],work_type='기술사업화')
        self.assertEqual(edited.performance_id,before.performance_id)
        self.assertEqual(edited.management_id,'000007/PRJ-02')
        self.assertEqual(technical_names(edited),['자동차 / 모빌리티','이차전지 / 에너지저장'])
        self.assertEqual(edited.raw_source,raw)
        for name in ('year','management_id','project_name','client','technical_field','work_type'):
            self.assertEqual(edited.field_sources[name],'user')
        from src.local_client.enrichment import can_infer
        for name in ('project_name','technical_field','work_type'):
            self.assertFalse(can_infer(edited,name,True))
        with closing(sqlite3.connect(self.path)) as connection, connection:
            saved = connection.execute('SELECT management_id,normalized FROM performance_uploads_v1 WHERE performance_id=?',(before.performance_id,)).fetchone()
            self.assertEqual(saved[0],'000007/PRJ-02')
            self.assertEqual(json.loads(saved[1])['project_name'],'수정된 배터리 실적')

    def test_invalid_taxonomy_work_type_year_do_not_write(self):
        self.save()
        original = self.service.list()[0]
        for values in ({'technical_fields':['배터리팩']},{'technical_fields':['소부장','반도체','전기 / 전자','소재 / 화학']},
                       {'work_type':'새로운 임의 업무'},{'year':True},{'project_name':''},{'management_id':123}):
            with self.assertRaises(ValueError):
                self.change(original,**values)
        self.assertEqual(self.service.get(original.performance_id).base_revision,original.base_revision)

    def test_edit_changes_matcher_inputs_without_changing_scoring(self):
        self.save()
        original = self.service.list()[0]
        notice = dict(title='이차전지',summary='',keywords=[],category='이차전지 / 에너지저장',participation_type='')
        before = match_notice(notice,[PerformanceStore(self.path).get(original.performance_id)],reference_year=2025)[0]
        self.change(original,technical_fields=['이차전지 / 에너지저장'])
        after = match_notice(notice,[PerformanceStore(self.path).get(original.performance_id)],reference_year=2025)[0]
        self.assertGreater(after.score,before.score)
        self.assertEqual(after.score,sum(r.points for r in after.reasons))

    def test_delete_multiple_cleans_both_metadata_tables_and_persists(self):
        self.save()
        targets = self.service.list()[:2]
        self.assertEqual(self.service.delete(targets),2)
        self.assertEqual(len(PerformanceManagement(self.path).list()),3)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            for table in ('performances','performance_uploads_v1','performance_enrichment_v1'):
                self.assertEqual(connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0],3)
                for value in targets:
                    self.assertEqual(connection.execute(f'SELECT count(*) FROM {table} WHERE performance_id=?',(value.performance_id,)).fetchone()[0],0)

    def test_delete_failure_rolls_back_parent_and_metadata(self):
        self.save()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TRIGGER stop_delete BEFORE DELETE ON performances BEGIN SELECT RAISE(ABORT,'test failure'); END")
        with self.assertRaises(PerformanceError):
            self.service.delete(self.service.list()[:2])
        with closing(sqlite3.connect(self.path)) as connection, connection:
            for table in ('performances','performance_uploads_v1','performance_enrichment_v1'):
                self.assertEqual(connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0],5)

    def test_stale_edit_and_stale_batch_delete_rejected_without_partial_write(self):
        self.save()
        rows = self.service.list()
        self.change(rows[1],project_name='다른 창 수정')
        with self.assertRaisesRegex(ValueError,'RECORD_CHANGED'):
            self.change(rows[1],client='덮어쓰기 시도')
        with self.assertRaisesRegex(ValueError,'RECORD_CHANGED'):
            self.service.delete(rows[:2])
        self.assertEqual(len(self.service.list()),5)

    def test_legacy_management_id_storage_and_no_missing_db_recreation(self):
        store = PerformanceStore(self.path)
        store.create(Performance(performance_id='legacy',project_name='기존 실적',technical_field='반도체',work_type='특허분석'))
        original = self.service.get('legacy')
        edited = self.change(original,management_id='001245/A-01',project_name='기존 실적 수정')
        self.assertEqual(edited.management_id,'001245/A-01')
        self.assertEqual(edited.performance_id,'legacy')
        self.assertEqual(edited.raw_source,original.raw_source)
        self.path.unlink()
        with self.assertRaises(PerformanceError):
            self.change(edited,year=2028)
        self.assertFalse(self.path.exists())

    def test_more_than_default_store_search_limit_returned(self):
        store = PerformanceStore(self.path)
        for i in range(105):
            store.create(Performance(performance_id=f'legacy-{i}',project_name=f'실적 {i}',year=2025))
        self.assertEqual(len(self.service.list()),105)


class PreviewSelectionHandlers(unittest.TestCase):
    def dialog(self,count):
        from src.local_client.upload_ui import UploadDialog
        dialog = UploadDialog.__new__(UploadDialog)
        dialog._busy = False
        dialog.result = None
        dialog.page = 0
        dialog.preview = UploadPreview('test.xlsx',1,[row() for _ in range(count)],0,[],{})
        dialog.selection = PreviewSelection(count)
        dialog.tree = Mock()
        dialog.tree.get_children.return_value = []
        dialog.selection_text = Mock()
        dialog.message = Mock()
        return dialog

    def test_selection_column_click_and_space_and_zero_selection_save(self):
        dialog = self.dialog(5)
        dialog.tree.identify_column.return_value = '#1'
        dialog.tree.identify_row.return_value = '1'
        dialog._check_click(SimpleNamespace(x=10,y=40))
        self.assertNotIn(1,dialog.selection.checked)
        dialog.tree.identify_column.return_value = '#2'
        dialog._check_click(SimpleNamespace(x=80,y=40))
        self.assertNotIn(1,dialog.selection.checked)
        dialog.tree.selection.return_value = ('0','2')
        self.assertEqual(dialog._check_space(),'break')
        self.assertEqual(dialog.selection.checked,{3,4})
        dialog.select_all('none')
        dialog.save()
        dialog.message.set.assert_called_with('저장할 실적을 선택하세요.')

    def test_paging_keeps_hidden_row_selection_and_bulk_scope_is_all_rows(self):
        dialog = self.dialog(1001)
        dialog.change_page(1)
        self.assertEqual(dialog.page,1)
        self.assertEqual(dialog.tree.insert.call_args.kwargs['iid'],'1000')
        dialog.toggle_checked(1000)
        dialog.change_page(-1)
        dialog.change_page(1)
        self.assertNotIn(1000,dialog.selection.checked)
        dialog.select_all('none')
        self.assertEqual(dialog.selection.checked,set())
        dialog.select_all('invert')
        self.assertEqual(len(dialog.selection.checked),1001)
