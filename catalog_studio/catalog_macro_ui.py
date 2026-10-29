"""Catalogue macro menu dialogs."""
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import catalog_macro,macro_import,macro_export,macro_destinations


def import_macro(host):
    path=filedialog.askopenfilename(parent=host,title='カタログマクロ読込',filetypes=[('E3D macro','*.mac *.txt'),('All','*')])
    if not path:return
    try:
        text,_=macro_import.read_text(path)
        candidate,ids=catalog_macro.import_text(host.data,text,host.cate_id or '')
    except (ValueError,OSError) as exc:messagebox.showerror('読込エラー',str(exc),parent=host);return
    host.data=candidate
    ident=ids[0]
    collection=next(col for col in ('cates','catalog_details','catalog_props') if any(r['id']==ident for r in candidate.get(col,[])))
    record=next(r for r in candidate[collection] if r['id']==ident)
    host.cate_id=ident if collection=='cates' else record['cate_id'];host.scom_id=None
    host.catalog_tab='scom' if collection=='cates' else 'members'
    key=collection+':'+ident
    host.registered_browser.catalog_target=key
    if collection!='cates':host.catalog_member_key=key
    host.render_page();host.mark('カタログマクロを読み込みました。外部参照は名前を保持します。')



def export_macro(host):
    data=host.data;ident=host.cate_id
    choices=macro_destinations.options(data,'CATE')
    try:source=catalog_macro.creation_text(data,ident,choices[0] if choices else '')
    except ValueError as exc:messagebox.showerror('出力エラー',str(exc),parent=host);return
    win=tk.Toplevel(host);win.title('カタログ：マクロ出力');win.geometry('760x580');win.transient(host);win.grab_set()
    bar=ttk.Frame(win,padding=10);bar.pack(fill='x')
    ttk.Label(bar,text='登録先').pack(side='left')
    value=tk.StringVar(value=choices[0] if choices else '')
    combo=ttk.Combobox(bar,textvariable=value,values=choices,state='readonly' if choices else 'disabled');combo.pack(side='left',fill='x',expand=True,padx=8)
    ttk.Label(win,text='CATE・SDTE・TEXT・SCOMをCP932で出力。DETAIL・PROPは対象外。',padding=8).pack(anchor='w')
    body=tk.Text(win,wrap='none');body.pack(fill='both',expand=True,padx=10)
    def refresh(_=None):
        body.configure(state='normal');body.delete('1.0','end');body.insert('1.0',catalog_macro.creation_text(data,ident,value.get()));body.configure(state='disabled')
    refresh();combo.bind('<<ComboboxSelected>>',refresh)
    def save():
        path=filedialog.asksaveasfilename(parent=win,defaultextension='.mac',filetypes=[('E3D macro','*.mac')])
        if not path:return
        try:macro_export.save(path,catalog_macro.creation_text(data,ident,value.get()))
        except (ValueError,OSError) as exc:messagebox.showerror('出力エラー',str(exc),parent=win);return
        win.destroy();host.status.configure(text='マクロを保存しました：'+path)
    ttk.Button(win,text='保存',command=save).pack(side='right',padx=10,pady=10)
    ttk.Button(win,text='取消',command=win.destroy).pack(side='right')
    return win
