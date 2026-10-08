"""Reusable scrollable labeled forms for long Korean source material."""
import tkinter as tk
from tkinter import ttk
from .hwpx import split_keywords

class ScrollFrame(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent)
        self.canvas=tk.Canvas(self,highlightthickness=0)
        scrollbar=ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y'); self.canvas.pack(side='left',fill='both',expand=True)
        self.body=ttk.Frame(self.canvas,padding=12)
        self.item=self.canvas.create_window((0,0),window=self.body,anchor='nw')
        self.body.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.item,width=e.width))
        # The scrollbar remains usable while Text widgets keep their own scrolling.

class Form:
    def __init__(self,parent,specs):
        self.widgets={}; self.labels={}; self.specs=specs
        parent.columnconfigure(1,weight=1)
        for row,(key,label,kind,options) in enumerate(specs):
            self.labels[key]=label
            ttk.Label(parent,text=label,wraplength=150).grid(row=row,column=0,sticky='nw',padx=(0,10),pady=5)
            if kind=='text':
                frame=ttk.Frame(parent); frame.grid(row=row,column=1,sticky='ew',pady=5)
                widget=tk.Text(frame,height=options or 4,wrap='word',undo=True,font=('맑은 고딕',10))
                bar=ttk.Scrollbar(frame,command=widget.yview); widget.configure(yscrollcommand=bar.set)
                widget.pack(side='left',fill='both',expand=True); bar.pack(side='right',fill='y')
            elif kind=='choice':
                widget=ttk.Combobox(parent,values=options,state='readonly')
                widget.grid(row=row,column=1,sticky='ew',pady=5)
            else:
                widget=ttk.Entry(parent)
                if kind=='readonly': widget.configure(state='readonly')
                widget.grid(row=row,column=1,sticky='ew',pady=5)
            self.widgets[key]=widget
    def get(self,key):
        widget=self.widgets[key]
        return widget.get('1.0','end-1c') if isinstance(widget,tk.Text) else widget.get()
    def set(self,key,value):
        widget=self.widgets[key]
        if isinstance(value,list): value=', '.join(str(v) for v in value)
        if value is None: value=''
        value=str(value)
        if isinstance(widget,tk.Text): widget.delete('1.0','end'); widget.insert('1.0',value)
        else:
            if isinstance(widget,ttk.Combobox): widget.set(value)
            else:
                readonly=str(widget.cget('state'))=='readonly'
                if readonly: widget.configure(state='normal')
                widget.delete(0,'end'); widget.insert(0,value)
                if readonly: widget.configure(state='readonly')
    def load(self,data):
        for key in self.widgets:
            if key in data: self.set(key,data[key])
    def snapshot(self): return {key:self.get(key) for key in self.widgets}
    def collect(self,list_keys=(),int_keys=(),float_keys=()):
        result=self.snapshot()
        for key in list_keys:
            if key in result: result[key]=split_keywords(result[key])
        for keys,converter in [(int_keys,int),(float_keys,float)]:
            for key in keys:
                if key in result:
                    text=result[key].strip()
                    try: result[key]=converter(text) if text else None
                    except ValueError as e: raise ValueError(self.labels[key]+'는 숫자로 입력하세요. 미확인은 비워 두세요.') from e
        return result
