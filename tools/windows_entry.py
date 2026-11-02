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


def smoke_check(report_path, feed_url):
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
            window = DashboardWindow(root, cache_path=client.cache_path,
                                     database_path=folder / 'absent.db')
            root.update()
            report['tk_patchlevel'] = root.tk.call('info', 'patchlevel')
            report['ui_title'] = root.title()
            report['cache_path_correct'] = window.cache_path.get() == str(client.cache_path)
            report['database_created'] = (folder / 'absent.db').exists()
            if report['database_created'] or not report['cache_path_correct']:
                raise RuntimeError('unexpected path behavior')
            report['status'] = 'SUCCESS'
    except Exception as error:
        report['error_type'] = type(error).__name__
    finally:
        if root is not None:
            root.destroy()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['status'] == 'SUCCESS' else 1


def entry(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if '--smoke-report' in args:
        parser = argparse.ArgumentParser(description='Opt-in isolated packaged UI/feed check')
        parser.add_argument('--smoke-report', required=True)
        parser.add_argument('--feed-url', required=True)
        options = parser.parse_args(args)
        return smoke_check(options.smoke_report, options.feed_url)
    return main(launch_arguments(args))


if __name__ == '__main__':
    raise SystemExit(entry())
