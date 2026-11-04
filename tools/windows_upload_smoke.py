"""Explicit opt-in frozen upload verification. No embedded fixtures or demo DB.

The caller supplies all files/paths. Normal production launches never enter this
module. The native picker return is injected for repeatable testing; the real
upload button, preview, save button, workers, database and matcher are exercised.
"""
import json
import socket
import time
import re
from pathlib import Path
from urllib.request import OpenerDirector


def memory_mib():
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in
            ('peak', 'working', 'peak_paged', 'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile', 'private')]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise RuntimeError('MEMORY_MEASUREMENT_FAILED')
    return {name: round(getattr(counters, name)/1024**2, 2) for name in ('working', 'peak', 'private')}


def check(options):
    from src.local_client.ui import DashboardWindow
    import tkinter as tk
    from tkinter import filedialog
    import sys
    report = {'status': 'ERROR', 'frozen': bool(getattr(sys, 'frozen', False)),
              'verify_only': options.verify_only, 'native_picker_click_verified': False}
    root = window = manager = None
    original_open, original_connection = OpenerDirector.open, socket.create_connection
    original_picker = filedialog.askopenfilename
    attempts = []
    started = time.perf_counter()
    heartbeat = []
    def deny(*args, **kwargs):
        attempts.append(True)
        raise RuntimeError('NETWORK_FORBIDDEN')
    def wait(predicate):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            root.update()
            if predicate():
                return
            time.sleep(.01)
        if not predicate():
            raise RuntimeError('UPLOAD_TIMEOUT')
    try:
        OpenerDirector.open, socket.create_connection = deny, deny
        source = Path(options.upload_file).resolve()
        original_bytes = source.read_bytes()
        db = Path(options.smoke_db).resolve()
        before_db = db.read_bytes() if db.exists() else None
        root = tk.Tk()
        root.withdraw()
        def tick():
            heartbeat.append(time.monotonic())
            root.after(25, tick)
        root.after(25, tick)
        window = DashboardWindow(root, database_path=db, cache_path=options.smoke_cache,
                                 base_url=options.smoke_base_url, reference_year=2026, auto_sync=False)
        root.update()
        report['upload_button'] = window.upload_button.cget('text') == '실적 업로드'
        report['management_button'] = window.management_button.cget('text') == '실적 관리'
        report['source_cards'] = len(window._source_widgets)
        report['github_status_card'] = hasattr(window, 'github_dot')
        from src.local_client.ui import BG
        report['dark_night_ui'] = BG == '#0c0f14'
        report['records_before'] = len(window.data.performances) if window.data else 0
        check_ai = getattr(options, 'enrichment_check', False)
        check_management = getattr(options,'management_check',False)
        manager = None
        if check_management:
            window.management_button.invoke()
            manager = window._management_dialog
            wait(lambda:not manager._busy)
            if not options.verify_only:
                report['empty_management_readonly'] = not db.exists() and not manager.rows
                if not report['empty_management_readonly']:
                    raise RuntimeError('EMPTY_MANAGEMENT_WROTE_DATABASE')
        if check_ai:
            from src.local_client.local_model import LocalEncoder
            report['idle_model_sessions'] = LocalEncoder.active_sessions
            report['runtime_imported_on_start'] = 'onnxruntime' in sys.modules
            if report['idle_model_sessions'] or report['runtime_imported_on_start']:
                raise RuntimeError('MODEL_LOADED_AT_STARTUP')
        if not options.verify_only:
            filedialog.askopenfilename = lambda **kwargs: str(source)
            window.upload_button.invoke()
            upload = window._upload_dialog
            wait(lambda: upload.preview is not None or (not upload._busy))
            if upload.preview is None:
                raise RuntimeError('PREVIEW_FAILED')
            report['preview_rows'] = len(upload.preview.rows)
            report['preview_columns'] = list(upload.tree['columns'])
            if report['preview_columns'] != ['selected','number', 'year', 'management_id', 'project_name', 'client', 'technical_field', 'work_type']:
                raise RuntimeError('PREVIEW_COLUMNS_MISMATCH')
            report['default_all_selected'] = upload.selection.checked == set(range(len(upload.preview.rows)))
            excluded_ids = set()
            if check_management:
                upload.select_all('none')
                upload.save_button.invoke()
                report['zero_selection_no_write'] = not db.exists() and upload.message.get() == '저장할 실적을 선택하세요.'
                upload.select_all('all')
                upload.select_all('invert')
                report['invert_clears_all'] = not upload.selection.checked
                upload.select_all('all')
                for index in (1,3):
                    if index < len(upload.preview.rows):
                        upload.tree.selection_set(str(index))
                        upload._check_space()
                        excluded_ids.add(upload.preview.rows[index].fingerprint)
                report['selected_before_save'] = len(upload.selection.checked)
                report['unchecked_before_save'] = len(excluded_ids)
                if not all(report[k] for k in ('default_all_selected','zero_selection_no_write','invert_clears_all')):
                    raise RuntimeError('SELECTION_CONTROLS_FAILED')
            ev_rows = [(i, row) for i, row in enumerate(upload.preview.rows) if row.project_name == '전기자동차 배터리팩']
            if ev_rows:
                report['ev_battery_tags'] = all([v['name'] for v in row.technical_tags][:2] == ['전기자동차', '배터리'] for _, row in ev_rows)
                report['ev_battery_fields'] = all([v['name'] for v in row.technical_fields][:2] == ['자동차 / 모빌리티', '이차전지 / 에너지저장'] for _, row in ev_rows)
                report['ev_battery_visible'] = all(any(str(v).startswith('자동차 / 모빌리티 · 이차전지 / 에너지저장') for v in upload.tree.item(str(i), 'values')) for i, _ in ev_rows)
                if not report['ev_battery_tags'] or not report['ev_battery_visible'] or not report['ev_battery_fields']:
                    raise RuntimeError('EV_BATTERY_TAGS_MISSING')
            report['preview_sheets'] = upload.preview.sheet_count
            report['leading_zero_preserved'] = any(row.management_id == '001245' for row in upload.preview.rows)
            report['preview_did_not_write_db'] = (db.read_bytes() if db.exists() else None) == before_db
            if not report['preview_did_not_write_db']:
                raise RuntimeError('EARLY_DATABASE_WRITE')
            if check_ai:
                from src.local_client.technical_labels import allowed_technical_fields
                allowed_fields = set(allowed_technical_fields())
                report['closed_taxonomy'] = all(row.technical_field in allowed_fields or row.technical_field in ('',None,'미분류')
                    for row in upload.preview.rows) and all(len(row.technical_fields) <= 3 and
                    all(v['name'] in allowed_fields for v in row.technical_fields) for row in upload.preview.rows)
                housing = [(i,row) for i,row in enumerate(upload.preview.rows) if row.project_name == '전기자동차 배터리팩 하우징']
                if housing:
                    expected = '자동차 / 모빌리티 · 이차전지 / 에너지저장 · 소부장'
                    report['soboogang_triple_visible'] = all(expected in upload.tree.item(str(i),'values') for i,_ in housing)
                    if not report['soboogang_triple_visible']:
                        raise RuntimeError('SOBOOJANG_PREVIEW_FAILED')
                if not report['closed_taxonomy']:
                    raise RuntimeError('OUTSIDE_TAXONOMY')
                report['hallucinations'] = upload.preview.analysis_stats.get('protected_field_changes', -1)
                report['inferred_technical_rows'] = sum(row.field_sources.get('technical_field') == 'local_model' for row in upload.preview.rows)
                report['inferred_work_rows'] = sum(row.field_sources.get('work_type') == 'local_model' for row in upload.preview.rows)
                report['keyword_rows'] = sum(bool(row.keywords) for row in upload.preview.rows)
                report['analysis_process'] = upload.preview.analysis_stats
                report['explicit_values_preserved'] = upload.preview.analysis_stats.get('explicit_field_changes', -1) == 0
                if (report['hallucinations'] or not report['inferred_technical_rows'] or not report['inferred_work_rows']
                        or not report['keyword_rows'] or not report['explicit_values_preserved']):
                    raise RuntimeError('AI_ENRICHMENT_FAILED')
                index = next(i for i, row in enumerate(upload.preview.rows) if row.field_sources.get('technical_field') == 'local_model' and i in upload.selection.checked)
                upload.tree.selection_set(str(index))
                upload._show_row()
                upload.tech_value.set('통신 / 네트워크')
                upload.work_value.set('사용자 고정 업무')
                upload.edit_button.invoke()
                report['user_editor'] = upload.preview.rows[index].field_sources.get('technical_field') == 'user'
            upload.save_button.invoke()
            wait(lambda: upload.result is not None or not upload._busy)
            if upload.result is None or upload.result.failed:
                raise RuntimeError('SAVE_FAILED')
            report['saved'] = upload.result.saved
            report['duplicates'] = upload.result.duplicates
            report['excluded_by_user'] = upload.result.excluded_by_user
            if check_management:
                from src.local_client.upload_store import load_enrichment_preview
                saved_rows = load_enrichment_preview(db).rows
                report['only_checked_saved'] = not ({r.fingerprint for r in saved_rows} & excluded_ids) and len(saved_rows) == report['selected_before_save']
                if not report['only_checked_saved']:
                    raise RuntimeError('UNCHECKED_RECORD_SAVED')
            wait(lambda: window.data is not None and not window.database_error
                 and len(window.data.performances) >= upload.result.saved)
            if check_ai:
                upload.force_analysis.set(True)
                upload.analyze_button.invoke()
                wait(lambda: upload.preview is not None or not upload._busy)
                if upload.preview is None:
                    raise RuntimeError('REANALYSIS_FAILED')
                report['user_survives_force_reanalysis'] = any(row.technical_field == '통신 / 네트워크'
                    and row.work_type == '사용자 고정 업무' and row.field_sources.get('technical_field') == 'user'
                    for row in upload.preview.rows)
                if not report['user_survives_force_reanalysis']:
                    raise RuntimeError('USER_OVERRIDE_LOST')
                upload.save_button.invoke()
                wait(lambda: upload.result is not None or not upload._busy)
                if upload.result is None or upload.result.failed:
                    raise RuntimeError('REANALYSIS_SAVE_FAILED')
                report['reanalyzed_saved'] = upload.result.updated
            upload.close()
            if check_management:
                report['phase'] = 'management_after_upload'
                wait(lambda:not manager._busy and len(manager.rows) == report['selected_before_save'])
                window.toggle_match(window.visible_notices[0]['notice_id'])
                report['management_auto_refresh'] = True
                manager.query.set('001245')
                manager.refresh()
                report['phase'] = 'management_search'
                wait(lambda:not manager._busy)
                report['management_search'] = len(manager.rows) == 1
                manager.query.set('')
                manager.refresh()
                report['phase'] = 'management_clear_search'
                wait(lambda:not manager._busy)
                target = next(r for r in manager.rows if r.project_name == '전기자동차 배터리팩')
                manager.tree.selection_set(target.performance_id)
                manager.edit_button.invoke()
                editor = manager.editor
                editor.values['year'].set('2028')
                editor.values['management_id'].set('000007/PRJ-UI')
                editor.values['project_name'].set('검증용 수정 실적')
                editor.values['client'].set('검증 고객')
                expected_technical = {'반도체', '이차전지 / 에너지저장'}
                for name,value in editor.technical.items():
                    value.set(name in expected_technical)
                editor.work.set('기술사업화')
                editor.save_button.invoke()
                report['phase'] = 'management_edit'
                wait(lambda:editor._closed and not manager._busy)
                wait(lambda:any(p.performance_id == target.performance_id and p.project_name == '검증용 수정 실적' for p in window.data.performances))
                report['matcher_edit_auto_refresh'] = any(r['performance_id'] == target.performance_id and r['project_name'] == '검증용 수정 실적' for r in window.results)
                edited = manager.service.get(target.performance_id)
                from src.local_client.performance_management import technical_names
                report['management_edit'] = (edited.management_id == '000007/PRJ-UI' and edited.year == 2028
                    and set(technical_names(edited)) == expected_technical and edited.work_type == '기술사업화')
                report['management_two_technical_fields'] = len(technical_names(edited)) == 2
                report['management_user_sources'] = all(edited.field_sources.get(n) == 'user' for n in ('year','management_id','project_name','client','technical_field','work_type'))
                deleted = next(r for r in manager.rows if r.management_id == '001245')
                manager.tree.selection_set(deleted.performance_id)
                from tkinter import messagebox
                original_confirm = messagebox.askyesno
                try:
                    messagebox.askyesno = lambda *a,**k:False
                    manager.delete_button.invoke()
                    report['delete_cancelled'] = manager.service.get(deleted.performance_id) is not None
                    messagebox.askyesno = lambda *a,**k:True
                    manager.delete_button.invoke()
                    wait(lambda:not manager._busy and len(manager.rows) == report['selected_before_save']-1)
                    wait(lambda:len(window.data.performances) == report['selected_before_save']-1)
                finally:
                    messagebox.askyesno = original_confirm
                report['management_delete'] = manager.service.get(deleted.performance_id) is None
                report['matcher_deleted_record_absent'] = all(r['performance_id'] != deleted.performance_id for r in window.results)
                if not all(report[k] for k in ('management_search','management_edit','management_user_sources','delete_cancelled','management_delete','matcher_deleted_record_absent','matcher_edit_auto_refresh')):
                    raise RuntimeError('MANAGEMENT_FLOW_FAILED')
        if window.data is None:
            raise RuntimeError('CACHE_REQUIRED_FOR_MATCH_CHECK')
        report['records_after'] = len(window.data.performances)
        if not window.visible_notices or not window.data.performances:
            raise RuntimeError('MATCH_INPUT_REQUIRED')
        window.toggle_match(window.visible_notices[0]['notice_id'])
        report['matching_count'] = len(window.results)
        report['positive_match'] = bool(window.results and window.results[0]['total_score'] > 0)
        if not report['positive_match']:
            raise RuntimeError('MATCH_FAILED')
        report['source_unchanged'] = source.read_bytes() == original_bytes
        if check_management:
            from src.local_client.performance_management import PerformanceManagement
            from src.local_client.performance_management import technical_names
            from src.local_client.upload import preview_upload
            stored_managed = PerformanceManagement(db).list()
            edited_managed = [r for r in stored_managed if r.management_id == '000007/PRJ-UI']
            source_rows = len(preview_upload(source).rows)
            expected_count = source_rows - sum(i < source_rows for i in (1,3)) - 1
            report['management_persisted'] = (len(stored_managed) == expected_count and len(edited_managed) == 1
                and set(technical_names(edited_managed[0])) == {'반도체', '이차전지 / 에너지저장'})
            report['deleted_record_persisted_absent'] = not any(r.management_id == '001245' for r in stored_managed)
            import sqlite3
            from contextlib import closing
            with closing(sqlite3.connect(db)) as connection:
                report['database_integrity'] = connection.execute('PRAGMA integrity_check').fetchone()[0]
                report['foreign_key_violations'] = len(connection.execute('PRAGMA foreign_key_check').fetchall())
                report['orphan_metadata'] = sum(connection.execute(f'SELECT count(*) FROM {table} m LEFT JOIN performances p USING(performance_id) WHERE p.performance_id IS NULL').fetchone()[0]
                    for table in ('performance_enrichment_v1','performance_uploads_v1'))
            if (not report['management_persisted'] or not report['deleted_record_persisted_absent'] or report['orphan_metadata']
                    or report['database_integrity'] != 'ok' or report['foreign_key_violations']):
                raise RuntimeError('MANAGEMENT_PERSISTENCE_FAILED')
        if check_ai:
            from src.local_client.upload_store import load_enrichment_preview
            stored = load_enrichment_preview(db)
            ev_stored = [row for row in stored.rows if row.project_name == '전기자동차 배터리팩']
            if ev_stored:
                report['ev_battery_persisted'] = all(
                    [v['name'] for v in row.technical_tags][:2] == ['전기자동차', '배터리']
                    and [v['name'] for v in row.technical_fields][:2] == ['자동차 / 모빌리티', '이차전지 / 에너지저장']
                    for row in ev_stored)
                if not report['ev_battery_persisted']:
                    raise RuntimeError('MULTILABEL_RESTART_LOSS')
            report['user_override_persisted'] = any(row.technical_field == '통신 / 네트워크'
                and row.work_type == '사용자 고정 업무' and row.field_sources.get('technical_field') == 'user' for row in stored.rows)
            report['active_model_sessions_after'] = LocalEncoder.active_sessions
            report['model_version_recorded'] = any(row.ai_model_version for row in stored.rows)
            report['memory_mib'] = memory_mib()
            report['wall_seconds'] = round(time.perf_counter()-started, 3)
            report['ui_heartbeat_ticks'] = len(heartbeat)
            report['max_heartbeat_gap_ms'] = round(max((b-a for a,b in zip(heartbeat, heartbeat[1:])), default=0)*1000, 2)
            if not report['user_override_persisted'] or report['active_model_sessions_after'] or not report['model_version_recorded']:
                raise RuntimeError('PROVENANCE_OR_UNLOAD_FAILED')
        report['external_calls'] = len(attempts)
        if attempts or not report['source_unchanged']:
            raise RuntimeError('UPLOAD_SIDE_EFFECT')
        report['status'] = 'SUCCESS'
    except Exception as error:
        report['error_type'] = type(error).__name__
        if re.fullmatch(r'[A-Z_]+',str(error)):
            report['error_code'] = str(error)
        if manager is not None:
            report['management_diagnostic'] = {'busy':manager._busy,'closed':manager._closed,'rows':len(manager.rows),
                'error_code':getattr(manager,'_last_error',None), 'events':manager._events.qsize(),
                'poll_job':manager._job, 'pending_jobs':list(root.tk.call('after','info'))}
    finally:
        OpenerDirector.open, socket.create_connection = original_open, original_connection
        filedialog.askopenfilename = original_picker
        if window:
            window.close()
        if root:
            root.destroy()
    path = Path(options.upload_smoke_report).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['status'] == 'SUCCESS' else 1
