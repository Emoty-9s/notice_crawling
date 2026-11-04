"""Real Tk interaction smoke with isolated synthetic data; no paid APIs."""
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _night_fixtures import create_demo, BASE
from src.local_client.ui import DashboardWindow, BLUE, RED, YELLOW, GREEN
from src.local_client.monitor import MonitorResult
from src.local_client.monitor import notice_badge
from src.local_client.seen import SeenStore, seen_path


def texts(widget):
    output = []
    if 'text' in widget.keys():
        output.append(str(widget.cget('text')))
    for child in widget.winfo_children():
        output.extend(texts(child))
    return output


def main():
    import tkinter as tk
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='night-ui-') as folder:
        snapshot, cache, db, health = create_demo(folder)
        before_db, before_cache = db.read_bytes(), cache.read_bytes()
        root = tk.Tk()
        root.withdraw()
        try:
            window = DashboardWindow(root, cache_path=cache, database_path=db, base_url=BASE, auto_sync=False)
            root.update()
            assert len(window.notice_cards) == 2
            assert window.reference_year.get() == ''
            first = window.visible_notices[0]
            assert all(notice_badge(n, window._seen) == 'NEW' for n in window.visible_notices)
            assert not seen_path(cache).exists()  # Loading/syncing never acknowledges.
            window.toggle_match(first['notice_id'])
            assert first['notice_id'] in window.expanded
            assert any('기준 연도' in t for t in texts(window.notice_cards[first['notice_id']]['panel']))
            window.reference_year.set('2026')
            root.update()
            assert len(window.results) == 2
            assert window.results[0]['total_score'] == 22
            assert 'PRIVATE_DO_NOT_DISPLAY' not in ' '.join(texts(root))
            assert any('technical_field' in t for t in texts(window.body))
            window.top_n.set('1')
            assert len(window.results) == 1
            window.toggle_match(first['notice_id'])
            assert first['notice_id'] not in window.expanded
            window.show_detail(first)
            assert window.detail_notice['notice_id'] == first['notice_id']
            persisted = SeenStore(seen_path(cache), BASE).load()
            assert persisted[first['notice_id']] == first['updated_at']
            assert notice_badge(first, persisted) == 'NEW'
            assert any('공고 요약' == t for t in texts(window.body))
            with patch('src.local_client.ui.webbrowser.open', return_value=True) as browser:
                window.open_original(first)
                browser.assert_called_once_with(first['url'], new=2)
            window.show_list()
            assert window.detail_notice is None and len(window.notice_cards) == 2
            other = next(n for n in window.visible_notices if n['notice_id'] != first['notice_id'])
            assert notice_badge(other, window._seen) == 'NEW'
            window.mark_seen(other)
            assert all(n['notice_id'] in window._seen for n in window.visible_notices)
            assert all(notice_badge(n, window._seen) == 'NEW' for n in window.visible_notices)
            assert not any('추천 선택' in t or '추천선택' in t for t in texts(root))
            window._source_document = health
            for row in health['sources']:
                row['notices_found'] = 999  # Raw crawler counts never drive public cards.
            window._render_sources()
            assert len(window._source_widgets) == 7
            for source, widgets in window._source_widgets.items():
                count = sum(n['source_id'] == source for n in window.eligible_active_notices)
                assert widgets[2].cget('text') == f'지원가능 {count}건'
            assert list(window._source_widgets.values())[0][0].light_color == GREEN
            assert list(window._source_widgets.values())[2][0].light_color == RED
            for state, color in [('UPDATED', BLUE), ('FALLBACK', YELLOW), ('ERROR', RED)]:
                window.set_connection(state)
                assert window.github_dot.light_color == color
            window._apply_feed(MonitorResult('FALLBACK', window.data))
            assert len(window.notice_cards) == 2
            window.top_n.set('0')
            window.toggle_match(first['notice_id'])
            assert window.results == []
            # A blocked network worker cannot block Tk's heartbeat. The event
            # releasing it is scheduled on the UI thread itself.
            gate = threading.Event()
            heartbeat = []
            result = MonitorResult('UNCHANGED', window.data)
            def slow_sync(*args):
                assert gate.wait(2)
                return result
            with patch('src.local_client.ui.sync_monitor', side_effect=slow_sync), \
                 patch('src.local_client.ui.read_sources', return_value=(health, False)):
                window.start_sync()
                root.after(150, lambda: (heartbeat.append(True), gate.set()))
                deadline = time.monotonic() + 3
                while window._busy and time.monotonic() < deadline:
                    root.update()
                    time.sleep(.01)
                assert heartbeat and not window._busy
                assert window.github_text.get() == 'GitHub 연결 정상'
            # Late results from a prior settings generation are ignored.
            window._events.put((window._generation-1, 'feed', MonitorResult('ERROR', None)))
            root.update()
            assert window.data is not None
            assert db.read_bytes() == before_db and cache.read_bytes() == before_cache
            window.close()
            assert not window._jobs
            restarted = DashboardWindow(root, cache_path=cache, database_path=db, base_url=BASE, auto_sync=False)
            assert all(n['notice_id'] in restarted._seen for n in restarted.visible_notices)
            assert all(notice_badge(n, restarted._seen) == 'NEW' for n in restarted.visible_notices)
            restarted.close()
            print('NIGHT_UI_SMOKE_PASS: cards, accordion, scores, detail/back, browser dispatch, states, privacy, shutdown')
        finally:
            root.destroy()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
