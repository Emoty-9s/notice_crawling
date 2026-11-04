"""Dark Night local performance list/edit/delete. All SQL stays in the service."""
import queue
import threading
from pathlib import Path
from .performance_management import PerformanceManagement, EMPTY_TEXT, technical_names, allowed_work_types
from .technical_labels import allowed_technical_fields


COLUMNS = ('number','year','management_id','project_name','client','technical_field','work_type')
HEADINGS = ('번호','연도','관리번호','실적명','고객','기술분야','업무유형')


class PerformanceManagementDialog:
    def __init__(self,app):
        from .ui import BG,CARD,INNER,TEXT,MUTED,FONT
        self.app,self.tk,self.ttk = app,app.tk,app.ttk
        self.database_path = Path(app.database_path.get()).resolve()
        self.service = PerformanceManagement(self.database_path)
        self._closed = self._busy = self._refresh_pending = False
        self._events = queue.Queue()
        self.rows = []
        self.editor = None
        self.dialog = self.tk.Toplevel(app.root)
        self.dialog.title('실적 관리')
        self.dialog.geometry('1320x700')
        self.dialog.minsize(950,520)
        self.dialog.configure(bg=BG)
        self.dialog.transient(app.root)
        self.dialog.protocol('WM_DELETE_WINDOW',self.close)
        self.dialog.bind('<Destroy>',lambda e:setattr(self,'_closed',True) if e.widget is self.dialog else None,add='+')
        app.label(self.dialog,'실적 관리',bg=BG,size=18,bold=True).pack(anchor='w',padx=22,pady=(20,10))
        search = self.tk.Frame(self.dialog,bg=BG)
        search.pack(fill='x',padx=22,pady=8)
        self.query = self.tk.StringVar(self.dialog)
        entry = app.entry(search,self.query,width=45)
        entry.pack(side='left',ipady=5)
        entry.bind('<Return>',lambda e:self.refresh())
        app.button(search,'검색',self.refresh).pack(side='left',padx=8)
        self.message = self.tk.StringVar(self.dialog,'로컬 실적을 불러오고 있습니다…')
        app.label(self.dialog,variable=self.message,bg=BG,color=MUTED,wrap=1200).pack(fill='x',padx=22,pady=6)
        table = self.tk.Frame(self.dialog,bg=BG)
        table.pack(fill='both',expand=True,padx=22,pady=8)
        table.columnconfigure(0,weight=1)
        table.rowconfigure(0,weight=1)
        style = self.ttk.Style(self.dialog)
        style.configure('Management.Treeview',background=CARD,fieldbackground=CARD,foreground=TEXT,
                        rowheight=30,borderwidth=0,font=(FONT,10))
        style.configure('Management.Treeview.Heading',background=INNER,foreground=TEXT,font=(FONT,10))
        style.map('Management.Treeview',background=[('selected','#344051')],foreground=[('selected',TEXT)])
        self.tree = self.ttk.Treeview(table,columns=COLUMNS,show='headings',selectmode='extended',style='Management.Treeview')
        self._descending = {}
        for name,title,width in zip(COLUMNS,HEADINGS,(55,70,120,280,150,420,130)):
            self.tree.heading(name,text=title,command=lambda n=name:self.sort(n))
            self.tree.column(name,width=width,minwidth=50,stretch=name in ('project_name','client','technical_field'))
        self.tree.grid(row=0,column=0,sticky='nsew')
        yscroll = self.ttk.Scrollbar(table,orient='vertical',command=self.tree.yview)
        yscroll.grid(row=0,column=1,sticky='ns')
        xscroll = self.ttk.Scrollbar(table,orient='horizontal',command=self.tree.xview)
        xscroll.grid(row=1,column=0,sticky='ew')
        self.tree.configure(yscrollcommand=yscroll.set,xscrollcommand=xscroll.set)
        self.tree.bind('<Double-1>',lambda e:self.edit())
        actions = self.tk.Frame(self.dialog,bg=BG)
        actions.pack(fill='x',padx=22,pady=(8,20))
        self.edit_button = app.button(actions,'수정',self.edit)
        self.edit_button.pack(side='left')
        self.delete_button = app.button(actions,'삭제',self.delete)
        self.delete_button.pack(side='left',padx=8)
        app.button(actions,'새로고침',self.refresh).pack(side='left')
        app.button(actions,'닫기',self.close).pack(side='right')
        self._job = self.dialog.after(60,self._poll)
        self.refresh()

    def _start(self,kind,callback):
        self._busy = True
        self.edit_button.configure(state='disabled')
        self.delete_button.configure(state='disabled')
        def work():
            try:
                self._events.put((kind,callback(),None))
            except Exception as error:
                # Never expose raw SQL or company contents through an exception.
                code = str(error) if isinstance(error,ValueError) and str(error) in ('RECORD_CHANGED','INVALID_YEAR','INVALID_PROJECT','INVALID_WORK_TYPE','INVALID_TECHNICAL_SELECTION') else 'LOCAL_DATABASE_ERROR'
                self._events.put((kind,None,code))
        threading.Thread(target=work,name='local-performance-management',daemon=True).start()

    def refresh(self):
        if self._closed:
            return
        if self._busy:
            self._refresh_pending = True
            return
        self._refresh_pending = False
        query = self.query.get()
        self._start('list',lambda:self.service.list(query))

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        for index,row in enumerate(self.rows):
            self.tree.insert('','end',iid=row.performance_id,values=(index+1,row.year or '',row.management_id or '',
                row.project_name or '',row.client or '', ' · '.join(technical_names(row)) or '미분류', row.work_type or '미분류'))
        self.message.set(f'실적 {len(self.rows):,}건 · 로컬 DB' if self.rows else
                         ('검색 결과가 없습니다.' if self.query.get().strip() else EMPTY_TEXT))

    def sort(self,name):
        if self._busy:
            return
        reverse = not self._descending.get(name,False)
        self._descending[name] = reverse
        if name == 'number':
            self.rows.reverse()
        else:
            key = (lambda r:r.year or 0) if name == 'year' else (
                lambda r:(' · '.join(technical_names(r)) if name == 'technical_field' else str(getattr(r,name) or '')).casefold())
            self.rows.sort(key=key,reverse=reverse)
        self._render()

    def selected_rows(self):
        identities = set(self.tree.selection())
        return [r for r in self.rows if r.performance_id in identities]

    def edit(self):
        if self._busy:
            return
        rows = self.selected_rows()
        if len(rows) != 1:
            self.message.set('수정할 실적 1건을 선택하세요.')
            return
        if self.editor is not None and not self.editor._closed:
            self.editor.dialog.lift()
            return
        self.editor = PerformanceEditDialog(self,rows[0])

    def update(self,row,values):
        if self._busy:
            self.message.set('목록 갱신이 끝난 후 다시 저장하세요.')
            return False
        self._start('updated',lambda:self.service.update(row,**values))
        return True

    def delete(self):
        if self._busy:
            return
        rows = self.selected_rows()
        if not rows:
            self.message.set('삭제할 실적을 선택하세요.')
            return
        from tkinter import messagebox
        prompt = f'"{rows[0].project_name}" 실적을 삭제하시겠습니까?' if len(rows) == 1 else f'{len(rows):,}건의 실적을 삭제하시겠습니까?'
        if messagebox.askyesno('실적 삭제',prompt,parent=self.dialog):
            self._start('deleted',lambda:self.service.delete(rows))

    def _poll(self):
        if self._closed:
            return
        try:
            while True:
                kind,value,error = self._events.get_nowait()
                self._busy = False
                self.edit_button.configure(state='normal')
                self.delete_button.configure(state='normal')
                if error:
                    self._last_error = error
                    self.message.set('실적이 다른 곳에서 변경되었습니다. 새로고침 후 다시 시도하세요.' if error == 'RECORD_CHANGED' else '로컬 DB 처리에 실패했습니다. 입력값·DB 상태를 확인하세요.')
                    if self.editor and not self.editor._closed:
                        self.editor.save_button.configure(state='normal')
                        self.editor.message.set(self.message.get())
                elif kind == 'list':
                    self.rows = value
                    self._render()
                else:
                    if kind == 'updated' and self.editor and not self.editor._closed:
                        self.editor.close()
                    self.app.reload_performances(self.database_path)
                    self.refresh()
                if self._refresh_pending and not self._busy:
                    self.refresh()
        except queue.Empty:
            pass
        self._job = self.dialog.after(60,self._poll)

    def close(self):
        if self._busy:
            self.message.set('로컬 DB 처리가 끝난 후 닫아 주세요.')
            return
        if not self._closed:
            self._closed = True
            self.dialog.after_cancel(self._job)
            self.dialog.destroy()


class PerformanceEditDialog:
    def __init__(self,manager,row):
        from .ui import BG,INNER,TEXT,MUTED
        self.manager,self.row,self.app = manager,row,manager.app
        self._closed = False
        tk,ttk = manager.tk,manager.ttk
        self.dialog = tk.Toplevel(manager.dialog)
        self.dialog.title('실적 수정')
        self.dialog.geometry('870x750')
        self.dialog.configure(bg=BG)
        self.dialog.transient(manager.dialog)
        self.dialog.protocol('WM_DELETE_WINDOW',self.close)
        self.dialog.columnconfigure(1,weight=1)
        self.values = {}
        for index,(name,title,value) in enumerate((('year','연도',row.year or ''),('management_id','관리번호',row.management_id or ''),
                ('project_name','실적명',row.project_name or ''),('client','고객',row.client or ''))):
            self.app.label(self.dialog,title,bg=BG,color=MUTED).grid(row=index,column=0,sticky='w',padx=20,pady=10)
            variable = tk.StringVar(self.dialog,str(value))
            self.values[name] = variable
            self.app.entry(self.dialog,variable,width=75).grid(row=index,column=1,sticky='ew',padx=20,pady=10,ipady=5)
        self.app.label(self.dialog,'기술분야 · 최대 3개',bg=BG,color=MUTED).grid(row=4,column=0,columnspan=2,sticky='w',padx=20,pady=(15,5))
        fields = tk.Frame(self.dialog,bg=BG)
        fields.grid(row=5,column=0,columnspan=2,sticky='ew',padx=20)
        self.technical = {}
        for index,name in enumerate(allowed_technical_fields()):
            value = tk.BooleanVar(self.dialog,name in technical_names(row))
            self.technical[name] = value
            tk.Checkbutton(fields,text=name,variable=value,command=lambda n=name:self._limit(n),bg=BG,fg=TEXT,
                           activebackground=BG,activeforeground=TEXT,selectcolor=INNER,anchor='w').grid(row=index//3,column=index%3,sticky='w',pady=5,padx=(0,15))
        self.app.label(self.dialog,'업무유형',bg=BG,color=MUTED).grid(row=6,column=0,sticky='w',padx=20,pady=15)
        self.work = tk.StringVar(self.dialog,row.work_type if row.work_type in allowed_work_types() else '미분류')
        ttk.Combobox(self.dialog,textvariable=self.work,values=['미분류',*allowed_work_types()],state='readonly',width=35).grid(row=6,column=1,sticky='w',padx=20)
        self.message = tk.StringVar(self.dialog,'수정한 값은 사용자 값으로 저장되어 AI 재분석에서 보호됩니다.')
        self.app.label(self.dialog,variable=self.message,bg=BG,color=MUTED,wrap=800).grid(row=7,column=0,columnspan=2,sticky='ew',padx=20,pady=15)
        actions = tk.Frame(self.dialog,bg=BG)
        actions.grid(row=8,column=0,columnspan=2,sticky='e',padx=20,pady=15)
        self.save_button = self.app.button(actions,'저장',self.save)
        self.save_button.pack(side='left',padx=8)
        self.app.button(actions,'취소',self.close).pack(side='left')

    def _limit(self,name):
        if sum(v.get() for v in self.technical.values()) > 3:
            self.technical[name].set(False)
            self.message.set('기술분야는 최대 3개까지 선택할 수 있습니다.')

    def save(self):
        try:
            year = self.values['year'].get().strip()
            year = int(year) if year else None
            if year is not None and not 1 <= year <= 9999:
                raise ValueError()
            if not self.values['project_name'].get().strip():
                raise ValueError()
        except ValueError:
            self.message.set('연도는 1~9999 숫자로 입력하고, 실적명은 반드시 입력하세요.')
            return
        values = {name:value.get() for name,value in self.values.items()}
        values.update(year=year,technical_fields=[name for name,value in self.technical.items() if value.get()],work_type=self.work.get())
        if self.manager.update(self.row,values):
            self.save_button.configure(state='disabled')
            self.message.set('로컬 DB에 저장하고 있습니다…')

    def close(self):
        if self.manager._busy and str(self.save_button.cget('state')) == 'disabled':
            return
        if not self._closed:
            self._closed = True
            self.dialog.destroy()
