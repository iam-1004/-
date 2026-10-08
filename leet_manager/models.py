import copy
from datetime import datetime, date
from uuid import uuid4

TYPES = ['주제, 구조, 관점 파악','정보의 확인과 재구성','정보의 추론과 해석','정보의 평가와 적용']
STATES = ['미확인','예','아니요']
SUBJECTS = {'인문':['문학','역사','기타'], '사회':['정치학','경제학','사회학','기타'],
            '과학기술':['물리','화학','생물','기타'], '규범':['법학','철학','기타']}
SET_DEFAULTS = dict(title='', year=None, passage='', domain='', subject='', auxiliary_subjects=[], tags=[],
                    source='', author='', reviewer='', review_status='초안', memo='', keywords=[],
                    usage_status='미확인', past_status='미확인', disposal_status='미확인',
                    disposal_date='', disposal_reason='', original_name='', file_hash='', original_path='', raw_text='')
QUESTION_DEFAULTS = dict(prompt='', view='', type='', keywords=[], character='', objective='', solution='',
                         answer=None, evidence='', wrong_heading='오답 근거', wrong_explanation='', trap='',
                         difficulty='', rate=None, review_memo='', usage_status='미확인', past_status='미확인',
                         disposal_status='미확인', disposal_date='', disposal_reason='')

def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')

def new_id(prefix):
    return prefix + '-' + uuid4().hex

def validate_date(text,label):
    try:
        if date.fromisoformat(text).isoformat()!=text: raise ValueError()
    except (ValueError,TypeError): raise ValueError(label+'는 YYYY-MM-DD 형식의 실제 날짜여야 합니다.')

def normalize(data, questions, previous=None):
    s=copy.deepcopy(SET_DEFAULTS)
    s.update({k:copy.deepcopy(v) for k,v in data.items() if k in SET_DEFAULTS})
    if not s['title'].strip(): raise ValueError('세트 제목을 입력하세요.')
    if s['year'] is not None:
        if isinstance(s['year'],bool) or not isinstance(s['year'],int) or not 1 <= s['year'] <= 9999:
            raise ValueError('생성 연도는 1~9999 또는 미확인이어야 합니다.')
    if s['review_status'] not in ['초안','검토 중','검토 완료']: raise ValueError('검토 상태가 올바르지 않습니다.')
    for key in ['usage_status','past_status','disposal_status']:
        if s[key] not in STATES: raise ValueError('상태가 올바르지 않습니다.')
    if s['disposal_status']=='예' and (not s['disposal_date'] or not s['disposal_reason'].strip()):
        raise ValueError('폐기일과 사유를 입력하세요.')
    if s['disposal_date']: validate_date(s['disposal_date'],'세트 폐기일')
    old={q['number']:q for q in previous['questions']} if previous else {}
    normalized=[]; numbers=set()
    for item in questions:
        q=copy.deepcopy(QUESTION_DEFAULTS); q.update(copy.deepcopy(item))
        n=q.get('number')
        if n not in (1,2,3) or n in numbers: raise ValueError('문항 번호는 중복 없이 1~3이어야 합니다.')
        numbers.add(n)
        if n in old:
            if q.get('id',old[n]['id']) != old[n]['id']: raise ValueError('문항ID는 수정할 수 없습니다.')
            q['id']=old[n]['id']
        else:
            if q.get('id'): raise ValueError('문항ID는 자동 생성됩니다.')
            q['id']=new_id('Q')
        if q['answer'] is not None and (type(q['answer']) is not int or q['answer'] not in range(1,6)):
            raise ValueError('정답은 1~5 또는 미입력이어야 합니다.')
        if q['rate'] is not None and (not isinstance(q['rate'],(float,int)) or not 0<=q['rate']<=100):
            raise ValueError('실제 정답률은 0~100이어야 합니다.')
        if q['type'] and q['type'] not in TYPES: raise ValueError('문항 유형이 올바르지 않습니다.')
        choices=q.get('choices',[])
        if len(choices)>5: raise ValueError('선택지는 5개입니다.')
        q['choices']=[dict(text='',validity='미확인',explanation='',**{}) for _ in range(5)]
        for i,c in enumerate(choices):
            q['choices'][i].update(c)
            if q['choices'][i]['validity'] not in ['미확인','타당','부적절']: raise ValueError('선택지 타당성이 올바르지 않습니다.')
            q['choices'][i].pop('is_answer',None)
        for key in ['usage_status','past_status','disposal_status']:
            if q[key] not in STATES: raise ValueError('문항 상태가 올바르지 않습니다.')
        if q['disposal_status']=='예' and (not q['disposal_date'] or not q['disposal_reason'].strip()):
            raise ValueError('문항 폐기일과 사유를 입력하세요.')
        if q['disposal_date']: validate_date(q['disposal_date'],'문항 폐기일')
        normalized.append(q)
    if previous and set(old)-numbers: raise ValueError('기존 문항은 삭제할 수 없습니다. 폐기 상태를 사용하세요.')
    if s['review_status']=='검토 완료':
        if len(normalized)!=3 or not s['passage'].strip(): raise ValueError('검토 완료에는 제시문과 문항 3개가 필요합니다.')
        for q in normalized:
            if not q['prompt'].strip() or q['answer'] is None or not q['type'] or any(not c['text'].strip() for c in q['choices']):
                raise ValueError('검토 완료에는 각 발문, 선택지 5개, 정답, 문항 유형이 필요합니다.')
    return s,sorted(normalized,key=lambda q:q['number'])
