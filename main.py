"""No network services: start the local desktop application."""
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from leet_manager.store import Store
from leet_manager.ui import App
from leet_manager.instance import InstanceLock

def data_directory():
    if os.name=='nt': return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'LEETQuestionManager'
    return Path.home()/'.local'/'share'/'LEETQuestionManager'

def main():
    root=tk.Tk()
    store=None; lock=None
    try:
        lock=InstanceLock(data_directory()/'instance.lock')
        store=Store(data_directory()); app=App(root,store)
        def report_error(kind,value,traceback):
            messagebox.showerror('작업 실패',str(value)+'\n입력 내용은 확인 후 다시 저장하세요.',parent=root)
        root.report_callback_exception=report_error
        def close():
            if any(isinstance(w,tk.Toplevel) for w in root.winfo_children()):
                messagebox.showinfo('편집창 닫기','열린 자료 편집창을 먼저 저장하거나 닫으세요.',parent=root); return
            root.destroy()
        root.protocol('WM_DELETE_WINDOW',close)
        root.mainloop()
    except (ValueError,OSError) as e:
        messagebox.showerror('시작 실패',str(e),parent=root)
        root.destroy()
    finally:
        if store: store.close()
        if lock: lock.close()

if __name__=='__main__': main()
