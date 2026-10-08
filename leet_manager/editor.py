import copy
import json
import os
import tkinter as tk
from tkinter import ttk,messagebox
from .widgets import Form,ScrollFrame
from .models import SET_DEFAULTS,QUESTION_DEFAULTS,SUBJECTS,STATES,TYPES
from .import_service import import_confirmed

SET_SPECS=[
 ('id','세트ID','readonly',None),('title','제목 *','entry',None),('year','생성 연도 (미확인: 빈칸)','entry',None),
 ('created_at','등록 시각','readonly',None),('domain','내용 영역','choice',['']+list(SUBJECTS)),
 ('subject','세부 과목','choice',['']),('auxiliary_subjects','보조 과목 (쉼표 구분)','entry',None),
 ('tags','검색 태그 (쉼표 구분)','entry',None),('keywords','공통 핵심 키워드','entry',None),
 ('passage','제시문','text',12),('source','원문 출처 / 참고문헌','text',4),
 ('author','작성자','entry',None),('reviewer','검토자','entry',None),
 ('review_status','검토 상태','choice',['초안','검토 중','검토 완료']),('memo','메모','text',3),
 ('usage_status','사용 여부','choice',STATES),('past_status','기출 여부','choice',STATES),
 ('disposal_status','폐기 여부','choice',STATES),('disposal_date','폐기일 (YYYY-MM-DD)','entry',None),
 ('disposal_reason','폐기 사유','text',2),('original_name','원본 파일 이름','readonly',None),
 ('file_hash','원본 SHA256','readonly',None)]
QUESTION_SPECS=[
 ('id','문항ID (자동 생성)','readonly',None),('prompt','발문','text',3),('view','〈보기〉','text',5),
 ('type','문항 유형','choice',['']+TYPES),('keywords','문항별 핵심 키워드','entry',None),
 ('character','문항 성격','text',2),('objective','평가 목표','text',3),('solution','문항 풀이 / 해설 원문','text',8),
 ('answer','정답 번호 (미입력: 빈칸)','choice',['','1','2','3','4','5']),
 ('evidence','정답 / 제시문 근거','text',4),('wrong_heading','원문 오답 표제','entry',None),
 ('wrong_explanation','원문 오답 근거 / 해설','text',5),('trap','함정 유형','text',2),
 ('difficulty','예상 난이도','choice',['','쉬움','보통','어려움']),('rate','실제 정답률 (%)','entry',None),
 ('review_memo','검토 메모','text',3),('usage_status','사용 여부','choice',STATES),
 ('past_status','기출 여부','choice',STATES),('disposal_status','폐기 여부','choice',STATES),
 ('disposal_date','폐기일 (YYYY-MM-DD)','entry',None),('disposal_reason','폐기 사유','text',2)]

class QuestionForm(Form):
    def __init__(self,parent,number):
        self.number=number
        specs=QUESTION_SPECS[:]
        # Keep choices close to the prompt and answer; explanations remain separate fields.
        choice_specs=[]
        for n in range(1,6):
            choice_specs.extend([(f'choice{n}',f'{n}번 선택지','text',3),
                                 (f'validity{n}',f'{n}번 진술 타당성','choice',['미확인','타당','부적절']),
                                 (f'explanation{n}',f'{n}번 선택지 해설','text',3)])
        specs=specs[:3]+[QUESTION_SPECS[8]]+choice_specs+specs[3:8]+specs[9:]
        super().__init__(parent,specs)
        self.load(dict(copy.deepcopy(QUESTION_DEFAULTS),choices=[]))
    def load(self,data):
        super().load(data)
        for n in range(1,6):
            c=(data.get('choices',[])+[{}]*5)[n-1]
            for key,field,default in [('choice','text',''),('validity','validity','미확인'),('explanation','explanation','')]:
                self.set(key+str(n),c.get(field,default))
    def collect_question(self):
        raw=self.collect(list_keys=['keywords'],int_keys=['answer'],float_keys=['rate'])
        choices=[dict(text=raw.pop('choice'+str(n)),validity=raw.pop('validity'+str(n)),explanation=raw.pop('explanation'+str(n))) for n in range(1,6)]
        if not raw['id']: raw.pop('id')
        raw.update(number=self.number,choices=choices)
        return raw

class Editor:
    def __init__(self,parent,store,data=None,on_saved=None,source=None):
        self.store=store; self.on_saved=on_saved or (lambda:None); self.source=source
        self.data=data or copy.deepcopy(SET_DEFAULTS); self.sid=self.data.get('id')
        self.window=tk.Toplevel(parent); self.window.title('LEET · '+('자료 편집' if self.sid else '새 세트 등록'))
        self.window.geometry('1040x800'); self.window.minsize(760,540)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        top=ttk.Frame(self.window,padding=10); top.pack(fill='x')
        ttk.Label(top,text='초안으로 저장할 수 있습니다. 빈 연도·정답률은 미확인입니다. 정답과 진술 타당성은 별도입니다.',wraplength=800).pack(side='left')
        actions=ttk.Frame(self.window,padding=8); actions.pack(side='bottom',fill='x')
        ttk.Button(actions,text='저장',command=self.save).pack(side='right',padx=4)
        ttk.Button(actions,text='닫기',command=self.close).pack(side='right',padx=4)
        ttk.Button(actions,text='원본 열기',command=self.open_original).pack(side='left',padx=4)
        if self.data.get('raw_text'):
            ttk.Button(actions,text='추출 원문 확인 / 배정',command=self.show_raw).pack(side='left',padx=4)
        self.notebook=ttk.Notebook(self.window); self.notebook.pack(fill='both',expand=True,padx=10,pady=5)
        page=ScrollFrame(self.notebook); self.notebook.add(page,text='세트 · 제시문')
        self.set_form=Form(page.body,SET_SPECS); self.set_form.load(self.data)
        self.set_form.widgets['domain'].bind('<<ComboboxSelected>>',self.change_domain)
        self.update_subjects(); self.set_form.set('subject',self.data.get('subject',''))
        self.question_forms=[]
        by_number={q['number']:q for q in self.data.get('questions',[])}
        for n in range(1,4):
            page=ScrollFrame(self.notebook); self.notebook.add(page,text=f'문항 {n}')
            f=QuestionForm(page.body,n)
            if n in by_number: f.load(by_number[n])
            self.question_forms.append(f)
        self.records=ScrollFrame(self.notebook); self.notebook.add(self.records,text='사용 · 기출 · 수정 이력')
        self.draw_records()
        self.initial=self.snapshot()
    def snapshot(self): return [self.set_form.snapshot()]+[f.snapshot() for f in self.question_forms]
    def update_subjects(self):
        domain=self.set_form.get('domain')
        self.set_form.widgets['subject'].configure(values=['']+self.store.subjects().get(domain,[]))
    def change_domain(self,event=None): self.update_subjects(); self.set_form.set('subject','')
    def collect(self):
        data=self.set_form.collect(list_keys=['keywords','auxiliary_subjects','tags'],int_keys=['year'])
        data['raw_text']=self.data.get('raw_text','')
        if self.sid: data['revision']=self.data['revision']
        qs=[f.collect_question() for f in self.question_forms]
        return data,qs
    def save(self,close=True):
        try:
            data,qs=self.collect()
            if self.source and not self.sid:
                if not messagebox.askyesno('가져오기 확인','제시문·세 문항·보기·선택지·정답·해설의 배정을 확인했습니까?\n확인한 내용으로 원본 사본과 자료를 저장합니다.',parent=self.window): return None
                sid=import_confirmed(self.store,self.source,data,qs)
            else: sid=self.store.save_set(data,qs,self.sid)
            self.sid=sid; self.data=self.store.get_set(sid); self.source=None
            self.set_form.load(self.data)
            for f,q in zip(self.question_forms,self.data['questions']): f.load(q)
            self.initial=self.snapshot(); self.draw_records(); self.on_saved()
            if close: self.window.destroy()
            return sid
        except (ValueError,OSError) as e: messagebox.showerror('저장하지 못했습니다',str(e),parent=self.window)
        return None
    def close(self):
        if self.snapshot()!=self.initial:
            result=messagebox.askyesnocancel('미저장 변경','변경한 내용을 저장하고 닫을까요?',parent=self.window)
            if result is None: return
            if result: self.save(); return
        self.window.destroy()
    def open_original(self):
        try:
            path=self.source or (self.store.data_dir/self.data.get('original_path',''))
            if not self.source and not self.data.get('original_path'): raise ValueError('등록된 원본이 없습니다.')
            if not path.is_file(): raise ValueError('원본 파일이 없습니다.')
            if os.name!='nt': raise ValueError('원본 열기는 Windows 파일 연결을 사용합니다.')
            os.startfile(str(path.resolve()))
        except (ValueError,OSError) as e: messagebox.showerror('원본 열기',str(e),parent=self.window)
    def assignment_targets(self):
        result={}
        for key in ['passage','source','keywords','memo']:
            result['세트 / '+self.set_form.labels[key]]=(self.set_form,key)
        for n,f in enumerate(self.question_forms,1):
            for key in f.widgets:
                if key in ['id','answer','type','difficulty','rate','usage_status','past_status','disposal_status'] or key.startswith('validity'): continue
                label='보기' if key=='view' else f.labels[key]
                result[f'문항 {n} / {label}']=(f,key)
        return result
    def assign_text(self,target,text):
        f,key=self.assignment_targets()[target]; f.set(key,text)
    def show_raw(self):
        w=tk.Toplevel(self.window); w.title('추출 원문 확인 · 선택 텍스트 배정'); w.geometry('900x700')
        ttk.Label(w,text='원문의 필요한 부분을 선택하고 대상 입력란에 배정하세요. 원본 서식·수식·이미지는 원본 열기로 확인합니다.',wraplength=850,padding=10).pack(fill='x')
        bottom=ttk.Frame(w,padding=10); bottom.pack(side='bottom',fill='x')
        target=ttk.Combobox(bottom,values=list(self.assignment_targets()),state='readonly',width=40); target.pack(side='left',padx=5); target.current(0)
        box=tk.Text(w,wrap='word',font=('맑은 고딕',11)); box.pack(side='left',fill='both',expand=True,padx=10,pady=5)
        bar=ttk.Scrollbar(w,command=box.yview); bar.pack(side='right',fill='y'); box.configure(yscrollcommand=bar.set)
        box.insert('1.0',self.data.get('raw_text',''))
        def assign():
            try: selected=box.get('sel.first','sel.last')
            except tk.TclError: messagebox.showinfo('텍스트 선택','배정할 텍스트를 먼저 선택하세요.',parent=w); return
            self.assign_text(target.get(),selected)
            messagebox.showinfo('배정 완료','대상 입력란에 배정했습니다. 저장 전에 확인하세요.',parent=w)
        ttk.Button(bottom,text='선택 부분 배정',command=assign).pack(side='left',padx=5)
    def draw_records(self):
        for c in self.records.body.winfo_children(): c.destroy()
        body=self.records.body
        if not self.sid:
            ttk.Label(body,text='세트를 저장한 후 사용·기출 이력을 추가할 수 있습니다.').pack(anchor='w'); return
        self.data=self.store.get_set(self.sid)
        bar=ttk.Frame(body); bar.pack(fill='x')
        ttk.Button(bar,text='사용 이력 추가',command=lambda:self.add_record('usage')).pack(side='left',padx=4)
        ttk.Button(bar,text='기출 기록 추가',command=lambda:self.add_record('past')).pack(side='left',padx=4)
        def render(title,value):
            ttk.Label(body,text=title,font=('맑은 고딕',11,'bold')).pack(anchor='w',pady=(15,4))
            t=tk.Text(body,height=8,wrap='word',font=('맑은 고딕',10)); t.pack(fill='x')
            t.insert('1.0',value); t.configure(state='disabled')
        statuses='\n'.join(f"문항 {q['number']} ({q['id']}): 사용 {q['usage_status']}, 기출 {q['past_status']}, 폐기 {q['disposal_status']}" for q in self.data['questions'])
        render('문항별 상태 · 세트 사용 상태는 문항 이력을 합산합니다',statuses)
        render('사용 이력',json.dumps(self.data['usage'],ensure_ascii=False,indent=2))
        render('기출 기록',json.dumps(self.data['past'],ensure_ascii=False,indent=2))
        render('수정 이력 (변경 전·후 전체 보존)',json.dumps(self.store.history(self.sid),ensure_ascii=False,indent=2))
    def add_record(self,kind):
        if self.snapshot()!=self.initial:
            messagebox.showinfo('먼저 저장','현재 수정 내용을 저장한 후 이력을 추가하세요.',parent=self.window); return
        w=tk.Toplevel(self.window); w.title('사용 이력 추가' if kind=='usage' else '기출 기록 추가'); w.geometry('660x580')
        page=ScrollFrame(w); page.pack(fill='both',expand=True)
        if kind=='usage': specs=[('date','사용일 (YYYY-MM-DD)','entry',None),('name','시험명 / 연구명','entry',None),('kind','사용 구분','choice',['실제 시험','모의시험','연구','기타']),('scope','사용 범위','entry',None),('memo','메모','text',3)]
        else: specs=[('exam','시험명','entry',None),('year','출제 연도','entry',None),('round','회차','entry',None),('number','시험 문항 번호','entry',None),('public','공개 여부','choice',STATES),('memo','메모','text',3)]
        options=['세트 전체']+[f"문항 {q['number']} ({q['id']})" for q in self.data['questions']]
        form=Form(page.body,[('target','대상','choice',options)]+specs); form.set('target','세트 전체')
        form.set('kind','연구') if kind=='usage' else form.set('public','미확인')
        def submit():
            try:
                d=form.collect(int_keys=['year'] if kind=='past' else [])
                index=options.index(d.pop('target')); qid=None if index==0 else self.data['questions'][index-1]['id']
                if kind=='usage': self.store.add_usage(self.sid,qid,d)
                else: self.store.add_past(self.sid,qid,d)
                self.data=self.store.get_set(self.sid); self.set_form.load(self.data)
                for f,q in zip(self.question_forms,self.data['questions']): f.load(q)
                self.initial=self.snapshot(); self.draw_records(); self.on_saved(); w.destroy()
            except (ValueError,OSError) as e: messagebox.showerror('이력 저장',str(e),parent=w)
        ttk.Button(w,text='이력 저장',command=submit).pack(side='bottom',pady=10)
