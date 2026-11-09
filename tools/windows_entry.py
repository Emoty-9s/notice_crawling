"""PyInstaller entry adapter; existing UI and explicit path options stay intact."""

import os
import sys
import argparse
import json
import tempfile
from pathlib import Path

from src.local_client.ui import main
from src.local_client.ui import DashboardWindow
from src.local_client.sync import FeedClient


def launch_arguments(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not getattr(sys, 'frozen', False):
        return args
    # User files live outside _MEIPASS/the installation, even in Program Files.
    data_home = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / 'AppData' / 'Local')) / 'NoticeCrawling'
    defaults = ['--cache', str(data_home / 'cache' / 'snapshot.json'),
                '--db', str(data_home / 'performance.db')]
    # argparse uses the last supplied option. Explicit --cache/--db paths keep
    # their original semantics, including relative paths against the caller CWD.
    return defaults + args


def smoke_check(report_path, feed_url, *, database_path=None):
    """Explicit packaged-runtime check; isolated cache, no personal database.

    Run with --smoke-report PATH --feed-url PUBLIC_BASE_URL. Normal launch
    remains the offline dashboard and does not perform this network check.
    """
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {'status': 'ERROR', 'frozen': bool(getattr(sys, 'frozen', False)),
              'default_arguments': launch_arguments([])}
    root = None
    try:
        import tkinter as tk
        with tempfile.TemporaryDirectory(dir=report_path.parent, prefix='exe-smoke-') as folder:
            folder = Path(folder)
            client = FeedClient(feed_url, cache_dir=folder / 'cache', timeout=20)
            first = client.sync()
            second = client.sync()
            report['sync'] = [first.status, second.status]
            if report['sync'] != ['UPDATED', 'UNCHANGED']:
                raise RuntimeError('unexpected sync result')
            root = tk.Tk()
            root.withdraw()
            from src.local_client.monitor import MonitorResult, read_sources
            window = DashboardWindow(root, cache_path=client.cache_path,
                                     database_path=database_path or folder / 'absent.db',
                                     base_url=feed_url, reference_year='2026', auto_sync=False)
            window._apply_feed(MonitorResult(second.status, window.data, database_error=window.database_error,
                                            checked_at=second.metadata['generated_at']))
            window._source_document, window._source_cached = read_sources(feed_url, client.cache_path)
            window._render_sources()
            root.update()
            # Verify real public A processing as well as the feed contract.
            # This is opt-in smoke only; normal startup stays asynchronous.
            import time
            from collections import Counter
            deadline=time.monotonic()+60
            while len(window.work_results)<len(first.feed['notices']) and time.monotonic()<deadline:
                root.update();time.sleep(.01)
            report['local_work_count']=len(window.work_results)
            report['local_work_grades']=dict(Counter(r['status'] for r in window.work_results.values()))
            report['local_work_states']=dict(Counter(r['analysis_state'] for r in window.work_results.values()))
            report['local_work_runtime']=getattr(window,'_work_runtime',{})
            report['github_state'] = window.github_text.get()
            report['source_cards'] = len(window._source_widgets)
            report['source_status_available'] = window._source_document is not None
            report['notice_cards'] = len(window.notice_cards)
            from src.local_client.work_opportunity import is_displayable
            report['default_visible_count']=len(window.visible_notices)
            report['default_visible_titles']=[n['title'] for n in window.visible_notices]
            if any(not is_displayable(window.work_results.get(n['notice_id'])) for n in window.visible_notices):
                raise RuntimeError('unproven opportunity in default list')
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            toggle=next(w for w in descendants(root) if isinstance(w,tk.Checkbutton) and w.cget('text')=='제외된 공고 보기')
            toggle.invoke();root.update()
            report['excluded_toggle_count']=len(window.visible_notices)
            report['excluded_reasons_available']=all(window._work_text(n) for n in window.visible_notices)
            current_ids={n['notice_id'] for n in window.visible_notices}
            window.list_view.set('마감된 공고');window.view_selector.event_generate('<<ComboboxSelected>>');root.update()
            closed_ids={n['notice_id'] for n in window.visible_notices}
            report['closed_including_excluded']=len(closed_ids)
            if current_ids & closed_ids or len(current_ids|closed_ids)!=len(first.feed['notices']):
                raise RuntimeError('excluded toggle lost public notices')
            window.list_view.set('현재 공고');window.view_selector.event_generate('<<ComboboxSelected>>');root.update()
            toggle.invoke();root.update()
            report['active_projection'] = True
            report['local_seen_state'] = not window._seen_error
            if window.visible_notices:
                notice = window.visible_notices[0]
                window.toggle_match(notice['notice_id'])
                report['accordion'] = notice['notice_id'] in window.expanded
                report['matching_count'] = len(window.results)
                window.show_detail(notice)
                report['detail'] = window.detail_notice['notice_id'] == notice['notice_id']
                from src.local_client.monitor import notice_badge
                from src.local_client.seen import SeenStore, seen_path
                persisted = SeenStore(seen_path(client.cache_path), feed_url).load()
                report['seen_persisted'] = persisted.get(notice['notice_id']) == notice['updated_at']
                report['central_new_preserved'] = (notice_badge(notice, persisted) ==
                                                   ('NEW' if notice['is_new'] else 'EXISTING'))
                window.show_list()
                report['back'] = window.detail_notice is None
            report['removed_recommendation_selection'] = not hasattr(window, 'result_tree')
            report['tk_patchlevel'] = root.tk.call('info', 'patchlevel')
            report['ui_title'] = root.title()
            report['cache_path_correct'] = window.cache_path.get() == str(client.cache_path)
            report['database_created'] = (folder / 'absent.db').exists()
            if report['database_created'] or not report['cache_path_correct']:
                raise RuntimeError('unexpected path behavior')
            report['status'] = 'SUCCESS'
            window.close()
    except Exception as error:
        report['error_type'] = type(error).__name__
        if hasattr(error, 'code') and isinstance(error.code, str):
            report['error_code'] = error.code
    finally:
        if root is not None:
            root.destroy()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['status'] == 'SUCCESS' else 1


def entry(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if '--notice-settings-smoke-report' in args:
        parser=argparse.ArgumentParser(description='Synthetic local deadline/delete/restore Tk check')
        parser.add_argument('--notice-settings-smoke-report',required=True)
        from tools.notice_settings_smoke import check
        return check(parser.parse_args(args).notice_settings_smoke_report)
    if '--local-analysis-smoke-report' in args:
        parser=argparse.ArgumentParser(description='Synthetic offline Tk/ONNX A/B check; no company DB')
        parser.add_argument('--local-analysis-smoke-report',required=True)
        from tools.local_notice_smoke import check
        return check(parser.parse_args(args).local_analysis_smoke_report)
    if '--upload-smoke-report' in args:
        parser = argparse.ArgumentParser(description='Explicit local-only upload runtime check (writes the selected DB)')
        parser.add_argument('--upload-smoke-report', required=True)
        parser.add_argument('--upload-file', required=True)
        parser.add_argument('--smoke-db', required=True)
        parser.add_argument('--smoke-cache', required=True)
        parser.add_argument('--smoke-base-url', required=True)
        parser.add_argument('--verify-only', action='store_true')
        parser.add_argument('--enrichment-check', action='store_true')
        parser.add_argument('--management-check', action='store_true')
        from tools.windows_upload_smoke import check
        return check(parser.parse_args(args))
    if '--smoke-report' in args:
        parser = argparse.ArgumentParser(description='Opt-in isolated packaged UI/feed check')
        parser.add_argument('--smoke-report', required=True)
        parser.add_argument('--feed-url', required=True)
        parser.add_argument('--smoke-db', help='Optional existing read-only database for match verification')
        options = parser.parse_args(args)
        if options.smoke_db:
            return smoke_check(options.smoke_report, options.feed_url, database_path=options.smoke_db)
        return smoke_check(options.smoke_report, options.feed_url)
    return main(launch_arguments(args))


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(entry())
