from .hwpx import extract_text,propose_sections
from .editor import Editor
from tkinter import ttk

def open_import(parent,store,path,on_saved=None):
    text=extract_text(path); data=propose_sections(text)
    data['title']=path.stem
    e=Editor(parent,store,data,on_saved,source=path)
    warning='\n'.join(data['warnings'])
    ttk.Label(e.window,text=warning,foreground='#9a5200',wraplength=940,padding=10).pack(side='bottom',fill='x')
    e.show_raw()
    return e
