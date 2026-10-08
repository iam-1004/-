import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from leet_manager.ui import App
from leet_manager.editor import Editor
from leet_manager.store import Store
from test_store import questions
from test_hwpx import fixture

class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try: cls.root=tk.Tk(); cls.root.withdraw()
        except tk.TclError as e: raise unittest.SkipTest('GUI display unavailable: '+str(e))
    @classmethod
    def tearDownClass(cls): cls.root.destroy()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/'자료')
        self.app=App(self.root,self.store)
    def tearDown(self):
        for child in self.root.winfo_children(): child.destroy()
        self.store.close(); self.tmp.cleanup()
    def test_create_edit_and_id_display(self):
        e=Editor(self.root,self.store,on_saved=self.app.refresh)
        e.set_form.set('title','화면 한글')
        e.set_form.set('passage','제시문')
        for f,q in zip(e.question_forms,questions()):
            f.load(q)
        sid=e.save(close=False)
        self.assertIsNotNone(sid)
        self.assertTrue(e.question_forms[0].get('id').startswith('Q-'))
        self.assertEqual(self.store.get_set(sid)['questions'][2]['choices'][3]['validity'],'부적절')
        self.assertEqual(len(self.app.tree.get_children()),1)
        e.window.destroy()
    def test_import_assignment_confirm_and_cancel(self):
        p=Path(self.tmp.name)/'원본.hwpx'; fixture(p)
        from leet_manager.import_dialog import open_import
        e=open_import(self.root,self.store,p,self.app.refresh)
        e.set_form.set('title','가져오기')
        e.assign_text('문항 3 / 보기','사용자 확인 보기')
        self.assertEqual(e.question_forms[2].get('view'),'사용자 확인 보기')
        self.assertEqual(self.store.all_sets(),[])
        with patch('leet_manager.editor.messagebox.askyesno',return_value=True): sid=e.save(close=False)
        self.assertEqual(self.store.get_set(sid)['questions'][2]['view'],'사용자 확인 보기')
        e.window.destroy()
        # Reopening for inspection never creates another record.
        e=Editor(self.root,self.store); e.window.destroy()
        self.assertEqual(len(self.store.all_sets()),1)
    def test_question_view_and_filter(self):
        self.store.save_set({'title':'목록'},questions())
        self.app.filters['view'].set('문항')
        self.app.refresh()
        self.assertEqual(len(self.app.tree.get_children()),3)
        self.app.filters['type'].set('정보의 확인과 재구성'); self.app.refresh()
        self.assertEqual(len(self.app.tree.get_children()),0)
    def test_backup_restore_and_csv_buttons(self):
        self.store.save_set({'title':'버튼 검증'},questions())
        archive=Path(self.tmp.name)/'backup.zip'; csv=Path(self.tmp.name)/'rows.csv'
        with patch('leet_manager.ui.filedialog.asksaveasfilename',return_value=str(archive)), patch('leet_manager.ui.messagebox.showinfo'):
            self.app.backup()
        self.assertTrue(archive.exists())
        self.store.save_set({'title':'복원 후 없어질 자료'},questions())
        with patch('leet_manager.ui.filedialog.askopenfilename',return_value=str(archive)), patch('leet_manager.ui.messagebox.askyesno',return_value=True), patch('leet_manager.ui.messagebox.showinfo'):
            self.app.restore()
        self.assertEqual(len(self.store.all_sets()),1)
        with patch('leet_manager.ui.filedialog.asksaveasfilename',return_value=str(csv)), patch('leet_manager.ui.messagebox.showinfo'):
            self.app.export()
        self.assertIn('문항ID',csv.read_text(encoding='utf-8-sig'))
    def test_dirty_close_cancel_does_not_save(self):
        e=Editor(self.root,self.store)
        e.set_form.set('title','취소 자료')
        with patch('leet_manager.editor.messagebox.askyesnocancel',return_value=None): e.close()
        self.assertTrue(e.window.winfo_exists())
        self.assertEqual(self.store.all_sets(),[])
        with patch('leet_manager.editor.messagebox.askyesnocancel',return_value=False): e.close()
        self.assertEqual(self.store.all_sets(),[])
    def test_import_confirmation_declined_preserves_empty_store(self):
        p=Path(self.tmp.name)/'원본.hwpx'; fixture(p)
        from leet_manager.import_dialog import open_import
        e=open_import(self.root,self.store,p,self.app.refresh)
        with patch('leet_manager.editor.messagebox.askyesno',return_value=False):
            self.assertIsNone(e.save())
        self.assertEqual(self.store.all_sets(),[])
        self.assertEqual(list((self.store.data_dir/'originals').iterdir()),[])
