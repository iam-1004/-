import tempfile
import unittest
from pathlib import Path
from leet_manager.store import Store


def questions():
    return [dict(number=i, prompt=f'{i}. 적절하지 않은 것은?', type='정보의 평가와 적용',
                 keywords=['개별'], answer=a,
                 choices=[dict(text=f'선택지 {n}', validity='부적절' if n == a else '타당', explanation='해설') for n in range(1,6)])
            for i,a in enumerate([3,1,4],1)]

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.store = Store(self.path)
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def create(self, **fields):
        return self.store.save_set(dict(title='법치주의', passage='한글 제시문 [12면]' * 100, keywords=['공통'], **fields), questions())
    def test_persistence_ids_and_negative_answer(self):
        sid = self.create()
        data = self.store.get_set(sid)
        ids = [q['id'] for q in data['questions']]
        self.assertEqual(data['keywords'], ['공통'])
        self.assertEqual(data['usage_status'], '미확인')
        self.assertIsNone(data['year'])
        self.assertEqual(data['questions'][2]['answer'], 4)
        self.assertEqual(data['questions'][2]['choices'][3]['validity'], '부적절')
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual([q['id'] for q in self.store.get_set(sid)['questions']], ids)
        data['title'] = '변경 제목'
        self.store.save_set(data, data['questions'], sid)
        self.assertEqual([q['id'] for q in self.store.get_set(sid)['questions']], ids)
        self.assertGreaterEqual(len(self.store.history(sid)),2)
    def test_search_filters_and_disposal(self):
        sid = self.create()
        qid = self.store.get_set(sid)['questions'][0]['id']
        self.assertEqual(len(self.store.search('한글', {})),1)
        self.assertEqual(len(self.store.search(qid, {'view':'questions'})),1)
        self.assertEqual(len(self.store.search('개별', {'view':'questions','type':'정보의 평가와 적용'})),3)
        self.assertEqual(len(self.store.search('', {'year':1998})),0)
        data = self.store.get_set(sid)
        data.update(disposal_status='예', disposal_reason='검토 폐기', disposal_date='2026-10-08')
        self.store.save_set(data,data['questions'],sid)
        self.assertEqual(self.store.search('', {}),[])
        self.assertEqual(len(self.store.search('', {'include_disposed':True})),1)
    def test_usage_and_past_records_are_independent(self):
        sid=self.create()
        qid=self.store.get_set(sid)['questions'][0]['id']
        for name in ['연구 A','연구 B']:
            self.store.add_usage(sid,qid,dict(date='2026-10-08',name=name,kind='연구',scope='문항',memo=''))
        data=self.store.get_set(sid)
        self.assertEqual(len(data['usage']),2)
        self.assertEqual(data['past_status'],'미확인')
        self.assertEqual(data['questions'][0]['usage_status'],'예')
        self.assertEqual(data['questions'][1]['usage_status'],'미확인')
        self.assertEqual(data['usage_status'],'예')
        self.store.add_past(sid,qid,dict(exam='시험',year=2025,round='1',number='7',public='예'))
        self.assertEqual(len(self.store.get_set(sid)['past']),1)
    def test_validation_and_drafts(self):
        sid=self.store.save_set({'title':'초안'},[])
        self.assertEqual(self.store.get_set(sid)['questions'],[])
        for qs in [questions()[:2],questions()]:
            if len(qs)==3: qs[0]['answer']=6
            with self.assertRaises(ValueError):
                self.store.save_set({'title':'검토 완료','passage':'본문','review_status':'검토 완료'},qs)
        qs=questions(); qs[0]['rate']=101
        with self.assertRaises(ValueError): self.store.save_set({'title':'잘못된 정답률'},qs)
        self.assertEqual(len(self.store.search('',{})),1)
    def test_subject_management(self):
        self.store.add_subject('규범','사용자 과목')
        sid=self.create(domain='규범',subject='사용자 과목')
        with self.assertRaises(ValueError): self.store.delete_subject('규범','사용자 과목')
        self.assertIn('사용자 과목',self.store.subjects()['규범'])
    def test_question_ids_cannot_be_reassigned(self):
        sid=self.create(); data=self.store.get_set(sid)
        data['questions'][0]['id']='변경ID'
        with self.assertRaises(ValueError): self.store.save_set(data,data['questions'],sid)
    def test_unknown_is_not_unused(self):
        self.create()
        self.assertEqual(len(self.store.search('',{'usage_status':'아니요'})),0)
        self.assertEqual(len(self.store.search('',{'usage_status':'미확인'})),1)
