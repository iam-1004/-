import csv
import os
import tempfile
from .paths import check_output_path
from pathlib import Path

def safe(value):
    if value is None or value=='': return '미확인'
    if isinstance(value,list): value='; '.join(str(v) for v in value)
    value=str(value)
    if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')): return "'"+value
    return value

def export_csv(store,destination,filters=None):
    destination=check_output_path(store,destination)
    f=dict(filters or {},view='questions')
    sets={s['id']:s for s in store.all_sets()}
    rows=[]
    for q in store.search(f.pop('query',''),f):
        s=sets[q['set_id']]
        row={'세트ID':s['id'],'문항ID':q['id'],'세트 내 번호':q['number'],'제목':s['title'],
             '생성 연도':s['year'],'등록 시각':s['created_at'],'내용 영역':s['domain'],'세부 과목':s['subject'],
             '보조 과목':s['auxiliary_subjects'],'검색 태그':s['tags'],'원문 출처':s['source'],'작성자':s['author'],
             '검토자':s['reviewer'],'검토 상태':s['review_status'],'세트 메모':s['memo'],'제시문':s['passage'],
             '공통 키워드':s['keywords'],'문항 키워드':q['keywords'],'문항 유형':q['type'],'발문':q['prompt'],
             '보기':q['view'],'문항 성격':q['character'],'평가 목표':q['objective'],'문항 풀이':q['solution'],
             '정답':q['answer'],'정답 근거':q['evidence'],'원문 오답 표제':q['wrong_heading'],
             '원문 오답 해설':q['wrong_explanation'],'함정 유형':q['trap'],'예상 난이도':q['difficulty'],
             '실제 정답률':q['rate'],'검토 메모':q['review_memo'],'사용 여부':q['usage_status'],
             '기출 여부':q['past_status'],'폐기 여부':q['disposal_status'],'세트 폐기 여부':s['disposal_status'],
             '폐기일':q['disposal_date'],'폐기 사유':q['disposal_reason'],'원본 이름':s['original_name'],'파일 해시':s['file_hash']}
        for n,c in enumerate(q['choices'],1):
            row.update({f'선택지 {n}':c['text'],f'선택지 {n} 타당성':c['validity'],f'선택지 {n} 정답 여부':'예' if c['is_answer'] else '아니요',f'선택지 {n} 해설':c['explanation']})
        rows.append({k:safe(v) for k,v in row.items()})
    fields=list(rows[0]) if rows else ['세트ID','문항ID','세트 내 번호','제목']
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8-sig',newline='',dir=destination.parent,delete=False,prefix='.leet-csv-') as out:
            temporary=Path(out.name)
            writer=csv.DictWriter(out,fieldnames=fields); writer.writeheader(); writer.writerows(rows)
            out.flush(); os.fsync(out.fileno())
        os.replace(temporary,destination)
    finally:
        if temporary: temporary.unlink(missing_ok=True)
    return len(rows)
