import json
import sqlite3
import tempfile
import unittest
import zipfile
import hashlib
from pathlib import Path
from leet_manager.store import Store
from leet_manager.backup import backup,restore
from leet_manager.export import export_csv
from test_store import questions

class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name); self.store=Store(self.path/'data')
        self.sid=self.store.save_set({'title':'원래 자료','passage':'본문'},questions())
    def tearDown(self): self.store.close(); self.tmp.cleanup()
    def test_csv_rejects_managed_destinations_without_modifying(self):
        original=self.store.data_dir/'originals'/'managed.hwpx'; original.write_bytes(b'original')
        for target in [self.store.db_path,original,self.store.data_dir/'data.sqlite3-wal']:
            before=target.read_bytes() if target.exists() else None
            with self.assertRaises(ValueError): export_csv(self.store,target,{})
            self.assertEqual(target.read_bytes() if target.exists() else None,before)
        self.assertEqual(self.store.get_set(self.sid)['title'],'원래 자료')
    def test_csv_atomic_failure_preserves_destination(self):
        from unittest.mock import patch
        destination=self.path/'previous.csv'; destination.write_text('previous')
        with patch('leet_manager.export.os.replace',side_effect=OSError('disk failure')):
            with self.assertRaises(OSError): export_csv(self.store,destination,{})
        self.assertEqual(destination.read_text(),'previous')
    def test_stale_edit_rejected_preserves_new_passage(self):
        a=self.store.get_set(self.sid); b=self.store.get_set(self.sid)
        a['passage']='저장한 새 제시문'; self.store.save_set(a,a['questions'],self.sid)
        b['memo']='다른 편집창 수정'
        with self.assertRaises(ValueError): self.store.save_set(b,b['questions'],self.sid)
        self.assertEqual(self.store.get_set(self.sid)['passage'],'저장한 새 제시문')
    def corrupt_backup(self,statement):
        good=backup(self.store,self.path/'good.zip')
        stage=self.path/'stage'; stage.mkdir(exist_ok=True)
        with zipfile.ZipFile(good) as z: payload={n:z.read(n) for n in z.namelist()}
        db=stage/'data.sqlite3'; db.write_bytes(payload['data.sqlite3'])
        conn=sqlite3.connect(db); conn.execute(statement); conn.commit(); conn.close()
        payload['data.sqlite3']=db.read_bytes()
        manifest=json.loads(payload['manifest.json']); manifest['files']['data.sqlite3']=hashlib.sha256(payload['data.sqlite3']).hexdigest()
        payload['manifest.json']=json.dumps(manifest).encode()
        bad=self.path/'bad.zip'
        with zipfile.ZipFile(bad,'w') as z:
            for name,raw in payload.items(): z.writestr(name,raw)
        return bad
    def test_restore_rejects_incompatible_schema(self):
        bad=self.corrupt_backup('ALTER TABLE usage RENAME COLUMN data TO invalid_data')
        with self.assertRaises(ValueError): restore(self.store,bad)
        self.store.add_usage(self.sid,None,{'name':'유지된 DB','date':'2026-10-08'})
        self.assertEqual(len(self.store.get_set(self.sid)['usage']),1)
    def test_restore_rejects_invalid_record_payload(self):
        self.store.add_usage(self.sid,None,{'name':'자료','date':'2026-10-08'})
        bad=self.corrupt_backup("UPDATE usage SET data='not JSON'")
        with self.assertRaises(ValueError): restore(self.store,bad)
        self.assertEqual(self.store.get_set(self.sid)['usage'][0]['name'],'자료')
    def test_restore_rejects_missing_set_fields(self):
        bad=self.corrupt_backup("UPDATE sets SET data=json_remove(data,'$.passage')")
        with self.assertRaises(ValueError): restore(self.store,bad)
        self.assertEqual(self.store.get_set(self.sid)['passage'],'본문')
    def test_restore_swap_failure_rolls_back(self):
        from unittest.mock import patch
        archive=backup(self.store,self.path/'good.zip')
        original_replace=Path.replace
        def fail_new_originals(path,target):
            if path.parent.name=='new' and path.name=='originals': raise OSError('simulated rename failure')
            return original_replace(path,target)
        with patch.object(Path,'replace',fail_new_originals):
            with self.assertRaises(OSError): restore(self.store,archive)
        self.assertEqual(self.store.get_set(self.sid)['title'],'원래 자료')
        self.store.add_usage(self.sid,None,{'name':'복구 성공','date':'2026-10-08'})
        self.assertEqual(len(self.store.get_set(self.sid)['usage']),1)
        self.assertTrue(list((self.store.data_dir/'backups').glob('*.zip')))
