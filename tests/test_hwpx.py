import tempfile
import unittest
import zipfile
from pathlib import Path
from leet_manager.hwpx import extract_text, propose_sections
from leet_manager.import_service import import_confirmed
from leet_manager.store import Store
from test_store import questions

TEXT='''안내문
다음 글을 읽고 물음에 답하시오.
법치주의 제시문 [12면]
1. 적절한 것은?
① 하나
② 둘
③ 셋
④ 넷
⑤ 다섯
2. 추론으로 옳은 것은?
① 하나
② 둘
③ 셋
④ 넷
⑤ 다섯
3. 적절하지 않은 것은?
<보기>
보기 본문
① 하나
② 둘
③ 셋
④ 넷
⑤ 다섯
[해설 및 정답]
핵심 키워드: 법치주의, 자연법
1번 문항 해설
평가 목표: 이해
정답: ③
제시문 근거: 본문
오답 근거: 오답 해설 보존
2번 문항 해설
정답: ①
3번 문항 해설
정답: ④
함정 유형: 범위 확대
참고문헌
저서 1998년'''

def fixture(path,text=TEXT):
    import xml.etree.ElementTree as ET
    root=ET.Element('section')
    for line in text.splitlines():
        p=ET.SubElement(root,'p'); ET.SubElement(p,'t').text=line
    with zipfile.ZipFile(path,'w') as z: z.writestr('Contents/section0.xml',ET.tostring(root,encoding='utf-8'))

class HwpxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name); self.file=self.path/'한글.hwpx'
        fixture(self.file); self.store=Store(self.path/'data')
    def tearDown(self): self.store.close(); self.tmp.cleanup()
    def test_extraction_and_candidates(self):
        text=extract_text(self.file); self.assertIn('[12면]',text)
        candidate=propose_sections(text)
        self.assertEqual([q['answer'] for q in candidate['questions']],[3,1,4])
        self.assertEqual(candidate['questions'][2]['view'],'보기 본문')
        self.assertEqual(candidate['keywords'],['법치주의','자연법'])
        self.assertIn('1998',candidate['source']); self.assertIsNone(candidate['year'])
        self.assertEqual(candidate['questions'][0]['objective'],'이해')
        self.assertEqual(candidate['questions'][0]['wrong_explanation'],'오답 해설 보존')
        self.assertEqual(candidate['questions'][2]['trap'],'범위 확대')
        self.assertEqual(candidate['questions'][2]['choices'][3]['validity'],'미확인')
    def test_confirmed_copy_and_duplicate(self):
        data=propose_sections(extract_text(self.file)); data['title']='확인한 자료'
        sid=import_confirmed(self.store,self.file,data,data['questions'])
        original=self.store.data_dir/self.store.get_set(sid)['original_path']
        self.assertEqual(original.read_bytes(),self.file.read_bytes())
        with self.assertRaises(ValueError): import_confirmed(self.store,self.file,data,data['questions'])
        self.assertEqual(len(self.store.all_sets()),1)
    def test_candidate_does_not_register(self):
        propose_sections(extract_text(self.file))
        self.assertEqual(self.store.all_sets(),[])
        with self.assertRaises(ValueError): import_confirmed(self.store,self.file,{'title':''},questions())
        self.assertEqual(list((self.store.data_dir/'originals').iterdir()),[])
    def test_invalid_files_and_xml(self):
        for payload in ['<bad>', '<!DOCTYPE x [<!ENTITY a "evil">]><section/>']:
            with zipfile.ZipFile(self.file,'w') as z: z.writestr('Contents/section0.xml',payload)
            with self.assertRaises(ValueError): extract_text(self.file)
        self.file.write_text('not zip')
        with self.assertRaises(ValueError): extract_text(self.file)
    def test_unrecognized_is_preserved(self):
        c=propose_sections('구조가 다른 한글 원문')
        self.assertEqual(c['raw_text'],'구조가 다른 한글 원문')
        self.assertTrue(c['warnings'])
    def test_oversized_archive_is_rejected(self):
        from unittest.mock import patch
        with patch('leet_manager.hwpx.MAX_UNCOMPRESSED',10):
            with self.assertRaises(ValueError): extract_text(self.file)
