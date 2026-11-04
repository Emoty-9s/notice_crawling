"""Dark Night desktop monitor. Network I/O stays off the Tk thread."""
import argparse
import math
import queue
import threading
import time
import webbrowser
from pathlib import Path

from .dashboard import DashboardError, notice_rows, recommendation_rows, recommendation_details
from .monitor import (DEFAULT_FEED_URL, MonitorResult, notice_badge, ordered_notices,
                      read_local, read_sources, safe_original_url, sync_monitor, source_list_url)
from .performance import DEFAULT_DB_PATH
from .sync import DEFAULT_CACHE_DIR, SyncError
from .seen import SeenStore, SeenStateError, seen_path
from src.renderer.source_status import SOURCES

BG = '#0c0f14'
CARD = '#15191f'
INNER = '#11151b'
LINE = '#292f38'
TEXT = '#e8ebef'
MUTED = '#8993a3'
ORANGE = '#c88350'
BLUE = '#69a9e8'
YELLOW = '#d3b66c'
RED = '#ce777b'
GREEN = '#76b69a'
FONT = '맑은 고딕'


def blend(first, second, amount):
    a, b = [tuple(int(c[i:i+2], 16) for i in (1, 3, 5)) for c in (first, second)]
    return '#' + ''.join(f'{round(x+(y-x)*amount):02x}' for x, y in zip(a, b))


def display_stamp(value):
    if not value:
        return '확인 이력 없음'
    from datetime import datetime
    try:
        return datetime.fromisoformat(value).astimezone().strftime('%Y-%m-%d %H:%M')
    except (TypeError, ValueError):
        return '확인 이력 없음'


class DashboardWindow:
    def __init__(self, root, *, cache_path=DEFAULT_CACHE_DIR/'snapshot.json', database_path=DEFAULT_DB_PATH,
                 reference_year='', top_n=5, base_url=DEFAULT_FEED_URL, auto_sync=True):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk, self.root = tk, ttk, root
        self.data = None
        self.visible_notices = []
        self.eligible_active_notices = []
        self.notice_cards = {}
        self.expanded = set()
        self.matches = {}
        self.results = []
        self.selected_notice_id = None
        self.detail_notice = None
        self._seen = {}
        self._seen_error = False
        self._closed = False
        self._busy = False
        self._generation = 0
        self._events = queue.Queue()
        self._jobs = set()
        self._dots = []
        self._source_widgets = {}
        self._source_document = None
        self._source_cached = False
        self.database_error = True
        self.connection_state = 'CHECKING'
        self._last_sync = None
        self.cache_path = tk.StringVar(root, str(cache_path))
        self.database_path = tk.StringVar(root, str(database_path))
        self.base_url = tk.StringVar(root, base_url)
        self._load_seen()
        self.reference_year = tk.StringVar(root, str(reference_year))
        self.top_n = tk.StringVar(root, str(top_n))
        self.query = tk.StringVar(root)
        self.status = tk.StringVar(root, '중앙 공고를 확인하고 있습니다.')
        self.github_text = tk.StringVar(root, '확인 중')
        self.github_detail = tk.StringVar(root, '앱을 준비했습니다. GitHub 중앙 feed 확인을 시작합니다.')
        self.count_text = tk.StringVar(root, '공고를 불러오는 중')
        self.db_text = tk.StringVar(root, '실적 DB 확인 중')
        self._upload_dialog = None
        self._management_dialog = None
        root.title('Notice · 업무 모니터링 대시보드')
        root.geometry('1380x940')
        root.minsize(1040, 760)
        root.configure(bg=BG)
        self._theme()
        self.background = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.background.place(x=0, y=0, relwidth=1, relheight=1)
        self.background.bind('<Configure>', self._gradient)
        self.shell = tk.Frame(root, bg=BG)
        self.shell.place(x=28, y=22, relwidth=1, width=-56, relheight=1, height=-42)
        self.shell.columnconfigure(0, weight=1)
        self.shell.rowconfigure(4, weight=1)

        masthead = tk.Frame(self.shell, bg=BG)
        masthead.grid(row=0, column=0, sticky='ew', pady=(0, 17))
        self.label(masthead, 'NOTICE  /  INTELLIGENCE', bg=BG, size=11, color=MUTED, bold=True).pack(side='left')
        self.button(masthead, '설정 · 정보', self.open_settings).pack(side='right')
        self.label(masthead, 'CENTRAL MONITOR', bg=BG, size=9, color='#596575').pack(side='right', padx=20)

        github = self.card(self.shell)
        github.grid(row=1, column=0, sticky='ew', pady=(0, 14))
        line = tk.Frame(github, bg=CARD)
        line.pack(fill='x', padx=22, pady=(16, 6))
        self.label(line, 'GitHub Central Feed', size=15, bold=True).pack(side='left')
        self.sync_button = self.button(line, '지금 동기화 ↻', self.start_sync)
        self.sync_button.pack(side='right', padx=(18, 0))
        self.github_status_label = self.label(line, variable=self.github_text, size=11, color=YELLOW)
        self.github_status_label.pack(side='right', padx=(8, 0))
        self.github_dot = self.dot(line, YELLOW)
        self.github_dot.pack(side='right')
        self.label(github, variable=self.github_detail, color=MUTED, size=10).pack(anchor='w', padx=22, pady=(0, 16))

        sources = tk.Frame(self.shell, bg=BG)
        sources.grid(row=2, column=0, sticky='ew', pady=(0, 22))
        for index, (source, name) in enumerate(SOURCES.items()):
            sources.columnconfigure(index, weight=1, uniform='sources')
            card = self.card(sources)
            card.grid(row=0, column=index, sticky='nsew', padx=(0 if index == 0 else 5, 0 if index == 6 else 5))
            name_label = self.label(card, name, size=10, bold=True, wrap=145)
            name_label.pack(anchor='w', padx=12, pady=(13, 3))
            card.bind('<Configure>', lambda event, label=name_label: label.configure(wraplength=max(80, event.width-26)))
            self.label(card, source, size=8, color='#687586').pack(anchor='w', padx=12)
            state = tk.Frame(card, bg=CARD)
            state.pack(fill='x', padx=12, pady=(11, 2))
            dot = self.dot(state, MUTED)
            dot.pack(side='left')
            label = self.label(state, '상태 정보 없음', size=9, color=MUTED)
            label.pack(side='left', padx=(4, 0))
            stamp = self.label(card, '마지막 중앙 수집', size=8, color='#687586')
            stamp.pack(anchor='w', padx=12, pady=(0, 13))
            self._source_widgets[source] = (dot, label, stamp)
            def link_widgets(widget, source=source):
                widget.configure(cursor='hand2')
                widget.bind('<Button-1>', lambda event, s=source: self.open_source(s))
                for child in widget.winfo_children():
                    link_widgets(child, source)
            link_widgets(card)

        heading = tk.Frame(self.shell, bg=BG)
        heading.grid(row=3, column=0, sticky='ew', pady=(0, 12))
        self.label(heading, '지원가능 공고', bg=BG, size=22, bold=True).pack(side='left')
        self.label(heading, variable=self.count_text, bg=BG, size=10, color=MUTED).pack(side='left', padx=16)
        self.label(heading, '특허법인 참여 가능 · 현재 유효', bg=BG, size=9, color='#687586').pack(side='right')

        self.content = tk.Frame(self.shell, bg=BG)
        self.content.grid(row=4, column=0, sticky='nsew')
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(1, weight=1)
        toolbar = tk.Frame(self.content, bg=BG)
        toolbar.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 12))
        search = self.entry(toolbar, self.query, width=26)
        search.pack(side='left', ipady=5)
        search.bind('<Return>', lambda event: self.filter_notices())
        self.button(toolbar, '검색', self.filter_notices).pack(side='left', padx=(6, 18))
        self.label(toolbar, '매칭 기준 연도', bg=BG, size=9, color=MUTED).pack(side='left')
        self.entry(toolbar, self.reference_year, width=6).pack(side='left', padx=(8, 14), ipady=5)
        self.label(toolbar, 'TOP N', bg=BG, size=9, color=MUTED).pack(side='left')
        self.entry(toolbar, self.top_n, width=4).pack(side='left', padx=8, ipady=5)
        self.upload_button = self.button(toolbar, '실적 업로드', self.open_upload)
        self.upload_button.pack(side='left', padx=(12, 0))
        self.management_button = self.button(toolbar,'실적 관리',self.open_management)
        self.management_button.pack(side='left',padx=(8,0))
        self.label(toolbar, variable=self.db_text, bg=BG, size=9, color=MUTED).pack(side='right')
        self.canvas = tk.Canvas(self.content, bg=BG, highlightthickness=0, bd=0)
        self.canvas.grid(row=1, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(self.content, orient='vertical', command=self.canvas.yview)
        scrollbar.grid(row=1, column=1, sticky='ns', padx=(8, 0))
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.body = tk.Frame(self.canvas, bg=BG)
        self._body_id = self.canvas.create_window((0, 0), window=self.body, anchor='nw')
        self.body.bind('<Configure>', lambda event: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda event: self.canvas.itemconfigure(self._body_id, width=event.width))
        root.bind('<MouseWheel>', self._wheel, add='+')
        self.label(self.shell, variable=self.status, bg=BG, color='#748092', size=9).grid(row=5, column=0, sticky='w', pady=(13, 0))
        for variable in (self.reference_year, self.top_n):
            variable.trace_add('write', self._invalidate_matches)
        root.bind('<Destroy>', self._destroyed, add='+')
        self._render_list()
        self._schedule(80, self._pulse)
        self._schedule(100, self._poll)
        self._schedule(60000, self._retention_tick)
        if auto_sync:
            self._schedule(60, self.start_sync)
        else:
            self._apply_local(read_local(self.cache_path.get(), self.database_path.get(), self.base_url.get()))

    def _theme(self):
        style = self.ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('Vertical.TScrollbar', background=LINE, troughcolor=BG, bordercolor=BG,
                        arrowcolor=MUTED, lightcolor=LINE, darkcolor=LINE)
        self.root.option_add('*Font', (FONT, 10))

    def label(self, parent, text=None, *, variable=None, size=10, color=TEXT, bg=CARD, bold=False, wrap=None):
        options = dict(bg=bg, fg=color, font=(FONT, size, 'bold' if bold else 'normal'),
                       anchor='w', justify='left', bd=0)
        if variable is not None:
            options['textvariable'] = variable
        else:
            options['text'] = text
        if wrap:
            options['wraplength'] = wrap
        label = self.tk.Label(parent, **options)
        if wrap:
            parent.bind('<Configure>', lambda event, target=label: target.configure(wraplength=max(80, event.width-48)), add='+')
        return label

    def button(self, parent, text, command):
        return self.tk.Button(parent, text=text, command=command, bg='#20262f', fg=TEXT,
                              activebackground='#2a3039', activeforeground=TEXT, relief='flat',
                              bd=0, padx=13, pady=7, cursor='hand2', font=(FONT, 9),
                              highlightthickness=1, highlightbackground=LINE, highlightcolor=ORANGE)

    def entry(self, parent, variable, width=24):
        return self.tk.Entry(parent, textvariable=variable, width=width, bg=INNER, fg=TEXT,
                             insertbackground=TEXT, relief='flat', highlightthickness=1,
                             highlightbackground=LINE, highlightcolor=ORANGE, font=(FONT, 10))

    def card(self, parent):
        frame = self.tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        # Four restrained bands imitate light falling underneath the card.
        glow = self.tk.Frame(frame, bg=CARD, height=4)
        glow.pack(side='bottom', fill='x')
        for color in ('#211e1d', '#2a221e', '#30241e', '#251f1d'):
            self.tk.Frame(glow, height=1, bg=color).pack(fill='x')
        return frame

    def dot(self, parent, color):
        canvas = self.tk.Canvas(parent, width=14, height=16, bg=CARD, highlightthickness=0)
        canvas.create_oval(3, 4, 11, 12, fill=color, outline='', tags='light')
        canvas.light_color = color
        self._dots.append(canvas)
        return canvas

    def _gradient(self, event):
        self.background.delete('gradient')
        for i in range(80):
            t = i / 79
            color = blend('#0b0d10', '#111419', t*2) if t <= .5 else blend('#111419', '#08090b', (t-.5)*2)
            self.background.create_rectangle(0, i*event.height/80, event.width, (i+1)*event.height/80+1,
                                             fill=color, outline='', tags='gradient')

    def _schedule(self, delay, callback):
        if self._closed:
            return
        holder = []
        def run():
            self._jobs.discard(holder[0])
            if not self._closed:
                callback()
        holder.append(self.root.after(delay, run))
        self._jobs.add(holder[0])

    def _pulse(self):
        # Two-second rise/fall; never turns a light off.
        brightness = .78 + .22 * (math.sin(time.monotonic()*math.pi/2)+1)/2
        for dot in self._dots:
            dot.itemconfigure('light', fill=blend(CARD, dot.light_color, brightness))
        self._schedule(80, self._pulse)

    def _destroyed(self, event):
        if event.widget is self.root:
            self.close()

    def close(self):
        self._closed = True
        self._generation += 1
        for job in tuple(self._jobs):
            self.root.after_cancel(job)
        self._jobs.clear()

    def _wheel(self, event):
        if event.widget.winfo_toplevel() is self.root:
            self.canvas.yview_scroll(-int(event.delta / 120), 'units')

    def start_sync(self):
        if self._closed or self._busy:
            return
        self._busy = True
        self.sync_button.configure(state='disabled')
        self.set_connection('CHECKING')
        token = self._generation
        base, cache, database = self.base_url.get(), self.cache_path.get(), self.database_path.get()
        # Capture Tk variables here. Worker threads never access Tk objects.
        def work():
            try:
                local = read_local(cache, database, base)
                self._events.put((token, 'local', local))
                result = sync_monitor(base, cache, database)
                self._events.put((token, 'feed', result))
                if result.data is not None:
                    self._events.put((token, 'sources', read_sources(base, cache)))
            except Exception:
                self._events.put((token, 'feed', MonitorResult('ERROR', None, error_code='SYNC_ERROR')))
            finally:
                self._events.put((token, 'done', None))
        threading.Thread(target=work, name='notice-feed-sync', daemon=True).start()

    def _poll(self):
        try:
            while True:
                token, kind, result = self._events.get_nowait()
                if token != self._generation:
                    continue
                if kind == 'local':
                    self._apply_local(result)
                elif kind == 'feed':
                    self._apply_feed(result)
                elif kind == 'sources':
                    self._source_document, self._source_cached = result
                    self._render_sources()
                elif kind == 'retained' and result is not None:
                    if self.data is None or result.data.snapshot != self.data.snapshot:
                        self._apply_data(result)
                elif kind == 'performances':
                    self._apply_performances(*result)
                elif kind == 'done':
                    self._busy = False
                    self.sync_button.configure(state='normal')
                    if getattr(self, '_performance_reload_pending', False):
                        self._performance_reload_pending = False
                        self.reload_performances(self.database_path.get())
        except queue.Empty:
            pass
        self._schedule(100, self._poll)

    def _apply_local(self, result):
        if result:
            self._apply_data(result)
            if not self._busy:
                self.set_connection('FALLBACK')

    def _apply_feed(self, result):
        if result.data is not None:
            self._apply_data(result)
        elif self.data is not None:
            # Unexpected optional worker failures must not erase valid rows.
            result = MonitorResult('FALLBACK', self.data, database_error=self.database_error)
        self._last_sync = result.checked_at or self._last_sync
        self.set_connection(result.connection)
        if result.data is None:
            self.status.set('GitHub 연결 실패 · 사용 가능한 저장 데이터가 없습니다. 네트워크와 설정을 확인해 주세요.')
            self._render_list()

    def _apply_data(self, result):
        self.data = result.data
        self.database_error = result.database_error
        self.matches.clear()
        self.db_text.set('실적 DB 미연결 · 설정에서 연결' if self.database_error else f'로컬 실적 {len(self.data.performances):,}건 연결')
        self.filter_notices()

    def set_connection(self, state):
        self.connection_state = state
        color, text = {
            'CHECKING': (YELLOW, '확인 중'),
            'FALLBACK': (YELLOW, '마지막 저장 데이터 사용 중'),
            'ERROR': (RED, 'GitHub 연결 실패'),
        }.get(state, (BLUE, 'GitHub 연결 정상'))
        self.github_text.set(text)
        self.github_status_label.configure(fg=color)
        self.github_dot.light_color = color
        if state == 'CHECKING':
            detail = '동기화 중 · 저장된 공고가 있으면 먼저 표시합니다.'
        elif state == 'FALLBACK':
            detail = '마지막 저장 데이터 사용 중 · 중앙 최신 상태는 확인하지 못했습니다.'
        elif state == 'ERROR':
            detail = '연결 실패 · 사용할 수 있는 캐시가 없습니다. 잠시 후 다시 동기화해 주세요.'
        else:
            detail = f'마지막 동기화 {display_stamp(self._last_sync)}  ·  최신 공고 확인 완료'
        if self.data and state != 'CHECKING':
            detail += f"  /  중앙 feed 생성 {display_stamp(self.data.snapshot['metadata']['generated_at'])}"
        self.github_detail.set(detail)

    def _render_sources(self):
        records = {r['source_id']: r for r in self._source_document['sources']} if self._source_document else {}
        for source, (dot, label, stamp) in self._source_widgets.items():
            row = records.get(source)
            state = row['status'] if row else 'UNKNOWN'
            color, text = {'SUCCESS': (GREEN, '수집 정상'), 'ERROR': (RED, '수집 오류')}.get(state, (MUTED, '상태 정보 없음'))
            dot.light_color = color
            count = sum(n['source_id'] == source for n in self.eligible_active_notices)
            label.configure(text=text + (' · 저장 상태' if self._source_cached else ''), fg=color)
            stamp.configure(text=f'지원가능 {count}건')

    def _invalidate_matches(self, *args):
        self.matches.clear()
        self.results = []
        if self.detail_notice:
            self.show_detail(self.detail_notice, mark_seen=False)
        else:
            self._render_list()

    def filter_notices(self):
        if self.data:
            self.eligible_active_notices = notice_rows(self.data)
            query = self.query.get().strip().casefold()
            filtered = [n for n in self.eligible_active_notices if not query or query in
                        ' '.join(str(n[k] or '') for k in ('title','institution','category','participation_type','summary','keywords')).casefold()]
            self.visible_notices = ordered_notices(filtered, generated_at=self.data.snapshot['feed']['generated_at'])
        else:
            self.eligible_active_notices = []
            self.visible_notices = []
        self._render_sources()
        if self.detail_notice:
            notice = next((n for n in self.data.snapshot['feed']['notices'] if n['notice_id'] == self.detail_notice['notice_id']), None) if self.data else None
            if notice:
                self.show_detail(notice, mark_seen=False)
            else:
                self.show_list()
        else:
            self._render_list()

    def _clear_body(self):
        for child in self.body.winfo_children():
            child.destroy()
        self.notice_cards = {}

    def _render_list(self):
        self._clear_body()
        self.count_text.set(f'총 {len(self.eligible_active_notices):,}건' +
                            (f'  /  검색 결과 {len(self.visible_notices):,}건' if self.query.get().strip() else ''))
        if not self.visible_notices:
            card = self.card(self.body)
            card.pack(fill='x', pady=(0, 10))
            text = ('GitHub 연결 실패 · 저장된 공고가 없습니다.' if self.connection_state == 'ERROR' else
                    ('검색 조건에 맞는 공고가 없습니다.' if self.query.get().strip() else '현재 공개된 공고가 없습니다.')
                    if self.data else '중앙 공고를 확인하고 있습니다.')
            self.label(card, text, size=13).pack(anchor='w', padx=24, pady=(26, 8))
            self.label(card, '지금 동기화 또는 설정에서 연결 정보를 확인할 수 있습니다.', color=MUTED).pack(anchor='w', padx=24, pady=(0, 26))
        for notice in self.visible_notices:
            self._notice_card(notice)
        self.status.set('공고 제목을 눌러 상세 보기  ·  실적 매칭은 로컬 PC에서만 계산합니다.')
        if self._seen_error:
            self.status.set('확인 이력을 읽거나 저장하지 못했습니다. 확인 상태가 재실행 후 유지되지 않을 수 있습니다.')

    def _notice_card(self, notice):
        card = self.card(self.body)
        card.pack(fill='x', pady=(0, 6))
        badge = notice_badge(notice, generated_at=self.data.snapshot['feed']['generated_at'])
        top = self.tk.Frame(card, bg=CARD)
        top.pack(fill='x', padx=16, pady=(6, 1))
        if badge == 'NEW':
            self.label(top, 'NEW', size=8, color=ORANGE, bold=True).pack(side='left', padx=(0, 8))
        self.label(top, notice['institution'], size=10, color=MUTED).pack(side='left')
        self.label(top, notice.get('participation_type') or '참여 형태 미제공', size=9, color=MUTED).pack(side='right')
        title = self.label(card, notice['title'], size=13, bold=True, wrap=1100)
        title.pack(anchor='w', fill='x', padx=16, pady=(0, 1))
        title.configure(cursor='hand2')
        title.bind('<Button-1>', lambda event, n=notice: self.show_detail(n))
        card.bind('<Button-1>', lambda event, n=notice: self.show_detail(n))
        footer = self.tk.Frame(card, bg=CARD)
        footer.pack(fill='x', padx=16, pady=(0, 5))
        from src.core.eligibility import deadline_date
        end = deadline_date(notice.get('apply_end'))
        deadline = f'마감 {end.isoformat()}' if end else '마감 미확인'
        reason = notice['relevance_reason'].replace('\n', ' ')[:90]
        self.label(footer, deadline + ' · ' + reason, size=9, color=MUTED).pack(side='left')
        button = self.button(footer, '실적 매칭 펼쳐보기  ▾', lambda n=notice: self.toggle_match(n['notice_id']))
        button.pack(side='right')
        panel = self.tk.Frame(card, bg=INNER)
        self.notice_cards[notice['notice_id']] = dict(card=card, panel=panel, button=button, notice=notice)
        if notice['notice_id'] in self.expanded:
            card.configure(highlightbackground='#634b38')
            panel.pack(fill='x', padx=1, pady=(0, 1))
            button.configure(text='실적 매칭 접기  ▴')
            self._render_matches(panel, notice)

    @staticmethod
    def period(notice):
        return f"접수  {notice.get('apply_start') or '시작일 미제공'}  —  {notice.get('apply_end') or '마감일 미제공'}"

    def toggle_match(self, notice_id):
        row = self.notice_cards[notice_id]
        if notice_id in self.expanded:
            self.expanded.remove(notice_id)
            row['panel'].pack_forget()
            row['button'].configure(text='실적 매칭 펼쳐보기  ▾')
            row['card'].configure(highlightbackground=LINE)
        else:
            self.expanded.add(notice_id)
            row['panel'].pack(fill='x', padx=1, pady=(0, 1))
            row['button'].configure(text='실적 매칭 접기  ▴')
            row['card'].configure(highlightbackground='#634b38')
            self._render_matches(row['panel'], row['notice'])

    def _render_matches(self, parent, notice):
        self.results = []
        for child in parent.winfo_children():
            child.destroy()
        self.label(parent, '우리 실적 매칭', bg=INNER, size=11, bold=True).pack(anchor='w', padx=22, pady=(17, 5))
        if self.database_error:
            self.label(parent, '실적 DB 미연결 또는 읽기 실패 · 실적 업로드로 추가하거나 설정에서 기존 DB를 연결하세요.',
                       bg=INNER, color=MUTED).pack(anchor='w', padx=22, pady=(3, 20))
            return
        if not self.data.performances:
            self.label(parent, '등록된 실적이 없습니다.\n실적 업로드를 통해 데이터를 추가하세요.',
                       bg=INNER, color=MUTED).pack(anchor='w', padx=22, pady=(3, 20))
            return
        try:
            key = (notice['notice_id'], self.reference_year.get(), self.top_n.get())
            if key not in self.matches:
                self.matches[key] = recommendation_rows(self.data, notice['notice_id'], reference_year=key[1], top_n=key[2])
            rows = self.matches[key]
        except DashboardError as error:
            message = '매칭 기준 연도를 1~9999의 정수로 입력해 주세요.' if str(error) == 'INVALID_REFERENCE_YEAR' else 'TOP N을 0 이상의 정수로 입력해 주세요.'
            self.label(parent, message, bg=INNER, color=YELLOW).pack(anchor='w', padx=22, pady=(3, 20))
            return
        self.results = rows
        if notice['notice_id'] in self.notice_cards:
            self.notice_cards[notice['notice_id']]['button'].configure(text=f'실적 매칭 접기 · {len(rows)}건  ▴')
        if not rows:
            text = ('등록된 실적이 없습니다.\n실적 업로드를 통해 데이터를 추가하세요.' if not self.data.performances
                    else '매칭 결과 없음 · TOP N이 0입니다.')
            self.label(parent, text, bg=INNER, color=MUTED).pack(anchor='w', padx=22, pady=(3, 20))
        for row in rows:
            block = self.tk.Frame(parent, bg=INNER)
            block.pack(fill='x', padx=22, pady=(8, 12))
            headline = self.tk.Frame(block, bg=INNER)
            headline.pack(fill='x', pady=(0, 7))
            headline.columnconfigure(0, weight=1)
            self.label(headline, f"{row['ranking']:02d}   {row['project_name']}", bg=INNER, size=11, bold=True, wrap=950).grid(row=0, column=0, sticky='w')
            self.label(headline, f"{row['total_score']}점", bg=INNER, size=13, bold=True).grid(row=0, column=1, sticky='ne', padx=(15, 0))
            # Public matcher output only: no client, notes, attorney or private SQL fields.
            explanation = recommendation_details(row).split('\n')[2:]
            self.label(block, '\n'.join(explanation), bg=INNER, size=9, color=MUTED, wrap=1080).pack(anchor='w')
        self.status.set(f"이 공고의 매칭 {len(rows)}건  ·  기준 연도 {self.reference_year.get()}  ·  계산 방식은 기존 matcher와 동일합니다.")

    def _load_seen(self):
        try:
            path = seen_path(self.cache_path.get())
            if path.resolve() == Path(self.database_path.get()).resolve():
                raise SeenStateError('PATH_COLLISION')
            self._seen_store = SeenStore(path, self.base_url.get())
            self._seen = self._seen_store.load()
            self._seen_error = False
        except (SeenStateError, ValueError, OSError, SyncError):
            self._seen = {}
            self._seen_error = True
            self._seen_store = None

    def mark_seen(self, notice, *, refresh=True):
        try:
            if self._seen_store is None:
                raise SeenStateError('SEEN_UNAVAILABLE')
            self._seen = self._seen_store.mark(notice)
            self._seen_error = False

        except SeenStateError:
            self._seen_error = True
        if refresh:
            self.filter_notices()

    def _retention_tick(self):
        # Pruning shares the sync worker; no disk/network wait on the Tk thread.
        if not self._busy:
            self._busy = True
            self.sync_button.configure(state='disabled')
            token = self._generation
            cache, database, base = self.cache_path.get(), self.database_path.get(), self.base_url.get()
            def work():
                try:
                    self._events.put((token, 'retained', read_local(cache, database, base)))
                finally:
                    self._events.put((token, 'done', None))
            threading.Thread(target=work, name='notice-retention', daemon=True).start()
        self._schedule(60000, self._retention_tick)

    def show_detail(self, notice, *, mark_seen=True):
        if mark_seen:
            self.mark_seen(notice, refresh=False)
        self.detail_notice = notice
        self.selected_notice_id = notice['notice_id']
        self._clear_body()
        top = self.tk.Frame(self.body, bg=BG)
        top.pack(fill='x', pady=(0, 12))
        self.button(top, '← 공고 목록으로', self.show_list).pack(side='left')
        self.button(top, '원문 보기 ↗', lambda: self.open_original(notice)).pack(side='right')
        card = self.card(self.body)
        card.pack(fill='x', pady=(0, 14))
        self.label(card, notice['institution'], color=MUTED, size=11).pack(anchor='w', padx=24, pady=(23, 8))
        self.label(card, notice['title'], size=19, bold=True, wrap=1120).pack(anchor='w', padx=24, pady=(0, 12))
        self.label(card, self.period(notice), color=MUTED).pack(anchor='w', padx=24, pady=(0, 25))
        for label, value in (('공고 요약', notice['summary']), ('분류 · 참여 형태', f"{notice['category']}  /  {notice['participation_type']}"),
                             ('키워드', '   ·   '.join(notice['keywords'])), ('참여 관련성', notice['relevance_reason'])):
            self.label(card, label, size=10, color=MUTED, bold=True).pack(anchor='w', padx=24, pady=(10, 7))
            self.label(card, value or '공개 feed에 제공된 내용이 없습니다.', size=11, wrap=1120).pack(anchor='w', padx=24, pady=(0, 15))
        self.label(card, '공개 중앙 feed의 정보만 표시합니다. 첨부파일과 원문 전체는 원문 보기에서 확인하세요.',
                   size=9, color='#687586', wrap=1100).pack(anchor='w', padx=24, pady=(5, 23))
        matches = self.tk.Frame(self.body, bg=INNER, highlightbackground=LINE, highlightthickness=1)
        matches.pack(fill='x', pady=(0, 12))
        self._render_matches(matches, notice)
        self.canvas.yview_moveto(0)
        if self._seen_error:
            self.status.set('확인 상태를 저장하지 못했습니다. 저장 경로와 권한을 확인해 주세요.')

    def show_list(self):
        self.detail_notice = None
        self.selected_notice_id = None
        self.filter_notices()
        self.canvas.yview_moveto(0)

    def open_original(self, notice):
        if safe_original_url(notice['url']):
            webbrowser.open(notice['url'], new=2)

    def open_source(self, source):
        url = source_list_url(source)
        if url:
            webbrowser.open(url, new=2)

    def open_upload(self):
        from .upload_ui import UploadDialog
        if self._upload_dialog is not None and not self._upload_dialog._closed:
            self._upload_dialog.dialog.lift()
            return
        self._upload_dialog = UploadDialog(self)
        self._upload_dialog.choose_file()

    def reload_performances(self, database_path):
        from .monitor import read_database
        database_path = Path(database_path).resolve()
        token = self._generation
        if self._busy:
            self._performance_reload_pending = True
        def work():
            records, error = read_database(database_path)
            self._events.put((token, 'performances', (database_path, records, error)))
        threading.Thread(target=work, name='local-performance-reload', daemon=True).start()

    def open_management(self):
        from .performance_management_ui import PerformanceManagementDialog
        if self._management_dialog is not None and not self._management_dialog._closed:
            self._management_dialog.dialog.lift()
            self._management_dialog.refresh()
            return
        self._management_dialog = PerformanceManagementDialog(self)

    def _apply_performances(self, database_path, records, error):
        from .dashboard import DashboardData
        if Path(self.database_path.get()).resolve() != Path(database_path).resolve():
            self.status.set('실적 변경 완료 · 저장한 DB는 현재 설정과 다릅니다. 설정에서 해당 DB를 연결하세요.')
            return
        self.database_error = error
        self.db_text.set('실적 DB 읽기 실패 · 설정에서 확인' if error else f'로컬 실적 {len(records):,}건 연결')
        if self.data is not None:
            self.data = DashboardData(self.data.snapshot, records)
            self.matches.clear()
            self.results = []
            self.filter_notices()
        self.status.set('실적 변경 반영 · 로컬 매칭 데이터를 갱신했습니다.' if not error else '변경 후 DB를 읽지 못했습니다.')
        if self._management_dialog is not None and not self._management_dialog._closed and self._management_dialog.database_path == Path(database_path).resolve():
            self._management_dialog.refresh()

    def open_settings(self):
        dialog = self.tk.Toplevel(self.root)
        dialog.title('연결 · 로컬 데이터 설정')
        dialog.configure(bg=CARD)
        dialog.geometry('760x360')
        dialog.transient(self.root)
        fields = []
        for title, current in (('GitHub 공개 feed 주소', self.base_url), ('공고 캐시 파일', self.cache_path), ('로컬 실적 DB (읽기 전용)', self.database_path)):
            self.label(dialog, title, color=MUTED).pack(anchor='w', padx=22, pady=(16, 6))
            value = self.tk.StringVar(dialog, current.get())
            self.entry(dialog, value, width=85).pack(fill='x', padx=22, ipady=5)
            fields.append(value)
        self.label(dialog, '기관 사이트에는 직접 접속하지 않습니다. 개인 실적은 로컬에서만 읽습니다.', size=9, color=MUTED).pack(anchor='w', padx=22, pady=16)
        def apply():
            if self._busy:
                self.status.set('동기화가 끝난 후 설정을 적용해 주세요.')
                return
            self._generation += 1
            for current, value in zip((self.base_url, self.cache_path, self.database_path), fields):
                current.set(value.get().strip())
            self.data = None
            self._load_seen()
            self.expanded.clear()
            self.matches.clear()
            self._source_document = None
            self._source_cached = False
            self._render_sources()
            self.detail_notice = None
            self.visible_notices = []
            self._render_list()
            dialog.destroy()
            self.start_sync()
        self.button(dialog, '적용 후 동기화', apply).pack(anchor='e', padx=22)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Dark Night 업무용 공고 모니터링 대시보드')
    parser.add_argument('--cache', default=DEFAULT_CACHE_DIR/'snapshot.json')
    parser.add_argument('--db', default=DEFAULT_DB_PATH)
    parser.add_argument('--base-url', default=DEFAULT_FEED_URL)
    parser.add_argument('--reference-year', default='', help='매칭 기준 연도를 직접 지정')
    parser.add_argument('--top-n', default=5)
    parser.add_argument('--offline', action='store_true', help='네트워크 없이 기존 캐시만 표시')
    args = parser.parse_args(argv)
    try:
        import tkinter as tk
    except ImportError:
        return 2
    try:
        root = tk.Tk()
    except tk.TclError:
        return 2
    window = None
    try:
        window = DashboardWindow(root, cache_path=args.cache, database_path=args.db, reference_year=args.reference_year,
                                 top_n=args.top_n, base_url=args.base_url, auto_sync=not args.offline)
        root.protocol('WM_DELETE_WINDOW', root.quit)
        root.mainloop()
    finally:
        if window:
            window.close()
        root.destroy()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
