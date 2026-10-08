"""Versioned, integrity-checked backups; validation happens before replacement."""
import hashlib
import json
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from pathlib import Path
from .models import now,normalize,validate_date,STATES,SUBJECTS,SET_DEFAULTS,QUESTION_DEFAULTS
from .paths import check_output_path

MAX_BACKUP_SIZE=1024*1024*1024

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def validate_directory(directory):
    directory=Path(directory)
    db=directory/'data.sqlite3'
    if not db.is_file(): raise ValueError('백업 데이터베이스가 없습니다.')
    try:
        connection=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)
        try:
            if connection.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('DB 무결성 오류입니다.')
            if connection.execute('SELECT value FROM metadata WHERE key="schema_version"').fetchone()!=('1',):
                raise ValueError('지원하지 않는 데이터 버전입니다.')
            required={'metadata','sets','questions','usage','past','history','subjects'}
            tables={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not required.issubset(tables): raise ValueError('필수 DB 테이블이 없습니다.')
            if connection.execute('PRAGMA foreign_key_check').fetchall(): raise ValueError('DB 참조 오류입니다.')
            validate_schema(connection)
            validate_records(connection)
            originals=set()
            for sid,raw in connection.execute('SELECT id,data FROM sets'):
                s=json.loads(raw)
                validate_payload(s,SET_DEFAULTS)
                qs=[]
                for qid,n,qraw in connection.execute('SELECT id,number,data FROM questions WHERE set_id=?',(sid,)):
                    q=json.loads(qraw)
                    validate_payload(q,QUESTION_DEFAULTS)
                    if not isinstance(q.get('id'),str) or type(q.get('number')) is not int: raise ValueError('문항 식별자 형식 오류입니다.')
                    if not isinstance(q.get('choices'),list) or len(q['choices'])!=5: raise ValueError('선택지 5개가 필요합니다.')
                    for choice in q['choices']:
                        if not isinstance(choice,dict) or any(not isinstance(choice.get(k),str) for k in ['text','validity','explanation']): raise ValueError('선택지 형식 오류입니다.')
                    if q.get('id')!=qid or q.get('number')!=n: raise ValueError('문항ID 또는 번호가 일치하지 않습니다.')
                    qs.append(q)
                normalize(s,qs,dict(s,questions=qs))
                rel=s.get('original_path','')
                if rel:
                    p=Path(rel)
                    if p.parts!=('originals',s.get('file_hash','')+'.hwpx') or len(s.get('file_hash',''))!=64:
                        raise ValueError('원본 경로가 올바르지 않습니다.')
                    target=directory/p
                    if not target.is_file() or target.is_symlink() or digest(target)!=s['file_hash']:
                        raise ValueError('원본 누락 또는 해시 오류입니다.')
                    originals.add(rel)
            return originals
        finally: connection.close()
    except (sqlite3.Error,KeyError,TypeError,json.JSONDecodeError,IndexError,AttributeError) as e:
        raise ValueError('백업 데이터베이스 구조가 올바르지 않습니다.') from e

def backup(store,destination):
    destination=check_output_path(store,destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='leet-backup-') as temp:
        stage=Path(temp); (stage/'originals').mkdir()
        conn=sqlite3.connect(stage/'data.sqlite3')
        try: store.db.backup(conn)
        finally: conn.close()
        for s in store.all_sets():
            if s['original_path']:
                rel=Path(s['original_path'])
                if rel.parts!=('originals',s['file_hash']+'.hwpx'): raise ValueError('잘못된 원본 경로입니다.')
                source=store.data_dir/rel
                if not source.is_file() or source.is_symlink() or digest(source)!=s['file_hash']:
                    raise ValueError('원본이 없거나 손상되었습니다. 백업을 중단했습니다.')
                shutil.copy2(source,stage/rel)
        validate_directory(stage)
        files={p.relative_to(stage).as_posix():digest(p) for p in stage.rglob('*') if p.is_file()}
        manifest=dict(version=1,created_at=now(),files=files)
        tempzip=destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.tmp')
        try:
            with zipfile.ZipFile(tempzip,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
                for name in files: z.write(stage/name,name)
            tempzip.replace(destination)
        finally: tempzip.unlink(missing_ok=True)
    return destination

def restore(store,source):
    source=Path(source)
    try:
        with tempfile.TemporaryDirectory(prefix='leet-restore-',dir=store.data_dir.parent) as temp:
            stage=Path(temp)/'new'; stage.mkdir(); (stage/'originals').mkdir()
            with zipfile.ZipFile(source) as z:
                infos=z.infolist(); names=[i.filename for i in infos]
                if len(infos)>10000 or len(set(names))!=len(names) or sum(i.file_size for i in infos)>MAX_BACKUP_SIZE:
                    raise ValueError('백업이 너무 크거나 중복 경로가 있습니다.')
                if 'manifest.json' not in names: raise ValueError('백업 manifest가 없습니다.')
                manifest=json.loads(z.read('manifest.json'))
                if manifest.get('version')!=1 or not isinstance(manifest.get('files'),dict): raise ValueError('지원하지 않는 백업 버전입니다.')
                files=manifest['files']
                if set(names)!=set(files)|{'manifest.json'} or 'data.sqlite3' not in files: raise ValueError('백업 파일 목록이 일치하지 않습니다.')
                for name,expected in files.items():
                    p=Path(name)
                    allowed=name=='data.sqlite3' or (len(p.parts)==2 and p.parts[0]=='originals' and p.name.endswith('.hwpx'))
                    if not allowed or '\\' in name or p.is_absolute() or '..' in p.parts: raise ValueError('안전하지 않은 백업 경로입니다.')
                    raw=z.read(name)
                    if hashlib.sha256(raw).hexdigest()!=expected: raise ValueError('백업 파일 해시가 일치하지 않습니다.')
                    (stage/p).write_bytes(raw)
            originals=validate_directory(stage)
            if set(files)!={'data.sqlite3'}|originals: raise ValueError('DB와 원본 목록이 일치하지 않습니다.')
            automatic=backup(store,store.data_dir/'backups'/('before-restore-'+uuid.uuid4().hex+'.zip'))
            old=Path(temp)/'old'; old.mkdir()
            store.close()
            moved=[]; installed=[]
            try:
                for name in ['data.sqlite3','originals']:
                    (store.data_dir/name).replace(old/name); moved.append(name)
                for name in ['data.sqlite3','originals']:
                    (stage/name).replace(store.data_dir/name); installed.append(name)
                store.connect()
            except Exception:
                for name in installed:
                    target=store.data_dir/name
                    if target.is_dir(): shutil.rmtree(target)
                    else: target.unlink(missing_ok=True)
                for name in moved: (old/name).replace(store.data_dir/name)
                store.connect()
                raise
            return automatic
    except (zipfile.BadZipFile,KeyError,TypeError,json.JSONDecodeError,UnicodeError,RuntimeError) as e:
        raise ValueError('손상되었거나 지원하지 않는 백업입니다.') from e

# Complete supported schema, not merely a list of table names. Compare SQLite's
# normalized column/constraint descriptions rather than textual CREATE SQL.
SCHEMA={
 'metadata':[('key','TEXT',0,1),('value','TEXT',1,0)],
 'sets':[('id','TEXT',0,1),('created_at','TEXT',1,0),('updated_at','TEXT',1,0),('data','TEXT',1,0)],
 'questions':[('id','TEXT',0,1),('set_id','TEXT',1,0),('number','INTEGER',1,0),('data','TEXT',1,0)],
 'usage':[('id','INTEGER',0,1),('set_id','TEXT',1,0),('question_id','TEXT',0,0),('data','TEXT',1,0)],
 'past':[('id','INTEGER',0,1),('set_id','TEXT',1,0),('question_id','TEXT',0,0),('data','TEXT',1,0)],
 'history':[('id','INTEGER',0,1),('set_id','TEXT',1,0),('time','TEXT',1,0),('before_data','TEXT',0,0),('after_data','TEXT',1,0)],
 'subjects':[('domain','TEXT',0,1),('name','TEXT',0,2)]}

def validate_schema(conn):
    entries=conn.execute('SELECT type,name FROM sqlite_master').fetchall()
    if any(kind in ('trigger','view') for kind,name in entries): raise ValueError('지원하지 않는 DB 뷰/트리거입니다.')
    if {name for kind,name in entries if kind=='table'}!=set(SCHEMA): raise ValueError('백업 테이블 구조가 일치하지 않습니다.')
    for table,expected in SCHEMA.items():
        actual=[(r[1],r[2].upper(),r[3],r[5]) for r in conn.execute('PRAGMA table_info('+table+')')]
        if actual!=expected: raise ValueError('백업 DB 열 구조가 일치하지 않습니다: '+table)
        expected_fk=set()
        if table in ('questions','usage','past','history'): expected_fk.add(('sets','set_id','id'))
        if table in ('usage','past'): expected_fk.add(('questions','question_id','id'))
        actual_fk={(r[2],r[3],r[4]) for r in conn.execute('PRAGMA foreign_key_list('+table+')')}
        if actual_fk!=expected_fk: raise ValueError('백업 DB 참조 구조가 일치하지 않습니다: '+table)
    unique=[]
    for r in conn.execute('PRAGMA index_list(questions)'):
        if r[2]:
            index_name=r[1].replace('"','""')
            unique.append(tuple(i[2] for i in conn.execute('PRAGMA index_info("'+index_name+'")')))
    if ('set_id','number') not in unique: raise ValueError('문항 번호 고유 제약이 없습니다.')

def validate_records(conn):
    for table in ['usage','past']:
        for sid,qid,raw in conn.execute('SELECT set_id,question_id,data FROM '+table):
            data=json.loads(raw)
            if not isinstance(data,dict): raise ValueError('이력 형식이 잘못되었습니다.')
            if qid:
                row=conn.execute('SELECT set_id FROM questions WHERE id=?',(qid,)).fetchone()
                if row!=(sid,): raise ValueError('문항 이력이 다른 세트에 연결되어 있습니다.')
            if table=='usage':
                if not isinstance(data.get('name'),str) or not data['name'].strip(): raise ValueError('사용 이름이 없습니다.')
                validate_date(data.get('date'),'사용일')
            else:
                if not isinstance(data.get('exam'),str) or not data['exam'].strip(): raise ValueError('기출 시험명이 없습니다.')
                if data.get('year') is not None and (type(data['year']) is not int or not 1<=data['year']<=9999): raise ValueError('기출 연도 오류입니다.')
                if data.get('public','미확인') not in STATES: raise ValueError('기출 공개 상태 오류입니다.')
    for before,after in conn.execute('SELECT before_data,after_data FROM history'):
        for raw in [before,after]:
            if raw is not None and not isinstance(json.loads(raw),dict): raise ValueError('수정 이력 형식이 잘못되었습니다.')
    for domain,name in conn.execute('SELECT domain,name FROM subjects'):
        if domain not in SUBJECTS or not isinstance(name,str) or not name.strip(): raise ValueError('과목 정보가 잘못되었습니다.')


def validate_payload(data,defaults):
    if not isinstance(data,dict) or not set(defaults).issubset(data): raise ValueError('백업 자료의 필수 필드가 없습니다.')
    for key,default in defaults.items():
        value=data[key]
        if isinstance(default,str) and not isinstance(value,str): raise ValueError('텍스트 필드 형식 오류: '+key)
        if isinstance(default,list) and (not isinstance(value,list) or any(not isinstance(v,str) for v in value)): raise ValueError('목록 필드 형식 오류: '+key)
