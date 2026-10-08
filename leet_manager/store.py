import json
import sqlite3
from pathlib import Path
from .models import SUBJECTS, normalize, now, new_id, validate_date

def dumps(data):
    return json.dumps(data,ensure_ascii=False,sort_keys=True)

class Store:
    def __init__(self,data_dir):
        self.data_dir=Path(data_dir)
        self.data_dir.mkdir(parents=True,exist_ok=True)
        (self.data_dir/'originals').mkdir(exist_ok=True)
        self.db_path=self.data_dir/'data.sqlite3'
        self.connect()
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        INSERT OR IGNORE INTO metadata VALUES('schema_version','1');
        CREATE TABLE IF NOT EXISTS sets(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS questions(id TEXT PRIMARY KEY,set_id TEXT NOT NULL REFERENCES sets(id),number INTEGER NOT NULL,data TEXT NOT NULL,UNIQUE(set_id,number));
        CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY,set_id TEXT NOT NULL REFERENCES sets(id),question_id TEXT REFERENCES questions(id),data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS past(id INTEGER PRIMARY KEY,set_id TEXT NOT NULL REFERENCES sets(id),question_id TEXT REFERENCES questions(id),data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY,set_id TEXT NOT NULL REFERENCES sets(id),time TEXT NOT NULL,before_data TEXT,after_data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS subjects(domain TEXT, name TEXT, PRIMARY KEY(domain,name));
        ''')
        with self.db:
            for domain,names in SUBJECTS.items():
                self.db.executemany('INSERT OR IGNORE INTO subjects VALUES(?,?)',[(domain,n) for n in names])
    def connect(self):
        self.db=sqlite3.connect(self.db_path)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
    def close(self):
        self.db.close()
    def get_set(self,sid):
        row=self.db.execute('SELECT * FROM sets WHERE id=?',(sid,)).fetchone()
        if row is None: raise ValueError('세트를 찾을 수 없습니다.')
        s=json.loads(row['data']); s.update(id=sid,created_at=row['created_at'],updated_at=row['updated_at'])
        s['revision']=self.db.execute('SELECT COALESCE(MAX(id),0) FROM history WHERE set_id=?',(sid,)).fetchone()[0]
        s['questions']=[json.loads(r['data']) for r in self.db.execute('SELECT data FROM questions WHERE set_id=? ORDER BY number',(sid,))]
        for table in ['usage','past']:
            s[table]=[dict(json.loads(r['data']),record_id=r['id'],question_id=r['question_id']) for r in self.db.execute(f'SELECT * FROM {table} WHERE set_id=? ORDER BY id',(sid,))]
        for q in s['questions']:
            if any(r['question_id'] in (None,q['id']) for r in s['usage']): q['usage_status']='예'
            if any(r['question_id'] in (None,q['id']) for r in s['past']): q['past_status']='예'
            for i,c in enumerate(q['choices'],1): c['is_answer']=(i==q['answer'])
        if s['usage']: s['usage_status']='예'
        if s['past']: s['past_status']='예'
        return s
    def save_set(self,data,questions,set_id=None):
        previous=self.get_set(set_id) if set_id else None
        if previous and data.get('revision',previous['revision'])!=previous['revision']:
            raise ValueError('다른 편집창에서 자료가 변경되었습니다. 현재 입력을 복사해 보관하고 자료를 다시 열어 수정하세요.')
        s,qs=normalize(data,questions,previous)
        if previous:
            for key in ['original_name','file_hash','original_path','raw_text']:
                s[key]=previous[key]
        if s['domain'] and s['domain'] not in self.subjects(): raise ValueError('내용 영역을 확인하세요.')
        if s['subject'] and s['subject'] not in self.subjects().get(s['domain'],[]): raise ValueError('세부 과목을 추가하거나 올바른 과목을 선택하세요.')
        sid=set_id or new_id('S'); timestamp=now()
        with self.db:
            if previous:
                self.db.execute('UPDATE sets SET updated_at=?,data=? WHERE id=?',(timestamp,dumps(s),sid))
            else:
                self.db.execute('INSERT INTO sets VALUES(?,?,?,?)',(sid,timestamp,timestamp,dumps(s)))
            for q in qs:
                self.db.execute('INSERT INTO questions VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(q['id'],sid,q['number'],dumps(q)))
            self.db.execute('INSERT INTO history(set_id,time,before_data,after_data) VALUES(?,?,?,?)',
                            (sid,timestamp,dumps(previous) if previous else None,dumps(dict(s,questions=qs))))
        return sid
    def all_sets(self):
        return [self.get_set(r[0]) for r in self.db.execute('SELECT id FROM sets ORDER BY updated_at DESC')]
    def search(self,query='',filters=None):
        f=filters or {}; result=[]; view=f.get('view','sets')
        for s in self.all_sets():
            for q in (s['questions'] if view=='questions' else [None]):
                item=dict(s)
                if q: item.update(q); item.update(set_id=s['id'],title=s['title'],set_disposal_status=s['disposal_status'])
                disposed=s['disposal_status']=='예' or (q and q['disposal_status']=='예')
                if disposed and not f.get('include_disposed') and f.get('disposal_status')!='예': continue
                keys=['year','domain','subject','usage_status','past_status','disposal_status','review_status']
                if any(f.get(k) not in (None,'','전체') and item.get(k)!=(None if k=='year' and f[k]=='미확인' else f[k]) for k in keys): continue
                if f.get('type') and f['type']!='전체':
                    if q and q['type']!=f['type']: continue
                    if not q and not any(x['type']==f['type'] for x in s['questions']): continue
                searchable=[s['id'],s['title'],s['passage'],s['source'],s['keywords'],s['tags']]
                searchable+= [q] if q else s['questions']
                if query.casefold() not in dumps(searchable).casefold(): continue
                result.append(item)
        return result
    def _add_record(self,table,sid,qid,data):
        s=self.get_set(sid)
        if qid and qid not in [q['id'] for q in s['questions']]: raise ValueError('문항이 이 세트에 속하지 않습니다.')
        data=dict(data)
        if table=='usage':
            if not data.get('name','').strip() or not data.get('date'): raise ValueError('사용일과 시험명/연구명을 입력하세요.')
            validate_date(data['date'],'사용일')
        else:
            if not data.get('exam','').strip(): raise ValueError('시험명을 입력하세요.')
            if data.get('year') is not None and (type(data['year']) is not int or not 1<=data['year']<=9999): raise ValueError('출제 연도는 1~9999 또는 미확인이어야 합니다.')
        data['registered_at']=now()
        with self.db:
            self.db.execute(f'INSERT INTO {table}(set_id,question_id,data) VALUES(?,?,?)',(sid,qid,dumps(data)))
            self.db.execute('INSERT INTO history(set_id,time,before_data,after_data) VALUES(?,?,?,?)',(sid,now(),None,dumps({table:data,'question_id':qid})))
    def add_usage(self,set_id,question_id,data): self._add_record('usage',set_id,question_id,data)
    def add_past(self,set_id,question_id,data): self._add_record('past',set_id,question_id,data)
    def history(self,sid):
        return [dict(time=r['time'],before=json.loads(r['before_data']) if r['before_data'] else None,after=json.loads(r['after_data']))
                for r in self.db.execute('SELECT * FROM history WHERE set_id=? ORDER BY id DESC',(sid,))]
    def subjects(self):
        result={k:[] for k in SUBJECTS}
        for r in self.db.execute('SELECT * FROM subjects ORDER BY domain,name'): result.setdefault(r['domain'],[]).append(r['name'])
        return result
    def add_subject(self,domain,name):
        if domain not in SUBJECTS or not name.strip(): raise ValueError('내용 영역과 과목 이름을 확인하세요.')
        with self.db: self.db.execute('INSERT OR IGNORE INTO subjects VALUES(?,?)',(domain,name.strip()))
    def delete_subject(self,domain,name):
        if any(s['domain']==domain and (s['subject']==name or name in s['auxiliary_subjects']) for s in self.all_sets()):
            raise ValueError('자료가 사용하는 과목은 삭제할 수 없습니다.')
        with self.db: self.db.execute('DELETE FROM subjects WHERE domain=? AND name=?',(domain,name))
    def find_hash(self,digest):
        return next((s for s in self.all_sets() if s['file_hash']==digest),None)
