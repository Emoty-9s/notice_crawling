"""M15 offline Tk desktop UI. Launch: python -m src.local_client.ui."""

import argparse

from .dashboard import (DashboardError, load_dashboard, notice_details, notice_rows,
                        recommendation_details, recommendation_rows)
from .performance import DEFAULT_DB_PATH
from .sync import DEFAULT_CACHE_DIR


ERROR_MESSAGES = {
    'INVALID_OR_MISSING_CACHE': '정상 M12 cache 파일을 읽을 수 없습니다. 파일 위치와 JSON을 확인하세요.',
    'INVALID_OR_MISSING_DATABASE': '정상 M13 DB를 읽을 수 없습니다. 기존 DB 파일 위치와 schema를 확인하세요.',
    'INVALID_REFERENCE_YEAR': '기준 연도를 1~9999의 정수로 직접 입력하세요.',
    'INVALID_TOP_N': 'TOP N은 0 이상의 정수로 입력하세요.',
    'SELECT_NOTICE': '목록에서 공고를 선택하세요.',
    'MATCH_INPUT_ERROR': '공고 또는 실적의 매칭 입력을 확인하세요.',
}


class DashboardWindow:
    def __init__(self, root, *, cache_path=DEFAULT_CACHE_DIR/'snapshot.json', database_path=DEFAULT_DB_PATH,
                 reference_year='', top_n=5):
        import tkinter as tk
        from tkinter import ttk
        from tkinter.scrolledtext import ScrolledText

        self.root = root
        self.data = None
        self.visible_notices = []
        self.results = []
        self.selected_notice_id = None
        root.title('공고 · 로컬 실적 매칭')
        root.geometry('1250x850')
        root.minsize(900, 650)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)

        self.cache_path = tk.StringVar(root, str(cache_path))
        self.database_path = tk.StringVar(root, str(database_path))
        self.reference_year = tk.StringVar(root, str(reference_year))
        self.top_n = tk.StringVar(root, str(top_n))
        self.query = tk.StringVar(root)
        self.institution = tk.StringVar(root)
        self.category = tk.StringVar(root)
        self.status = tk.StringVar(root, '로컬 파일만 읽습니다. 기준 연도는 직접 입력하세요.')
        self.cache_status = tk.StringVar(root, 'cache 미로드')
        self.result_status = tk.StringVar(root, '공고를 선택하고 매칭 실행을 누르세요.')

        files = ttk.LabelFrame(root, text='로컬 데이터 (읽기 전용)', padding=8)
        files.grid(row=0, column=0, sticky='ew', padx=10, pady=8)
        files.columnconfigure(1, weight=1)
        for index, (label, variable) in enumerate((('M12 snapshot 파일', self.cache_path), ('M13 실적 DB', self.database_path))):
            ttk.Label(files, text=label).grid(row=index, column=0, sticky='w', padx=4)
            ttk.Entry(files, textvariable=variable).grid(row=index, column=1, sticky='ew', padx=5, pady=3)
        ttk.Button(files, text='파일 다시 읽기', command=self.reload).grid(row=0, column=2, rowspan=2, padx=6)
        ttk.Label(files, textvariable=self.cache_status).grid(row=2, column=0, columnspan=3, sticky='w', pady=4)

        filters = ttk.Frame(root, padding=(10, 0))
        filters.grid(row=1, column=0, sticky='ew')
        ttk.Label(filters, text='기관 (빈 값=전체)').pack(side='left')
        self.institution_box = ttk.Combobox(filters, textvariable=self.institution, state='readonly', width=18)
        self.institution_box.pack(side='left', padx=5)
        ttk.Label(filters, text='category').pack(side='left')
        self.category_box = ttk.Combobox(filters, textvariable=self.category, state='readonly', width=16)
        self.category_box.pack(side='left', padx=5)
        ttk.Label(filters, text='검색').pack(side='left')
        search_entry = ttk.Entry(filters, textvariable=self.query, width=24)
        search_entry.pack(side='left', padx=5)
        ttk.Button(filters, text='필터 적용', command=self.filter_notices).pack(side='left')
        search_entry.bind('<Return>', lambda event: self.filter_notices())

        controls = ttk.Frame(root, padding=10)
        controls.grid(row=2, column=0, sticky='ew')
        ttk.Label(controls, text='기준 연도 (직접 입력)').pack(side='left')
        ttk.Entry(controls, textvariable=self.reference_year, width=8).pack(side='left', padx=6)
        ttk.Label(controls, text='TOP N').pack(side='left')
        ttk.Spinbox(controls, textvariable=self.top_n, from_=0, to=10000, width=7).pack(side='left', padx=6)
        ttk.Button(controls, text='매칭 실행', command=self.run_match).pack(side='left', padx=6)
        ttk.Label(controls, textvariable=self.result_status).pack(side='left', padx=8)

        panes = ttk.Panedwindow(root, orient='horizontal')
        panes.grid(row=3, column=0, sticky='nsew', padx=10)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=1)
        for frame in (left, right):
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
            frame.rowconfigure(3, weight=2)

        def tree(parent, columns, labels):
            container = ttk.Frame(parent)
            container.grid(row=1, column=0, sticky='nsew')
            container.columnconfigure(0, weight=1)
            container.rowconfigure(0, weight=1)
            widget = ttk.Treeview(container, columns=columns, show='headings', selectmode='browse', height=10)
            widget.grid(row=0, column=0, sticky='nsew')
            for name, label in zip(columns, labels):
                widget.heading(name, text=label)
                widget.column(name, width=90 if name != 'title' else 260, minwidth=60)
            scrollbar = ttk.Scrollbar(container, orient='vertical', command=widget.yview)
            scrollbar.grid(row=0, column=1, sticky='ns')
            horizontal = ttk.Scrollbar(container, orient='horizontal', command=widget.xview)
            horizontal.grid(row=1, column=0, sticky='ew')
            widget.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
            return widget

        ttk.Label(left, text='공고 목록').grid(row=0, column=0, sticky='w')
        self.notice_tree = tree(left, ('id', 'title', 'category'), ('공고 ID', '제목', 'category'))
        ttk.Label(left, text='선택 공고 상세').grid(row=2, column=0, sticky='w', pady=4)
        self.notice_text = ScrolledText(left, wrap='word', height=15, state='disabled', font=('맑은 고딕', 10))
        self.notice_text.grid(row=3, column=0, sticky='nsew')
        ttk.Label(right, text='추천 실적 (총점 내림차순 · 동점 ID 순)').grid(row=0, column=0, sticky='w')
        self.result_tree = tree(right, ('ranking', 'id', 'title', 'score'), ('순위', '실적 ID', '과제명', '총점'))
        ttk.Label(right, text='추천 선택 → 규칙별 점수와 근거').grid(row=2, column=0, sticky='w', pady=4)
        self.reason_text = ScrolledText(right, wrap='word', height=15, state='disabled', font=('맑은 고딕', 10))
        self.reason_text.grid(row=3, column=0, sticky='nsew')
        ttk.Label(root, textvariable=self.status, wraplength=1200, padding=10).grid(row=4, column=0, sticky='ew')

        self.notice_tree.bind('<<TreeviewSelect>>', self.select_notice)
        self.result_tree.bind('<<TreeviewSelect>>', self.select_result)
        for variable in (self.reference_year, self.top_n):
            variable.trace_add('write', lambda *args: self.clear_results())
        for variable in (self.cache_path, self.database_path):
            variable.trace_add('write', lambda *args: self.invalidate_data())
        self.reload()

    @staticmethod
    def _text(widget, value):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', value)
        widget.configure(state='disabled')

    def clear_results(self):
        self.results = []
        self.result_tree.delete(*self.result_tree.get_children())
        self._text(self.reason_text, '')
        self.result_status.set('공고를 선택하고 매칭 실행을 누르세요.')

    def invalidate_data(self):
        self.data = None
        self.clear_results()
        self.selected_notice_id = None
        self.visible_notices = []
        self.notice_tree.delete(*self.notice_tree.get_children())
        self._text(self.notice_text, '')
        self.cache_status.set('cache 미로드')
        self.status.set('로컬 파일 경로를 확인하고 파일 다시 읽기를 누르세요.')

    def reload(self):
        self.invalidate_data()
        try:
            self.data = load_dashboard(self.cache_path.get(), self.database_path.get())
        except DashboardError as error:
            self.status.set(ERROR_MESSAGES.get(str(error), '로컬 데이터 오류') + f' [{error}]')
            return
        notices = self.data.snapshot['feed']['notices']
        self.institution.set('')
        self.category.set('')
        self.institution_box.configure(values=[''] + sorted({row['institution'] for row in notices}))
        self.category_box.configure(values=[''] + sorted({row['category'] for row in notices}))
        stamp = self.data.snapshot['metadata']['generated_at']
        self.cache_status.set(f'검증된 로컬 cache | 생성 시각: {stamp} | 공고 {len(notices)}건 | 실적 {len(self.data.performances)}건')
        self.filter_notices()

    def filter_notices(self):
        self.clear_results()
        self.selected_notice_id = None
        self._text(self.notice_text, '')
        self.notice_tree.delete(*self.notice_tree.get_children())
        if self.data is None:
            return
        self.visible_notices = notice_rows(self.data, query=self.query.get(), institution=self.institution.get(), category=self.category.get())
        for index, row in enumerate(self.visible_notices):
            self.notice_tree.insert('', 'end', iid=str(index), values=(row['notice_id'], row['title'], row['category']))
        self.status.set(f'표시 공고 {len(self.visible_notices)}건. 공고 선택 → 기준 연도 입력 → 매칭 실행. 네트워크 호출 없음.')

    def select_notice(self, event=None):
        self.clear_results()
        selection = self.notice_tree.selection()
        if not selection:
            return
        notice = self.visible_notices[int(selection[0])]
        self.selected_notice_id = notice['notice_id']
        self._text(self.notice_text, notice_details(notice))

    def run_match(self):
        self.clear_results()
        if self.data is None:
            self.status.set('먼저 정상 cache와 실적 DB를 파일 다시 읽기로 불러오세요.')
            return
        try:
            self.results = recommendation_rows(self.data, self.selected_notice_id, reference_year=self.reference_year.get(), top_n=self.top_n.get())
        except DashboardError as error:
            self.status.set(ERROR_MESSAGES.get(str(error), '매칭 표시 오류') + f' [{error}]')
            return
        for index, row in enumerate(self.results):
            self.result_tree.insert('', 'end', iid=str(index), values=(row['ranking'], row['performance_id'], row['project_name'], row['total_score']))
        self.result_status.set(f'기준 연도 {self.reference_year.get()} | TOP {self.top_n.get()} | 결과 {len(self.results)}건')
        self.status.set('추천 결과를 선택하면 규칙별 점수와 합계를 확인할 수 있습니다.' if self.results else '추천 결과 없음 (빈 실적 DB 또는 TOP N=0).')
        if self.results:
            self.result_tree.selection_set('0')
            self.select_result()

    def select_result(self, event=None):
        selection = self.result_tree.selection()
        if selection:
            self._text(self.reason_text, recommendation_details(self.results[int(selection[0])]))


def main(argv=None):
    parser = argparse.ArgumentParser(description='M15 offline read-only local matching desktop UI.')
    parser.add_argument('--cache', default=DEFAULT_CACHE_DIR/'snapshot.json')
    parser.add_argument('--db', default=DEFAULT_DB_PATH)
    parser.add_argument('--reference-year', default='', help='Explicit year; otherwise input in the UI (no clock default)')
    parser.add_argument('--top-n', default=5)
    args = parser.parse_args(argv)
    try:
        import tkinter as tk
    except ImportError:
        print('UI ERROR: TK_UNAVAILABLE; use a Python installation with Tk support')
        return 2
    try:
        root = tk.Tk()
    except tk.TclError:
        print('UI ERROR: DISPLAY_UNAVAILABLE; a local desktop session is required')
        return 2
    try:
        DashboardWindow(root, cache_path=args.cache, database_path=args.db, reference_year=args.reference_year, top_n=args.top_n)
        root.protocol('WM_DELETE_WINDOW', root.quit)
        root.mainloop()
    finally:
        root.destroy()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
