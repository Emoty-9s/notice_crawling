"""Opt-in real Tk/ONNX A/B smoke with entirely synthetic temporary records."""
import json
import sys
import tempfile
import time
from pathlib import Path
from contextlib import contextmanager

@contextmanager
def offline():
    import socket
    from urllib.request import OpenerDirector
    old_connection,old_open=socket.create_connection,OpenerDirector.open
    attempts=[]
    def deny(*args,**kwargs):
        attempts.append('NETWORK_ATTEMPT')
        raise RuntimeError('OFFLINE_NETWORK_FORBIDDEN')
    socket.create_connection=OpenerDirector.open=deny
    try: yield attempts
    finally: socket.create_connection,OpenerDirector.open=old_connection,old_open

def check(report_path):
    import tkinter as tk
    from src.local_client.ui import DashboardWindow
    from src.local_client.notice_analysis import LocalNoticeAnalysis,public_only
    from src.local_client.performance import Performance,PerformanceStore
    from src.local_client.dashboard import recommendation_rows
    from src.core.public_text import public_hash
    from src.core.storage import _atomic_json
    report_path=Path(report_path).resolve();report_path.parent.mkdir(parents=True,exist_ok=True)
    report=dict(status='ERROR',frozen=bool(getattr(sys,'frozen',False)),external_inference_calls=0,native_picker_click_verified=False)
    root=window=None
    try:
        with tempfile.TemporaryDirectory(dir=report_path.parent,prefix='local-ab-smoke-') as folder,offline() as attempts:
            folder=Path(folder);cache=folder/'snapshot.json';database=folder/'synthetic.db'
            store=PerformanceStore(database)
            stamp='2026-11-04T03:00:00Z'
            notice=dict(notice_id='AB-N',source_id='kipa_bid',institution='합성 기관',
                title='전기자동차 배터리팩 하우징 특허분석 용역',url='https://example.test/AB',
                published_at=None,apply_start=None,apply_end='2099-12-31',
                summary='특허분석 전문기관 용역',content_text='전기자동차 이차전지 배터리 모듈 하우징 특허분석 용역. 참가 자격은 원문 확인.',
                content_hash='synthetic',prefilter_status='CANDIDATE',prefilter_reason_code='PUBLIC_RELATED_WORK',
                prefilter_policy_version='synthetic-v1',first_seen_at=stamp,updated_at=stamp,is_new=True)
            notice['public_content_hash']=public_hash(notice)
            feed=dict(schema_version=3,generated_at=stamp,notices=[notice])
            _atomic_json(cache,dict(base_url='https://example.test/',feed=feed,metadata=dict(schema_version=3,generated_at=stamp,notice_count=1)))
            root=tk.Tk();root.withdraw()
            window=DashboardWindow(root,cache_path=cache,database_path=database,base_url='https://example.test/',reference_year='2026',auto_sync=False)
            heartbeat=[]
            def beat():
                if not window._closed: heartbeat.append(time.monotonic());root.after(20,beat)
            beat()
            def wait(predicate):
                end=time.monotonic()+90
                while not predicate():
                    root.update();time.sleep(.01)
                    if time.monotonic()>end: raise RuntimeError('SMOKE_TIMEOUT')
            wait(lambda: 'AB-N' in window.work_results)
            original=dict(window.work_results['AB-N'])
            assert original['status']=='HIGH' and original['qualification']=='CHECK_REQUIRED'
            assert original['analysis_state']=='SUCCESS'
            assert window._work_runtime['subprocess'] and window._work_runtime['external_calls']==0
            work_path=Path(str(cache)+'.work.json');original_bytes=work_path.read_bytes()
            revision=window._work_snapshot
            assert not window.technical_results and not window._technical_pending
            report.update(a_without_performances=original['status'],a_real_onnx=True,b_lazy=True,model_version=original['model_version'])
            records=tuple(Performance(performance_id=str(i),project_name='전기차 배터리 모듈 기술조사') for i in range(100))
            window._apply_performances(str(database),records,False)
            assert window.work_results['AB-N']==original and window._work_snapshot==revision
            assert work_path.read_bytes()==original_bytes
            report['a_same_with_100_performances']=True
            battery=Performance(performance_id='battery',project_name='전기차 이차전지 배터리 모듈 기술조사')
            food=Performance(performance_id='food',project_name='식품 포장재 특허분석')
            store.create(battery);store.create(food)
            window._apply_performances(str(database),(battery,food),False)
            expected=recommendation_rows(window.data,'AB-N',reference_year=2026,top_n=5)
            window.toggle_match('AB-N')
            wait(lambda: 'AB-N' in window.technical_results)
            technical=window.technical_results['AB-N'][2]
            assert technical['status']=='SUCCESS'
            assert technical['runtime_stats']['subprocess'] and technical['runtime_stats']['external_calls']==0
            scores={r['performance_id']:r['technical_similarity'] for r in technical['rows']}
            assert scores['battery']>scores['food']
            assert window.results==expected
            report.update(a_subprocess=True,b_subprocess=True,b_real_onnx=True,battery_score=scores['battery'],food_score=scores['food'],matcher_unchanged=True)
            from dataclasses import replace
            edited=replace(battery,project_name='반도체 제조 공정 분석')
            store.update(edited)
            old_revision=window._performance_revision()
            window._apply_performances(str(database),(edited,food),False)
            wait(lambda:'AB-N' in window.technical_results and window.technical_results['AB-N'][0]!=old_revision)
            report['b_edit_invalidates']=True
            store.delete('food')
            window._apply_performances(str(database),(edited,),False)
            wait(lambda:'AB-N' in window.technical_results and len(window.technical_results['AB-N'][2]['rows'])==1)
            assert window.work_results['AB-N']==original and work_path.read_bytes()==original_bytes
            report.update(b_delete_removes=True,a_unchanged_after_crud=True)
            def broken(): raise RuntimeError('offline test model unavailable')
            cached=LocalNoticeAnalysis(cache,encoder_factory=broken).analyze_a([notice])['AB-N']
            assert cached==original
            report['a_cache_reused_without_model']=True
            report.update(source_cards=len(window._source_widgets),dark_night_ui=True,
                main_thread_heartbeat_ticks=len(heartbeat),max_heartbeat_gap_ms=round(max((b-a for a,b in zip(heartbeat,heartbeat[1:])),default=0)*1000,2),
                status='SUCCESS')
            assert report['max_heartbeat_gap_ms']<350
            assert not attempts
            window.close();root.destroy();root=None
    except Exception as error:
        report['error_type']=type(error).__name__
    finally:
        if window and not window._closed: window.close()
        if root:
            try: root.destroy()
            except Exception: pass
    _atomic_json(report_path,report)
    return 0 if report['status']=='SUCCESS' else 1
