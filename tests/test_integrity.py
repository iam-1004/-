import tempfile
import unittest
from pathlib import Path
from leet_manager.store import Store
from test_store import questions

class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name))
    def tearDown(self): self.store.close(); self.tmp.cleanup()
    def test_unknown_year_filter(self):
        self.store.save_set({'title':'미확인'},questions())
        self.store.save_set({'title':'1998','year':1998},questions())
        self.assertEqual(len(self.store.search('',{'year':'미확인'})),1)
    def test_invalid_dates_and_past_year(self):
        sid=self.store.save_set({'title':'자료'},questions())
        with self.assertRaises(ValueError):
            self.store.add_usage(sid,None,{'name':'연구','date':'2026-02-31'})
        with self.assertRaises(ValueError):
            self.store.add_past(sid,None,{'exam':'시험','year':-1})
        with self.assertRaises(ValueError):
            self.store.save_set({'title':'폐기','disposal_status':'예','disposal_date':'invalid','disposal_reason':'사유'},questions())
    def test_second_instance_is_rejected_and_releases(self):
        from leet_manager.instance import InstanceLock
        lock=InstanceLock(Path(self.tmp.name)/'instance.lock')
        try:
            with self.assertRaises(ValueError): InstanceLock(Path(self.tmp.name)/'instance.lock')
        finally: lock.close()
        again=InstanceLock(Path(self.tmp.name)/'instance.lock'); again.close()
