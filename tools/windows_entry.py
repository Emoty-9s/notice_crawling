"""PyInstaller entry adapter; existing UI and explicit path options stay intact."""

import os
import sys
from pathlib import Path

from src.local_client.ui import main


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


if __name__ == '__main__':
    raise SystemExit(main(launch_arguments()))
