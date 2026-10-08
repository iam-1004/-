import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from leet_manager.store import Store
from leet_manager.backup import backup,restore
from leet_manager.export import export_csv
from leet_manager.import_service import import_confirmed
from test_hwpx import fixture
from test_store import questions

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name); self.store=Store(self.path/'자료')
        p=self.path/'원본.hwpx'; fixture(p)
        self.sid=import_confirmed(self.store,p,{'title':'백업 한글','passage':'본문','keywords':['공통']},questions())
        self.store.add_usage(self.sid,None,dict(date='2026-10-08',name='연구'))
    def tearDown(self): self.store.close(); self.tmp.cleanup()
    def test_backup_restore_and_original(self):
        before=self.store.get_set(self.sid); b=backup(self.store,self.path/'백업.zip')
        data=self.store.get_set(self.sid); data['title']='수정'
        self.store.save_set(data,data['questions'],self.sid)
        automatic=restore(self.store,b)
        self.assertTrue(automatic.exists())
        after=self.store.get_set(self.sid)
        self.assertEqual(after['title'],'백업 한글')
        self.assertEqual(after['questions'],before['questions'])
        self.assertEqual(len(after['usage']),1)
        self.assertEqual(hashlib.sha256((self.store.data_dir/after['original_path']).read_bytes()).hexdigest(),after['file_hash'])
        restore(self.store,b)
        self.assertEqual(len(self.store.all_sets()),1)
    def test_invalid_restore_preserves_current(self):
        b=backup(self.store,self.path/'good.zip')
        with zipfile.ZipFile(b) as z: payload={n:z.read(n) for n in z.namelist()}
        for key,value in [('data.sqlite3',b'bad db'),('../evil',b'escape'),('originals/fake.hwpx',b'bad')]:
            changed=dict(payload); changed[key]=value
            bad=self.path/'bad.zip'
            with zipfile.ZipFile(bad,'w') as z:
                for n,v in changed.items(): z.writestr(n,v)
            with self.assertRaises(ValueError): restore(self.store,bad)
            self.assertEqual(self.store.get_set(self.sid)['title'],'백업 한글')
    def test_backup_rejects_corrupt_original(self):
        s=self.store.get_set(self.sid); (self.store.data_dir/s['original_path']).write_bytes(b'corrupt')
        with self.assertRaises(ValueError): backup(self.store,self.path/'bad.zip')
    def test_csv_ids_keywords_and_formula(self):
        import csv
        d=self.store.get_set(self.sid); d['title']='=수식'; d['questions'][0]['prompt']='@danger'
        self.store.save_set(d,d['questions'],self.sid)
        p=self.path/'한글.csv'
        self.assertEqual(export_csv(self.store,p,{}),3)
        self.assertTrue(p.read_bytes().startswith(b'\xef\xbb\xbf'))
        with p.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
        self.assertEqual(rows[0]['세트ID'],self.sid)
        self.assertTrue(rows[0]['문항ID'].startswith('Q-'))
        self.assertEqual(rows[0]['공통 키워드'],'공통')
        self.assertEqual(rows[0]['문항 키워드'],'개별')
        self.assertEqual(rows[0]['제목'],"'=수식")
        self.assertEqual(rows[0]['발문'],"'@danger")
