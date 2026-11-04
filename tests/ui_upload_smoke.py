"""Real Tk upload flow with a selected real xlsx; all fixtures are tests-only."""
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openpyxl import Workbook
from _night_fixtures import create_demo, BASE
from src.local_client.ui import DashboardWindow
from src.local_client.performance import PerformanceStore


def wait(root, predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        root.update()
        time.sleep(.01)
    root.update()
    assert predicate(), 'UI worker did not complete'


def main():
    import tkinter as tk
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='upload-ui-') as folder:
        folder = Path(folder)
        snapshot, cache, unused_db, health = create_demo(folder)
        db = folder/'selected-private.db'
        file = folder/'실적.xlsx'
        book = Workbook()
        sheet = book.active
        sheet.append(['관리번호', '사업명', '고객사', '수행년도', '기술분야', '주요업무'])
        sheet.append(['001245', '반도체 특허 분석', '합성 기관', 2026, '반도체', '반도체 특허분석'])
        book.save(file)
        book.close()
        original = file.read_bytes()
        root = tk.Tk()
        root.withdraw()
        guards = ('urllib.request.OpenerDirector.open', 'socket.create_connection',
                  'src.ai.gemini.GeminiClient.generate', 'src.local_client.sync.FeedClient.sync')
        from contextlib import ExitStack
        try:
            with ExitStack() as stack:
                for target in guards:
                    stack.enter_context(patch(target, side_effect=AssertionError('external call forbidden')))
                window = DashboardWindow(root, cache_path=cache, database_path=db, base_url=BASE,
                                         auto_sync=False, reference_year=2026)
                root.update()
                assert window.upload_button.cget('text') == '실적 업로드'
                assert not db.exists()
                with patch('tkinter.filedialog.askopenfilename', return_value=str(file)) as chooser:
                    window.upload_button.invoke()
                    chooser.assert_called_once()
                upload = window._upload_dialog
                wait(root, lambda: upload.preview is not None)
                assert not db.exists(), 'preview wrote the DB'
                assert len(upload.tree.get_children()) == 1
                assert upload.preview.analysis_stats.get('subprocess') is True
                assert upload.preview.analysis_stats['external_calls'] == 0
                assert upload.preview.rows[0].management_id == '001245'
                upload.tree.selection_set('0')
                upload._show_row()
                assert '001245' in upload.details.get('1.0', 'end')
                upload.save_button.invoke()
                wait(root, lambda: upload.result is not None and window.data is not None and len(window.data.performances) == 1)
                assert upload.result.saved == 1
                notice = window.visible_notices[0]
                window.toggle_match(notice['notice_id'])
                assert len(window.results) == 1
                assert window.results[0]['total_score'] > 0
                upload.close()
                window.close()
                root.destroy()
                root = tk.Tk()
                root.withdraw()
                restarted = DashboardWindow(root, cache_path=cache, database_path=db, base_url=BASE,
                                            auto_sync=False, reference_year=2026)
                root.update()
                assert len(restarted.data.performances) == 1
                assert len(PerformanceStore(db).search()) == 1
                restarted.close()
                assert file.read_bytes() == original
                print('UPLOAD_UI_SMOKE_PASS: button, picker dispatch, real xlsx preview, save, immediate matcher, restart, local-only')
        finally:
            root.destroy()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
