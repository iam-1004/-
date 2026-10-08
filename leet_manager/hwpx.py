"""Text extraction and conservative candidates; never writes user data."""
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from .models import SET_DEFAULTS, QUESTION_DEFAULTS
import copy

MAX_UNCOMPRESSED=50*1024*1024
MAX_COMPRESSED=25*1024*1024
CIRCLES='①②③④⑤'

def extract_text(path):
    path=Path(path)
    if path.stat().st_size>MAX_COMPRESSED: raise ValueError('HWPX 파일이 너무 큽니다 (25 MB 제한).')
    try:
        with zipfile.ZipFile(path) as z:
            entries=z.infolist()
            if len(entries)>2000 or sum(i.file_size for i in entries)>MAX_UNCOMPRESSED:
                raise ValueError('압축 해제 크기가 너무 큽니다 (50 MB 제한).')
            sections=sorted([i for i in entries if re.fullmatch(r'Contents/section\d+\.xml',i.filename)],
                            key=lambda i:int(re.search(r'\d+',i.filename).group()))
            if not sections: raise ValueError('HWPX 문단 파일을 찾을 수 없습니다.')
            paragraphs=[]
            for info in sections:
                raw=z.read(info)
                # Decode before checking declarations so UTF-16 XML cannot bypass checks.
                encoding='utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) or b'\x00' in raw[:100] else 'utf-8-sig'
                xml=raw.decode(encoding)
                if re.search(r'<!\s*(DOCTYPE|ENTITY)',xml,re.I): raise ValueError('DTD/엔티티가 포함된 XML은 지원하지 않습니다.')
                root=ET.fromstring(xml)
                for p in root.iter():
                    if p.tag.rsplit('}',1)[-1]=='p':
                        parts=[]
                        for node in p.iter():
                            tag=node.tag.rsplit('}',1)[-1]
                            if tag=='t' and node.text: parts.append(node.text)
                            elif tag in ('lineBreak','br'): parts.append('\n')
                            elif tag=='tab': parts.append('\t')
                        if parts: paragraphs.append(''.join(parts))
            return '\n'.join(paragraphs)
    except (zipfile.BadZipFile, ET.ParseError, UnicodeError, RuntimeError, KeyError) as e:
        raise ValueError('손상되었거나 지원하지 않는 HWPX 파일입니다.') from e

def split_keywords(text):
    return [v.strip() for v in re.split(r'[,;、\n]',text) if v.strip()]

def _fields(text):
    labels='평가 목표|정답|제시문 근거|오답 근거|함정 유형|핵심 키워드|문항 성격|문항 풀이|정답 해설|오답 해설'
    matches=list(re.finditer(r'(?m)^\s*('+labels+r')\s*[:：]\s*',text))
    return {m.group(1):text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
            for i,m in enumerate(matches)}

def propose_sections(text):
    s=copy.deepcopy(SET_DEFAULTS); s.update(raw_text=text,warnings=[],questions=[])
    split=re.split(r'\[\s*해설\s*및\s*정답\s*\]',text,maxsplit=1)
    body=split[0]; explanations=split[1] if len(split)>1 else ''
    refs=re.search(r'(?m)^\s*참고문헌\s*[:：]?\s*',explanations)
    if refs: s['source']=explanations[refs.end():].strip(); explanations=explanations[:refs.start()]
    starts=list(re.finditer(r'(?m)^\s*([123])\s*[.．]\s*',body))
    if len(starts)!=3 or [int(m.group(1)) for m in starts]!=[1,2,3]:
        s['warnings'].append('문항 1·2·3 경계를 확정하지 못했습니다. 원문을 직접 배정하세요.')
        s['passage']=body.strip(); return s
    s['passage']=body[:starts[0].start()].strip()
    # Remove only the documented reading instruction, not arbitrary introductory content.
    marker=re.search(r'다음\s*글을\s*읽고\s*물음에\s*답하시오\.?',s['passage'])
    if marker: s['passage']=s['passage'][marker.end():].strip()
    expstarts=list(re.finditer(r'(?m)^\s*([123])\s*번\s*문항\s*해설\s*[:：]?\s*',explanations))
    common=explanations[:expstarts[0].start()] if expstarts else explanations
    s['keywords']=split_keywords(_fields(common).get('핵심 키워드',''))
    expmap={int(m.group(1)):explanations[m.end():expstarts[i+1].start() if i+1<len(expstarts) else len(explanations)].strip()
            for i,m in enumerate(expstarts)}
    for i,m in enumerate(starts):
        block=body[m.end():starts[i+1].start() if i+1<len(starts) else len(body)].strip()
        cs=list(re.finditer(r'(?m)^\s*([①②③④⑤])\s*',block))
        q=copy.deepcopy(QUESTION_DEFAULTS); q['number']=i+1
        head=block[:cs[0].start()].strip() if cs else block
        view=re.search(r'[<〈]\s*보기\s*[>〉]',head)
        q['prompt']=head[:view.start()].strip() if view else head
        q['view']=head[view.end():].strip() if view else ''
        q['choices']=[dict(text='',validity='미확인',explanation='') for _ in range(5)]
        if len(cs)==5 and ''.join(c.group(1) for c in cs)==CIRCLES:
            for j,c in enumerate(cs): q['choices'][j]['text']=block[c.end():cs[j+1].start() if j+1<5 else len(block)].strip()
        else: s['warnings'].append(f'{i+1}번 선택지 경계를 확인하세요. 원문에서 직접 배정할 수 있습니다.')
        exp=expmap.get(i+1,''); f=_fields(exp)
        q['solution']=exp
        q['objective']=f.get('평가 목표',''); q['evidence']=f.get('제시문 근거','')
        q['wrong_explanation']=f.get('오답 근거',f.get('오답 해설',''))
        q['wrong_heading']='오답 근거' if '오답 근거' in f else '오답 해설' if '오답 해설' in f else '오답 근거'
        q['trap']=f.get('함정 유형',''); q['character']=f.get('문항 성격','')
        q['keywords']=split_keywords(f.get('핵심 키워드',''))
        answer=re.search(r'[①②③④⑤1-5]',f.get('정답',''))
        if answer: q['answer']=CIRCLES.index(answer.group())+1 if answer.group() in CIRCLES else int(answer.group())
        else: s['warnings'].append(f'{i+1}번 정답은 미입력입니다.')
        s['questions'].append(q)
    s['warnings'].append('자동 분리 결과입니다. 제시문·보기·선택지·정답·해설을 확인하고 수정한 뒤 저장하세요. 타당성과 분류는 추정하지 않았습니다.')
    return s
