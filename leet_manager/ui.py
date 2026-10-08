import tkinter as tk
from tkinter import ttk,messagebox,filedialog
from pathlib import Path
from .models import TYPES,SUBJECTS,STATES
from .editor import Editor
from .import_dialog import open_import
from .backup import backup,restore
from .export import export_csv
from .widgets import Form

class App:
    def __init__(self,root,store):
        self.root=root; self.store=store; self.filters={}; self.items={}
        root.title('LEET 언어이해 문항관리'); root.geometry('1250x820'); root.minsize(900,600)
        style=ttk.Style(root); style.theme_use('clam')
        style.configure('Treeview',rowheight=30,font=('맑은 고딕',10))
        style.configure('TLabel',font=('맑은 고딕',10)); style.configure('TButton',font=('맑은 고딕',10),padding=6)
        self.frame=ttk.Frame(root,padding=16); self.frame.pack(fill='both',expand=True)
        ttk.Label(self.frame,text='LEET 언어이해 · 문항 자료실',font=('맑은 고딕',18,'bold')).pack(anchor='w',pady=(0,4))
        ttk.Label(self.frame,text='개인용 오프라인 · 세트와 문항 관리 · 미확인 정보는 추정하지 않습니다').pack(anchor='w',pady=(0,12))
        bar=ttk.Frame(self.frame); bar.pack(fill='x',pady=5)
        for label,command in [('새 세트',self.new),('HWPX 가져오기',self.import_file),('선택 자료 열기',self.open_selected),('CSV 내보내기',self.export),('ZIP 백업',self.backup),('복원',self.restore),('세부 과목 관리',self.subjects)]:
            ttk.Button(bar,text=label,command=command).pack(side='left',padx=(0,5))
        search=ttk.Frame(self.frame); search.pack(fill='x',pady=8)
        ttk.Label(search,text='제목 · 제시문 · 문항 · 해설 · 키워드 · ID').pack(side='left')
        self.query=tk.StringVar(); entry=ttk.Entry(search,textvariable=self.query); entry.pack(side='left',fill='x',expand=True,padx=10)
        entry.bind('<Return>',lambda e:self.refresh())
        ttk.Button(search,text='검색',command=self.refresh).pack(side='left')
        ttk.Button(search,text='필터 초기화',command=self.reset_filters).pack(side='left',padx=5)
        panel=ttk.Frame(self.frame); panel.pack(fill='x',pady=(0,12))
        specs=[('view','보기',['세트','문항']),('year','생성 연도',None),('domain','내용 영역',['전체']+list(SUBJECTS)),
               ('subject','세부 과목',['전체']),('type','문항 유형',['전체']+TYPES),
               ('usage_status','사용 여부',['전체']+STATES),('past_status','기출 여부',['전체']+STATES),
               ('disposal_status','폐기 여부',['전체']+STATES),('review_status','검토 상태',['전체','초안','검토 중','검토 완료'])]
        self.filter_widgets={}
        for n,(key,label,options) in enumerate(specs):
            r,c=divmod(n,5)
            cell=ttk.Frame(panel); cell.grid(row=r,column=c,sticky='ew',padx=(0,8),pady=4); panel.columnconfigure(c,weight=1)
            ttk.Label(cell,text=label).pack(anchor='w')
            var=tk.StringVar(value=options[0] if options else '')
            widget=ttk.Combobox(cell,textvariable=var,values=options,state='readonly',width=18) if options else ttk.Entry(cell,textvariable=var,width=12)
            widget.pack(fill='x'); self.filters[key]=var; self.filter_widgets[key]=widget
            if options: widget.bind('<<ComboboxSelected>>',self.filter_changed)
            else: widget.bind('<Return>',lambda e:self.refresh())
        self.include_disposed=tk.BooleanVar(value=False)
        ttk.Checkbutton(panel,text='폐기 자료 포함',variable=self.include_disposed,command=self.refresh).grid(row=1,column=4,sticky='w',pady=(26,0))
        table=ttk.Frame(self.frame); table.pack(fill='both',expand=True)
        columns=('id','title','number','year','domain','subject','type','usage','past','disposal','review')
        self.tree=ttk.Treeview(table,columns=columns,show='headings',selectmode='browse')
        labels=['세트ID / 문항ID','제목','번호','생성 연도','영역','과목','문항 유형','사용','기출','폐기','검토']
        for col,label in zip(columns,labels):
            self.tree.heading(col,text=label); self.tree.column(col,width=210 if col in ('id','title','type') else 80,minwidth=60,stretch=col=='title')
        vertical=ttk.Scrollbar(table,command=self.tree.yview); horizontal=ttk.Scrollbar(table,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        self.tree.grid(row=0,column=0,sticky='nsew'); vertical.grid(row=0,column=1,sticky='ns'); horizontal.grid(row=1,column=0,sticky='ew')
        table.rowconfigure(0,weight=1); table.columnconfigure(0,weight=1)
        self.tree.bind('<Double-1>',lambda e:self.open_selected()); self.tree.bind('<Return>',lambda e:self.open_selected())
        self.status=tk.StringVar(); ttk.Label(self.frame,textvariable=self.status,wraplength=1150).pack(anchor='w',pady=(12,0))
        self.refresh()
    def filter_changed(self,event=None):
        if event and event.widget==self.filter_widgets['domain']:
            names=self.store.subjects().get(self.filters['domain'].get(),[])
            self.filter_widgets['subject'].configure(values=['전체']+names); self.filters['subject'].set('전체')
        self.refresh()
    def reset_filters(self):
        self.query.set(''); self.include_disposed.set(False)
        for key,var in self.filters.items(): var.set('세트' if key=='view' else '' if key=='year' else '전체')
        self.filter_widgets['subject'].configure(values=['전체']); self.refresh()
    def current_filters(self):
        d={k:v.get() for k,v in self.filters.items()}
        d['view']='questions' if d['view']=='문항' else 'sets'; d['include_disposed']=self.include_disposed.get()
        text=d['year'].strip()
        if text in ('미확인','미입력'):
            # Search post-filter for NULL year; the Store supports a sentinel.
            d['year']='미확인'
        elif text:
            try: d['year']=int(text)
            except ValueError as e: raise ValueError('생성 연도는 숫자 또는 미확인으로 입력하세요.') from e
        else: d['year']=None
        return d
    def refresh(self):
        try: result=self.store.search(self.query.get(),self.current_filters())
        except (ValueError,OSError) as e: messagebox.showerror('검색',str(e),parent=self.root); return
        for item in self.tree.get_children(): self.tree.delete(item)
        self.items={}
        for n,s in enumerate(result):
            iid=str(n); self.items[iid]=s.get('set_id',s['id'])
            self.tree.insert('', 'end',iid=iid,values=(s['id'],s['title'],s.get('number',''),s['year'] or '미확인',
                s['domain'] or '미확인',s['subject'] or '미확인',s.get('type','') or '미확인',
                s['usage_status'],s['past_status'],s['disposal_status'],s['review_status']))
        self.status.set(f"{len(result)}개 표시 · 데이터 위치: {self.store.data_dir} · 같은 데이터 폴더의 프로그램을 동시에 실행하지 마세요.")
    def new(self): return Editor(self.root,self.store,on_saved=self.refresh)
    def open_selected(self):
        selected=self.tree.selection()
        if not selected: messagebox.showinfo('자료 선택','목록에서 자료를 선택하세요.',parent=self.root); return
        return Editor(self.root,self.store,self.store.get_set(self.items[selected[0]]),self.refresh)
    def import_file(self):
        path=filedialog.askopenfilename(parent=self.root,title='HWPX 원본 선택',filetypes=[('HWPX','*.hwpx')])
        if not path: return
        try: return open_import(self.root,self.store,Path(path),self.refresh)
        except (ValueError,OSError) as e: messagebox.showerror('HWPX 가져오기',str(e),parent=self.root)
    def export(self):
        path=filedialog.asksaveasfilename(parent=self.root,title='현재 검색 결과의 문항 내보내기',defaultextension='.csv',filetypes=[('CSV','*.csv')])
        if not path: return
        try:
            f=self.current_filters(); f['query']=self.query.get()
            count=export_csv(self.store,Path(path),f)
            messagebox.showinfo('CSV 저장',f'{count}개 문항을 저장했습니다.',parent=self.root)
        except (ValueError,OSError) as e: messagebox.showerror('CSV 저장',str(e),parent=self.root)
    def backup(self):
        path=filedialog.asksaveasfilename(parent=self.root,title='DB와 원본 백업',defaultextension='.zip',filetypes=[('ZIP','*.zip')])
        if not path: return
        try:
            backup(self.store,path); messagebox.showinfo('백업 완료','데이터베이스와 원본을 백업했습니다.',parent=self.root)
        except (ValueError,OSError) as e: messagebox.showerror('백업 실패',str(e),parent=self.root)
    def restore(self):
        editors=[w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel)]
        if editors:
            messagebox.showinfo('편집창 닫기','자료 편집창과 가져오기창을 모두 닫은 후 복원하세요.',parent=self.root); return
        path=filedialog.askopenfilename(parent=self.root,title='백업 ZIP 선택',filetypes=[('ZIP','*.zip')])
        if not path: return
        if not messagebox.askyesno('복원 확인','현재 자료를 자동 백업한 뒤 선택한 백업으로 교체합니다. 계속할까요?',parent=self.root): return
        try:
            automatic=restore(self.store,path); self.refresh()
            messagebox.showinfo('복원 완료','현재 자료의 자동 백업:\n'+str(automatic),parent=self.root)
        except (ValueError,OSError) as e: messagebox.showerror('복원 실패',str(e),parent=self.root)
    def subjects(self):
        w=tk.Toplevel(self.root); w.title('세부 과목 관리'); w.geometry('550x340')
        f=Form(w,[('domain','내용 영역','choice',list(SUBJECTS)),('name','과목 이름','entry',None)])
        f.set('domain','인문')
        listing=tk.StringVar(); ttk.Label(w,textvariable=listing,wraplength=500).grid(row=2,column=0,columnspan=2,padx=10,pady=10)
        def refresh(): listing.set(', '.join(self.store.subjects().get(f.get('domain'),[])))
        f.widgets['domain'].bind('<<ComboboxSelected>>',lambda e:refresh())
        def change(delete=False):
            try:
                if delete: self.store.delete_subject(f.get('domain'),f.get('name'))
                else: self.store.add_subject(f.get('domain'),f.get('name'))
                refresh(); self.filter_changed()
            except ValueError as e: messagebox.showerror('과목 관리',str(e),parent=w)
        ttk.Button(w,text='추가',command=change).grid(row=3,column=0,pady=10)
        ttk.Button(w,text='삭제 (사용 중인 과목 보호)',command=lambda:change(True)).grid(row=3,column=1,pady=10)
        refresh()
