"""Optional real-Tk smoke, separate from display-independent unittest discovery.

Run on a desktop: .venv/Scripts/python.exe tests/ui_dashboard_smoke.py
Uses the same temporary synthetic fixture and side-effect guards as unit tests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_dashboard import DashboardTests
from src.local_client.ui import DashboardWindow


def main():
    import tkinter as tk

    case = DashboardTests()
    root = None
    try:
        case.setUp()
        before_db = case.db_path.read_bytes()
        before_cache = case.cache_path.read_bytes()
        root = tk.Tk()
        root.withdraw()
        window = DashboardWindow(root, cache_path=case.cache_path, database_path=case.db_path)
        root.update()
        assert window.reference_year.get() == ''  # No implicit current-year default.
        assert len(window.notice_tree.get_children()) == 2
        window.notice_tree.selection_set('0')
        root.update()
        window.run_match()
        assert 'INVALID_REFERENCE_YEAR' in window.status.get()
        assert not window.result_tree.get_children()

        window.reference_year.set('2026')
        window.run_match()
        root.update()
        assert len(window.result_tree.get_children()) == 2
        assert str(window.result_tree.item('0', 'values')[-1]) == '22'
        assert 'technical_field' in window.reason_text.get('1.0', 'end')
        assert '22' in window.reason_text.get('1.0', 'end')
        assert window.reason_text.cget('state') == 'disabled'

        window.top_n.set('1')
        assert not window.result_tree.get_children()  # Old results invalidated.
        window.run_match()
        root.update()
        assert len(window.result_tree.get_children()) == 1
        window.top_n.set('0')
        window.run_match()
        root.update()
        assert not window.result_tree.get_children()

        window.cache_path.set(str(case.root/'missing.json'))
        assert window.data is None
        assert not window.notice_tree.get_children()
        window.reload()
        window.run_match()
        assert window.data is None and not window.result_tree.get_children()
        assert case.db_path.read_bytes() == before_db
        assert case.cache_path.read_bytes() == before_cache
        print('UI_SMOKE_PASS: real Tk widgets, selection, scores, evidence, invalidation, empty/error states, immutable inputs')
        return 0
    finally:
        if root is not None:
            root.destroy()
        case.doCleanups()


if __name__ == '__main__':
    raise SystemExit(main())
