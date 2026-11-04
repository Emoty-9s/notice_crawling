"""Opt-in frozen Tk lifecycle smoke; synthetic public notices, no company DB."""
import copy
import json
import sys
import tempfile
import time
from datetime import datetime,timedelta,timezone
from pathlib import Path

def check(report_path):
    import tkinter as tk
    from src.local_client.ui import DashboardWindow,BG
    from src.local_client.notice_settings import settings_path,effective_deadline
    from src.local_client.local_model import LocalEncoder
    from src.local_client.sync import FeedClient,_atomic_snapshot
    from src.local_client.monitor import read_local,MonitorResult
    from src.local_client.notice_analysis import adapt_notice,LocalNoticeAnalysis
    from src.local_client.performance import Performance
    from src.local_client.matcher import match_notice
    from src.core.public_text import public_hash
    from src.core.retention import retention_date
    from tools.local_notice_smoke import offline
    report_path=Path(report_path).resolve();report_path.parent.mkdir(parents=True,exist_ok=True)
    report=dict(status='ERROR',frozen=bool(getattr(sys,'frozen',False)),native_mouse_verified=False)
    root=window=None
    try:
        with tempfile.TemporaryDirectory(dir=report_path.parent,prefix='notice-settings-smoke-') as folder,offline() as calls:
            folder=Path(folder);cache=folder/'snapshot.json';database=folder/'absent-company.db'
            today=retention_date();stamp=datetime.now(timezone.utc).isoformat();base='https://example.test/'
            def notice(key,age,official=None,title='배터리 특허분석 용역 수행기관 모집'):
                n=dict(notice_id=key,source_id='kipa_bid',institution='합성 기관',title=title,url=base+key,
                    published_at=(today-timedelta(days=age)).isoformat(),apply_start=None,apply_end=official,
                    summary='배터리 특허분석 용역 수행기관 모집',content_text='배터리 특허분석 용역 수행기관 모집. 세부 참가 자격 확인 필요.',
                    prefilter_status='CANDIDATE',prefilter_policy_version='synthetic',prefilter_reason_code='SYNTHETIC',
                    content_hash='synthetic-'+key,first_seen_at=stamp,updated_at=stamp,is_new=False)
                n['public_content_hash']=public_hash(n);return n
            rows=[notice('day20',20),notice('day21',21),notice('official',0,'2000-01-01'),
                  notice('fallback',0),notice('excluded',0,title='지식재산 출품작 공모전')]
            rows[4]['summary']=rows[4]['content_text']='지식재산 출품작을 공모합니다.'
            rows[4]['public_content_hash']=public_hash(rows[4])
            rows[3]['published_at']=None;rows[3]['first_seen_at']=(datetime.now(timezone.utc)-timedelta(days=20)).isoformat()
            rows[3]['public_content_hash']=public_hash(rows[3])
            feed=dict(schema_version=3,generated_at=stamp,notices=rows)
            meta=dict(schema_version=3,generated_at=stamp,notice_count=len(rows))
            _atomic_snapshot(cache,dict(base_url=base,feed=feed,metadata=meta));original=cache.read_bytes()
            def wait(predicate):
                end=time.monotonic()+60
                while not predicate():
                    root.update();time.sleep(.01)
                    if time.monotonic()>end:raise RuntimeError('LIFECYCLE_TIMEOUT')
            def start():
                nonlocal root,window
                root=tk.Tk();root.withdraw()
                window=DashboardWindow(root,cache_path=cache,database_path=database,base_url=base,reference_year=2026,auto_sync=False)
                wait(lambda:len(window.work_results)==len(rows))
            def ids():return {n['notice_id'] for n in window.visible_notices}
            def view(value):
                window.list_view.set(value);window.view_selector.event_generate('<<ComboboxSelected>>');root.update()
            def children(widget):
                for child in widget.winfo_children():yield child;yield from children(child)
            def button(widget,text):return next(w for w in children(widget) if isinstance(w,tk.Button) and w.cget('text')==text)
            def edit(n,value=None,clear=False):
                dialog=window.open_deadline(n)
                if clear:button(dialog,'사용자 마감일 해제').invoke()
                else:
                    entry=next(w for w in children(dialog) if isinstance(w,tk.Entry));entry.delete(0,'end');entry.insert(0,value)
                    button(dialog,'저장').invoke()
                root.update();assert not dialog.winfo_exists()
            start();assert ids()=={'day20','fallback'}
            report['day20_visible_day21_hidden']=True
            report['dark_night_ui']=BG=='#0c0f14';report['source_cards']=len(window._source_widgets)
            work=dict(window.work_results);a_before=Path(str(cache)+'.work.json').read_bytes()
            performances=[Performance(performance_id='p',project_name='배터리 특허분석',technical_field='배터리')]
            matcher_before=match_notice(adapt_notice(rows[0]),performances,reference_year=2026)
            analysis=LocalNoticeAnalysis(cache)
            b_result=analysis.analyze_b(rows[0],performances)
            assert b_result['status']=='SUCCESS'
            b_before=Path(str(cache)+'.technical.json').read_bytes()
            view('마감된 공고');assert ids()=={'day21','official'}
            # Use the actual card button then the date editor Save button.
            card=window.notice_cards['day21']['card'];button(card,'마감일 설정').invoke()
            dialog=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel) and w.title()=='공고 마감일 설정')
            entry=next(w for w in children(dialog) if isinstance(w,tk.Entry));entry.insert(0,'2099-12-31');button(dialog,'저장').invoke();root.update()
            view('현재 공고');assert 'day21' in ids()
            edit(rows[1],'2000-01-01');assert 'day21' not in ids()
            edit(rows[1],clear=True);assert 'day21' not in ids()
            edit(rows[2],'2099-12-31');assert 'official' in ids() and rows[2]['apply_end']=='2000-01-01'
            report['deadline_save_edit_clear_official_preserved']=True
            # Deletion is a persisted preference; source, matching and caches stay intact.
            button(window.notice_cards['day20']['card'],'목록에서 삭제').invoke();root.update();assert 'day20' not in ids()
            view('삭제한 공고');assert ids()=={'day20'}
            button(window.notice_cards['day20']['card'],'복원').invoke();root.update();assert not ids()
            view('현재 공고');assert 'day20' in ids()
            window.show_detail(rows[0],mark_seen=False);button(window.body,'목록에서 삭제').invoke();window.show_list()
            assert 'day20' not in ids();report['card_detail_delete_and_restore']=True
            edit(rows[4],'2099-12-31');assert 'excluded' not in ids()
            report['date_cannot_promote_a_exclusion']=True
            assert cache.read_bytes()==original
            updated=copy.deepcopy(feed);updated['notices'][0]['is_new']=True
            responses={'notices.json':updated,'metadata.json':meta}
            client=FeedClient(base,cache_dir=folder,transport=lambda url,_:json.dumps(responses[url.rsplit('/',1)[1]]).encode())
            client.sync();loaded=read_local(cache,database,base);window._apply_feed(MonitorResult('UPDATED',loaded.data,database_error=True));root.update()
            assert 'day20' not in ids() and 'official' in ids()
            assert window.work_results==work and Path(str(cache)+'.work.json').read_bytes()==a_before
            assert match_notice(adapt_notice(rows[0]),performances,reference_year=2026)==matcher_before
            assert analysis.analyze_b(rows[0],performances)==b_result
            assert Path(str(cache)+'.technical.json').read_bytes()==b_before
            report['a_b_caches_unchanged_by_preferences']=True
            report['sync_preserves_preferences_and_a_matcher']=True
            window.close();root.destroy();root=window=None
            start();assert 'day20' not in ids() and 'official' in ids()
            view('삭제한 공고');assert ids()=={'day20'}
            assert window._notice_settings['official']['user_deadline']=='2099-12-31'
            report['restart_preserves_deadline_and_deletion']=True
            report['settings_atomic_file']=settings_path(cache).is_file()
            report['company_database_created']=database.exists();assert not database.exists()
            assert not calls;report['external_calls']=len(calls)
            report['real_onnx']=all(r['analysis_state']=='SUCCESS' for r in window.work_results.values())
            report['status']='SUCCESS';window.close()
    except Exception as error:
        report['error_type']=type(error).__name__
        import traceback
        report['failure_line']=traceback.extract_tb(error.__traceback__)[-1].lineno
        if str(error) in ('LIFECYCLE_TIMEOUT',):report['error_code']=str(error)
    finally:
        if root is not None:root.destroy()
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if report['status']=='SUCCESS' else 1
