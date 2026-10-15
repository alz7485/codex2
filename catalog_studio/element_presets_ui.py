"""Register, recall, and edit independent copies of whole element lists."""
import copy
import tkinter as tk
import uuid
from tkinter import messagebox,ttk
from . import element_library, presets, project


def register_current(editor):
    e=editor
    if not e.commit_inline() or not e.definition() or not e.definition()['elements']:return
    win=tk.Toplevel(e.winfo_toplevel());win.title('現在の要素一覧を登録');win.geometry('520x330');win.transient(e.winfo_toplevel());win.grab_set()
    body=ttk.Frame(win,padding=18);body.pack(fill='both',expand=True)
    ttk.Label(body,text='要素一覧全体をプリセット登録',style='Heading.TLabel').pack(anchor='w')
    ttk.Label(body,text=e.kind+' / '+str(len(e.definition()['elements']))+' 要素 / '+presets.label(e.data,e.definition()),wraplength=470,style='Muted.TLabel').pack(anchor='w',pady=10)
    name=tk.StringVar(value=e.definition()['name'].lstrip('/')+' の要素');description=tk.StringVar()
    for label,var in (('プリセット名',name),('説明',description)):
        ttk.Label(body,text=label).pack(anchor='w',pady=(8,3));ttk.Entry(body,textvariable=var).pack(fill='x')
    error=ttk.Label(body,text='',foreground='#bb6440',wraplength=470);error.pack(fill='x',pady=8)
    row=ttk.Frame(body);row.pack(side='bottom',fill='x')
    def apply():
        try:element_library.register(e.data,e.definition(),name.get(),description.get())
        except ValueError as exc:error.configure(text=str(exc));return
        e.host.mark('要素一覧をプリセット登録しました。プロジェクトを保存して残せます。');win.destroy();e.refresh()
    ttk.Button(row,text='登録',command=apply,style='Primary.TButton').pack(side='right')
    ttk.Button(row,text='キャンセル',command=win.destroy).pack(side='right',padx=8)
    return win


def choose(editor,mode='recall'):
    e=editor
    if not e.commit_inline():return
    records=[p for p in e.data.get('element_presets',[]) if p['kind']==e.kind]
    if not records:return
    win=tk.Toplevel(e.winfo_toplevel());win.title('要素プリセットを呼び出し' if mode=='recall' else '要素プリセットを編集');win.geometry('570x510');win.transient(e.winfo_toplevel());win.grab_set()
    body=ttk.Frame(win,padding=18);body.pack(fill='both',expand=True)
    ttk.Label(body,text='登録した要素一覧',style='Heading.TLabel').pack(anchor='w',pady=(0,10))
    choices={p['name']:p['id'] for p in records};choice=ttk.Combobox(body,values=list(choices),state='readonly');choice.pack(fill='x');choice.current(0)
    preview=tk.Text(body,height=9,wrap='word',font=(e.host.ui_font,10),relief='flat',bg='#f3f7fc');preview.pack(fill='both',expand=True,pady=12)
    def selected():return element_library.get(e.data,choices.get(choice.get()))
    def describe(_=None):
        record=selected();preview.configure(state='normal');preview.delete('1.0','end')
        if record:
            preview.insert('end',record['kind']+' / '+str(len(record['elements']))+' 要素\nPARAM：'+presets.label(e.data,record)+'\n'+record['description']+'\n\n')
            for index,element in enumerate(record['elements']):preview.insert('end',str(index+1)+'  '+element['type']+'  '+element['name']+'\n')
        preview.configure(state='disabled')
    choice.bind('<<ComboboxSelected>>',describe);describe()
    how=tk.StringVar(value='追加')
    if mode=='recall':
        row=ttk.Frame(body);row.pack(fill='x')
        for label in ('追加','一覧を置き換え'):ttk.Radiobutton(row,text=label,variable=how,value=label).pack(side='left',padx=(0,16))
    error=ttk.Label(body,text='',foreground='#bb6440',wraplength=530);error.pack(fill='x',pady=10)
    row=ttk.Frame(body);row.pack(fill='x')
    def apply():
        record=selected()
        if not record:return
        if mode=='edit':win.destroy();PresetEditor(e,record);return
        try:elements=element_library.recall(e.data,e.definition(),record['id'],replace=how.get()=='一覧を置き換え')
        except ValueError as exc:error.configure(text=str(exc));return
        e.element_id=elements[0]['id'] if elements else None;e.field=None;e.host.mark('要素プリセットをコピーして呼び出しました。');win.destroy();e.refresh()
    ttk.Button(row,text='呼び出す' if mode=='recall' else '編集を開く',command=apply,style='Primary.TButton').pack(side='right')
    ttk.Button(row,text='キャンセル',command=win.destroy).pack(side='right',padx=8)
    return win


class PresetEditor(tk.Toplevel):
    """Use the normal authoring UI on a draft, saved only by the save button."""
    def __init__(self,owner,record):
        super().__init__(owner.winfo_toplevel());self.owner=owner;self.record_id=record['id'];self.title('要素プリセットを編集');self.geometry('1280x900');self.minsize(1040,740);self.transient(owner.winfo_toplevel());self.grab_set()
        self.data=copy.deepcopy(owner.data);self.ui_font=owner.host.ui_font;self.dirty=False;self.is_preset_editor=True
        working={'id':uuid.uuid4().hex,'name':'プリセット：'+record['name'],'kind':record['kind'],'revision':'01','elements':copy.deepcopy(record['elements']),'parameter_preset_id':record['parameter_preset_id']}
        self.data['definitions'].append(working);self.definition_id=working['id'];self.scom_id=owner.preview_scom_id
        self.name_var=tk.StringVar(value=record['name']);self.description_var=tk.StringVar(value=record['description'])
        header=ttk.Frame(self,padding=(16,12));header.pack(fill='x')
        ttk.Label(header,text='プリセット名').pack(side='left');ttk.Entry(header,textvariable=self.name_var,width=35).pack(side='left',padx=8)
        ttk.Label(header,text='説明').pack(side='left');ttk.Entry(header,textvariable=self.description_var).pack(side='left',fill='x',expand=True,padx=8)
        ttk.Button(header,text='保存',command=self.save,style='Primary.TButton').pack(side='right')
        ttk.Button(header,text='キャンセル',command=self.destroy).pack(side='right',padx=8)
        self.status=ttk.Label(self,text='属性行をダブルクリックして編集できます。保存すると登録したプリセットを更新します。',style='Muted.TLabel',padding=12);self.status.pack(side='bottom',fill='x')
        self.content=ttk.Frame(self,padding=16);self.content.pack(fill='both',expand=True)
        from .construction_ui import ConstructionEditor
        self.geometry_editor=ConstructionEditor(self,record['kind'])
        for index in range(3):self.geometry_editor.element_preset_menu.entryconfigure(index,state='disabled')
        self.protocol('WM_DELETE_WINDOW',self.destroy)

    def mark(self,text='編集中です。「保存」でプリセットへ反映します。'):
        self.dirty=True;self.status.configure(text=text)

    def table(self,*args,**kwargs):return self.owner.host.table(*args,**kwargs)
    def balance(self,*args,**kwargs):return self.owner.host.balance(*args,**kwargs)
    @staticmethod
    def required(value,label):
        if not value:raise ValueError(label+'を入力してください。')
        return value
    def choices(self,collection,kind=None):return {r['name']:r['id'] for r in self.data.get(collection,[]) if kind is None or r.get('kind')==kind}

    def switch(self,page):
        messagebox.showinfo('プリセットの設定','PARAM の規則や SCOM の値はメイン画面で管理します。この画面では既存の規則と確認用 SCOM を選択できます。',parent=self)

    def form(self,title,fields,apply):
        win=tk.Toplevel(self);win.title(title);win.transient(self);win.grab_set();win.geometry('520x600')
        body=ttk.Frame(win,padding=16);body.pack(fill='both',expand=True);variables={}
        for key,label,value,choices in fields:
            ttk.Label(body,text=label).pack(anchor='w',pady=(6,3));var=tk.StringVar(value=str(value));variables[key]=var
            widget=ttk.Combobox(body,textvariable=var,values=choices,state='readonly') if choices is not None else ttk.Entry(body,textvariable=var)
            widget.pack(fill='x')
        error=ttk.Label(body,text='',foreground='#bb6440',wraplength=470);error.pack(fill='x',pady=10)
        def submit():
            try:apply({key:var.get().strip() for key,var in variables.items()})
            except ValueError as exc:error.configure(text=str(exc));return
            win.destroy();self.grab_set();self.mark();self.geometry_editor.refresh()
        ttk.Button(body,text='適用',command=submit,style='Primary.TButton').pack(side='bottom',fill='x')
        return win

    def save(self):
        if not self.geometry_editor.commit_inline():return
        try:element_library.update(self.owner.data,self.record_id,self.geometry_editor.definition(),self.name_var.get(),self.description_var.get())
        except ValueError as exc:self.status.configure(text=str(exc));return
        self.owner.host.mark('登録した要素プリセットを更新しました。');self.owner.refresh();self.destroy()
