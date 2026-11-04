"""Upload-only Tk dialog. Reading/saving runs in local worker threads."""
import queue
import threading
from pathlib import Path

from .upload import UploadError, preview_upload
from .upload_store import save_preview, save_enriched_preview
from .performance import PerformanceError
from .preview_selection import PreviewSelection, save_selected


ERROR_TEXT = {
    'UNSUPPORTED_EXTENSION': '지원하지 않는 확장자입니다. .xlsx, .xls, .csv 파일을 선택하세요.',
    'FILE_READ_FAILED': '파일을 열지 못했습니다. 손상·암호 설정·파일 권한을 확인하세요.',
    'CSV_ENCODING_FAILED': 'CSV 인코딩을 읽지 못했습니다. UTF-8 또는 CP949로 저장해 주세요.',
    'READER_NOT_INSTALLED': 'Excel 읽기 라이브러리가 없습니다. 최신 배포본을 사용해 주세요.',
    'NO_SHEET_DATA': 'sheet에 데이터가 없습니다.',
    'HEADER_NOT_FOUND': 'header를 찾지 못했습니다. 열 제목과 데이터가 있는 파일을 선택하세요.',
    'NO_VALID_ROWS': '저장할 실적 행이 없습니다.',
    'FILE_TOO_LARGE': '파일이 50MB를 초과합니다. 파일을 나누어 업로드하세요.',
    'WORKBOOK_LIMIT_EXCEEDED': '데이터 크기 제한을 초과했습니다. 파일을 나누어 업로드하세요.',
    'DATABASE_SAVE_FAILED': 'DB 저장에 실패했습니다. DB 경로·권한·다른 프로그램의 사용 여부를 확인하세요.',
    'PATH_COLLISION': '실적 DB 경로가 공고 cache·확인 이력 또는 업로드 파일과 겹칩니다. 설정에서 DB 경로를 바꾸세요.',
    'DATABASE_READ_FAILED': '기존 실적 DB를 읽지 못했습니다. DB 경로와 형식을 확인하세요.',
    'NO_PERFORMANCE_RECORDS': '등록된 실적이 없습니다. 실적 업로드를 통해 데이터를 추가하세요.',
    'NO_SELECTED_ROWS': '저장할 실적을 선택하세요.',
}


class UploadDialog:
    def __init__(self, app):
        from .ui import BG, CARD, INNER, LINE, TEXT, MUTED, FONT
        self.app, self.tk, self.ttk = app, app.tk, app.ttk
        self._closed = self._busy = False
        self._events = queue.Queue()
        self._job = None
        self.preview = None
        self.result = None
        self.file_path = None
        self._mode = 'import'
        self.selection = PreviewSelection()
        self.page = 0
        self._cancel = threading.Event()
        self.database_path = Path(app.database_path.get()).resolve()
        self.dialog = self.tk.Toplevel(app.root)
        self.dialog.title('실적 업로드')
        self.dialog.geometry('1320x840')
        self.dialog.minsize(1000, 690)
        self.dialog.configure(bg=BG)
        self.dialog.transient(app.root)
        self.dialog.protocol('WM_DELETE_WINDOW', self.close)
        self.dialog.bind('<Destroy>', self._destroyed, add='+')
        self.dialog.columnconfigure(0, weight=1)
        self.dialog.rowconfigure(3, weight=1)
        self.dialog.rowconfigure(4, weight=1)
        app.label(self.dialog, '실적 업로드', bg=BG, size=18, bold=True).grid(row=0, column=0, sticky='w', padx=22, pady=(20, 8))
        self.message = self.tk.StringVar(self.dialog, '파일을 선택하세요. 미리보기 확인 후 저장할 때만 로컬 DB에 반영합니다.')
        app.label(self.dialog, variable=self.message, bg=BG, color=MUTED, wrap=1050).grid(row=1, column=0, sticky='ew', padx=22, pady=(0, 8))
        actions = self.tk.Frame(self.dialog, bg=BG)
        actions.grid(row=2, column=0, sticky='ew', padx=22, pady=8)
        self.choose_button = app.button(actions, '파일 선택', self.choose_file)
        self.choose_button.pack(side='left')
        self.analyze_button = app.button(actions, '미분류 실적 분석', self.analyze_existing)
        self.analyze_button.pack(side='left', padx=8)
        self.force_analysis = self.tk.BooleanVar(self.dialog, False)
        self.tk.Checkbutton(actions, text='기존 AI 결과도 갱신', variable=self.force_analysis,
                            bg=BG, fg=TEXT, selectcolor=INNER, activebackground=BG,
                            activeforeground=TEXT).pack(side='left')
        self.cancel_button = app.button(actions, '분석 취소', self.cancel_analysis)
        self.cancel_button.pack(side='left', padx=8)
        self.cancel_button.configure(state='disabled')
        self.save_button = app.button(actions, '저장', self.save)
        self.save_button.configure(state='disabled')
        self.save_button.pack(side='right')
        app.button(actions, '닫기', self.close).pack(side='right', padx=8)
        table = self.tk.Frame(self.dialog, bg=BG)
        table.grid(row=3, column=0, sticky='nsew', padx=22, pady=6)
        table.rowconfigure(1, weight=1)
        table.columnconfigure(0, weight=1)
        select_bar = self.tk.Frame(table,bg=BG)
        select_bar.grid(row=0,column=0,columnspan=2,sticky='ew',pady=(0,7))
        self.selection_text = self.tk.StringVar(self.dialog,'선택 0 / 전체 0')
        for title,action in (('전체 선택','all'),('전체 해제','none'),('선택 반전','invert')):
            app.button(select_bar,title,lambda a=action:self.select_all(a)).pack(side='left',padx=(0,6))
        app.label(select_bar,variable=self.selection_text,bg=BG,color=MUTED).pack(side='left',padx=10)
        app.button(select_bar,'다음 ›',lambda:self.change_page(1)).pack(side='right')
        app.button(select_bar,'‹ 이전',lambda:self.change_page(-1)).pack(side='right',padx=6)
        style = self.ttk.Style(self.dialog)
        style.configure('Upload.Treeview', background=CARD, fieldbackground=CARD, foreground=TEXT,
                        rowheight=28, borderwidth=0, font=(FONT, 9))
        style.configure('Upload.Treeview.Heading', background=INNER, foreground=TEXT, font=(FONT, 9))
        style.map('Upload.Treeview', background=[('selected', '#344051')], foreground=[('selected', TEXT)])
        columns = ('selected', 'number', 'year', 'management_id', 'project_name', 'client', 'technical_field', 'work_type')
        self.tree = self.ttk.Treeview(table, columns=columns, show='headings', style='Upload.Treeview')
        for name, title, width in zip(columns, ('선택', '번호', '연도', '관리번호', '실적명', '고객', '기술분야', '업무유형'),
                                      (55, 55, 60, 110, 280, 140, 420, 120)):
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, minwidth=55, stretch=name in ('project_name', 'client'))
        self.tree.grid(row=1, column=0, sticky='nsew')
        scroll = self.ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        scroll.grid(row=1, column=1, sticky='ns')
        horizontal = self.ttk.Scrollbar(table, orient='horizontal', command=self.tree.xview)
        horizontal.grid(row=2, column=0, sticky='ew')
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.tree.bind('<<TreeviewSelect>>', self._show_row)
        self.tree.bind('<Button-1>',self._check_click,add='+')
        self.tree.bind('<space>',self._check_space)
        detail_frame = self.tk.Frame(self.dialog, bg=BG)
        detail_frame.grid(row=4, column=0, sticky='nsew', padx=22, pady=(6, 0))
        detail_frame.rowconfigure(1, weight=1)
        detail_frame.columnconfigure(0, weight=1)
        self.details = self.tk.Text(detail_frame, bg=INNER, fg=TEXT, height=9, wrap='word', relief='flat',
                                    font=(FONT, 9), state='disabled')
        editor = self.tk.Frame(detail_frame, bg=BG)
        editor.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 8))
        app.label(editor, '선택 행 기술분야', bg=BG, color=MUTED).pack(side='left')
        self.tech_value = self.tk.StringVar(self.dialog)
        self.work_value = self.tk.StringVar(self.dialog)
        taxonomy = self._taxonomy()
        self.tech_editor = self.ttk.Combobox(editor, textvariable=self.tech_value,
            values=[v[0] for v in taxonomy.get('technical', [])]+['미분류'], width=32)
        self.tech_editor.pack(side='left', padx=8)
        app.label(editor, '업무유형', bg=BG, color=MUTED).pack(side='left')
        self.work_editor = self.ttk.Combobox(editor, textvariable=self.work_value,
            values=[v[0] for v in taxonomy.get('work', [])]+['미분류'], width=18)
        self.work_editor.pack(side='left', padx=8)
        self.edit_button = app.button(editor, '수정 적용', self.apply_edit)
        self.edit_button.pack(side='left')
        self.details.grid(row=1, column=0, sticky='nsew')
        detail_scroll = self.ttk.Scrollbar(detail_frame, orient='vertical', command=self.details.yview)
        detail_scroll.grid(row=1, column=1, sticky='ns')
        self.details.configure(yscrollcommand=detail_scroll.set)
        app.label(self.dialog, '모든 처리는 로컬 PC에서만 수행합니다. 확인 필요 행도 저장됩니다. 중복은 기존 기록을 유지합니다.',
                  bg=BG, color=MUTED, size=9, wrap=1050).grid(row=5, column=0, sticky='ew', padx=22, pady=(10, 18))
        self._poll()

    def choose_file(self):
        if self._busy:
            return
        from tkinter import filedialog
        filename = filedialog.askopenfilename(parent=self.dialog, title='회사 실적 파일 선택',
            filetypes=[('실적 파일', '*.xlsx *.xls *.csv'), ('Excel 통합 문서', '*.xlsx'),
                       ('Excel 97-2003', '*.xls'), ('CSV', '*.csv')])
        if filename:
            self.load_file(filename)

    def _start(self, kind, callback):
        self._busy = True
        self._cancel.clear()
        self._phase = kind
        self.choose_button.configure(state='disabled')
        self.analyze_button.configure(state='disabled')
        self.edit_button.configure(state='disabled')
        self.cancel_button.configure(state='normal' if kind == 'preview' else 'disabled')
        self.save_button.configure(state='disabled')
        def work():
            try:
                self._events.put((kind, callback(), None))
            except UploadError as error:
                self._events.put((kind, None, str(error)))
            except (PerformanceError, OSError):
                self._events.put((kind, None, 'DATABASE_SAVE_FAILED' if kind == 'saved' else 'FILE_READ_FAILED'))
            except Exception:
                self._events.put((kind, None, 'DATABASE_SAVE_FAILED' if kind == 'saved' else 'FILE_READ_FAILED'))
        threading.Thread(target=work, name='local-performance-upload', daemon=True).start()

    def load_file(self, filename):
        if self._busy:
            return
        self.file_path = Path(filename).resolve()
        self._mode = 'import'
        self.preview = self.result = None
        self.tree.delete(*self.tree.get_children())
        self.message.set('파일을 읽고 sheet·header·실적 행을 분석하고 있습니다…')
        path = self.file_path  # Capture without accessing Tk in the worker.
        from .analysis_worker import run_analysis
        self._start('preview', lambda: run_analysis('file', path, self.database_path, progress=self._progress, cancel=self._cancel))

    @staticmethod
    def _taxonomy():
        import json
        from .local_model import model_directory
        try:
            return json.loads((model_directory()/'taxonomy.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def _progress(self, current, total):
        self._events.put(('progress', (current, total), None))

    def cancel_analysis(self):
        if self._busy and self._phase == 'preview':
            self._cancel.set()
            self.message.set('현재 batch가 끝나면 분석을 취소합니다…')

    def analyze_existing(self):
        if self._busy:
            return
        if self.preview is not None and self.result is None and any(row.user_edits for row in self.preview.rows):
            self.message.set('사용자 수정값을 먼저 저장한 후 기존 실적을 재분석하세요.')
            return
        from .analysis_worker import run_analysis
        self._mode = 'existing'
        self.preview = self.result = None
        self.tree.delete(*self.tree.get_children())
        force = self.force_analysis.get()
        self.message.set('기존 실적의 비어 있는 AI 필드를 확인하고 있습니다…')
        self._start('preview', lambda: run_analysis('existing', None, self.database_path, progress=self._progress,
                                                   cancel=self._cancel, force=force))

    @staticmethod
    def _technical_display(row):
        # Never show stale model tags over an original/user primary value.
        from .technical_labels import allowed_technical_fields
        allowed = allowed_technical_fields()
        names = [row.technical_field]+[v.get('name') for v in row.technical_fields]
        return ' · '.join(list(dict.fromkeys(v for v in names if v in allowed))[:3]) or '미분류'

    def _row_values(self, row, index=0):
        return ('☑' if index in self.selection.checked else '☐',index+1, row.year or '', row.management_id or '', row.project_name or '이름 미확인',
                row.client or '', self._technical_display(row), row.work_type or '미분류')

    def toggle_checked(self,index):
        if self._busy or self.result is not None or self.preview is None:
            return
        self.selection.toggle(index)
        self._paint_selection()

    def _check_click(self,event):
        if self.tree.identify_column(event.x) == '#1':
            identity = self.tree.identify_row(event.y)
            if identity:
                self.toggle_checked(int(identity))

    def _check_space(self,event=None):
        for identity in self.tree.selection():
            self.toggle_checked(int(identity))
        return 'break'

    def select_all(self,action):
        if self._busy or self.result is not None or self.preview is None:
            return
        if action == 'invert':
            self.selection.invert()
        else:
            self.selection.set_all(action == 'all')
        self._paint_selection()

    def _paint_selection(self):
        self.selection_text.set(f'선택 {len(self.selection.checked):,} / 전체 {self.selection.count:,}  ·  {self.page+1}페이지')
        for identity in self.tree.get_children():
            self.tree.set(identity,'selected','☑' if int(identity) in self.selection.checked else '☐')

    def change_page(self,delta):
        if self._busy or self.preview is None:
            return
        self.page = min(max(0,self.page+delta),max(0,(len(self.preview.rows)-1)//1000))
        self._paint_rows()

    def _paint_rows(self):
        self.tree.delete(*self.tree.get_children())
        start = self.page*1000
        for index,row in enumerate(self.preview.rows[start:start+1000],start):
            self.tree.insert('','end',iid=str(index),values=self._row_values(row,index))
        self._paint_selection()

    def _render_preview(self):
        preview = self.preview
        self.message.set(f'파일: {preview.filename}   /   데이터 sheet {preview.sheet_count}개   /   전체 후보 {len(preview.rows):,}건   /   '
                         f'자동 분류 {len(preview.rows)-preview.review_count:,}건   /   확인 필요 {preview.review_count:,}건   /   제외 {preview.excluded:,}건')
        self.selection = PreviewSelection(len(preview.rows))
        self.page = 0
        self._paint_rows()
        self._set_details('\n'.join(preview.warnings + ['행을 선택하면 확인 필요 사유·매핑·보존된 원본을 볼 수 있습니다.',
            '이전/다음으로 1,000행씩 확인할 수 있습니다. 체크한 행만 저장합니다.']))
        self.save_button.configure(state='normal')

    def _set_details(self, text):
        self.details.configure(state='normal')
        self.details.delete('1.0', 'end')
        self.details.insert('1.0', text)
        self.details.configure(state='disabled')

    def _show_row(self, event=None):
        selected = self.tree.selection()
        if not selected or self.preview is None:
            return
        import json
        row = self.preview.rows[int(selected[0])]
        self.tech_value.set(self._technical_display(row))
        self.work_value.set(row.work_type or '미분류')
        self._set_details(f'번호 {int(selected[0])+1}  ·  {row.status}\n'
            + ('\n'.join(row.issues) or '확인 필요 항목 없음')
            + '\n\n열 매핑:\n' + json.dumps(self.preview.mappings.get(row.sheet, {}), ensure_ascii=False, indent=2)
            + '\n\n출처 / 실제 cosine·margin (확률이 아님):\n' + json.dumps({'field_sources':row.field_sources,
                'field_confidence':row.field_confidence, 'evidence':row.ai_evidence,
                'technical_fields':row.technical_fields, 'technical_tags':row.technical_tags, 'keywords':row.keywords,
                'model_version':row.ai_model_version}, ensure_ascii=False, indent=2)
            + '\n\n보존된 원본 행:\n' + json.dumps(row.raw_source, ensure_ascii=False, indent=2))

    def apply_edit(self):
        if self._busy or self.result is not None or self.preview is None or not self.tree.selection():
            return
        from .enrichment import set_user_value
        index = self.tree.selection()[0]
        row = self.preview.rows[int(index)]
        from .technical_labels import selection
        try:
            selection(self.tech_value.get())
        except ValueError:
            self.message.set('기술분야는 후보 목록에서 최대 3개를 선택하세요. 복수 후보는 · 로 구분합니다.')
            return
        for name, value in (('technical_field', self.tech_value.get()), ('work_type', self.work_value.get())):
            current = self._technical_display(row) if name == 'technical_field' else (getattr(row, name) or '미분류')
            if value != current:
                set_user_value(row, name, value)
        self.tree.item(index, values=self._row_values(row, int(index)))
        self._show_row()

    def save(self):
        if self._busy or self.preview is None or self.result is not None:
            return
        if not self.selection.checked:
            self.message.set(ERROR_TEXT['NO_SELECTED_ROWS'])
            return
        from .seen import seen_path
        cache = Path(self.app.cache_path.get()).resolve()
        protected = {cache, cache.with_name(cache.name + '.sources.json'), seen_path(cache).resolve(), self.file_path}
        if self.database_path in protected:
            self.message.set(ERROR_TEXT['PATH_COLLISION'])
            return
        self.message.set('확인한 실적을 로컬 DB에 저장하고 있습니다…')
        preview, database = self.preview, self.database_path
        checked,existing = set(self.selection.checked),self._mode == 'existing'
        self._start('saved', lambda: save_selected(database,preview,checked,existing=existing))

    def _poll(self):
        if self._closed:
            return
        try:
            while True:
                kind, value, error = self._events.get_nowait()
                if kind == 'progress':
                    self.message.set(f'실적 분석 중 {value[0]:,} / {value[1]:,} · 로컬 CPU 처리')
                    continue
                self._busy = False
                self.choose_button.configure(state='normal')
                self.analyze_button.configure(state='normal')
                self.edit_button.configure(state='normal')
                self.cancel_button.configure(state='disabled')
                if error:
                    self.message.set(ERROR_TEXT.get(error, '처리에 실패했습니다. 파일과 DB 설정을 확인하세요.'))
                    if self.preview is not None and self.result is None:
                        self.save_button.configure(state='normal')
                elif kind == 'preview':
                    self.preview = value
                    self._render_preview()
                elif kind == 'saved':
                    self.result = value
                    self.message.set(f'선택 {value.selected:,}건 중 {value.saved:,}건 저장, 갱신 {value.updated:,}건, '
                                     f'중복 {value.duplicates:,}건, 제외 {value.excluded_by_user:,}건, 실패 {value.failed:,}건')
                    self._set_details('\n'.join(f'{sheet} / {row}행: 저장 실패' for sheet, row, code in value.failed_rows)
                                      or '로컬 DB에 반영했습니다. 공고별 실적 매칭에서 바로 사용할 수 있습니다.')
                    self.app.reload_performances(self.database_path)
        except queue.Empty:
            pass
        self._job = self.dialog.after(80, self._poll)

    def _destroyed(self, event):
        if event.widget is self.dialog:
            self._closed = True

    def close(self):
        if self._busy:
            self.message.set('처리 중입니다. 저장·읽기가 끝난 후 닫아 주세요.')
            return
        if self._closed:
            return
        self._closed = True
        if self._job:
            self.dialog.after_cancel(self._job)
        self.dialog.destroy()
