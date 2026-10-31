"""Read/save companion macros, sharing the standard tone and destination editor."""
import copy
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from types import SimpleNamespace
from . import companion_macro,macro_import,macro_export,macro_destinations,project


def import_macro(editor):
    if not editor.finish():return
    host=editor.host;cate=editor.cates.get(editor.cate.get())
    path=filedialog.askopenfilename(parent=host,title='SDTE/CMPT：マクロ読込',filetypes=[('E3D macro','*.mac *.txt'),('すべて','*')])
    if not path:return
    try:
        text,_=macro_import.read_text(path)
        candidate,targets=companion_macro.import_text(host.data,text,cate)
    except (ValueError,OSError) as exc:messagebox.showerror('読込できません',str(exc),parent=host);return
    host.data=candidate;host.mark('SDTE/CMPTマクロを読み込みました。');editor.refresh(targets[0][1])


def edit_destinations(editor,kind):
    if not editor.finish():return
    from .macro_destinations_ui import edit_destinations as edit
    return edit(SimpleNamespace(host=editor.host,kind=kind))


def export_macro(editor):
    if not editor.finish():return
    row=editor.rows.get(next(iter(editor.tree.selection()),''))
    if not row:editor.host.status.configure(text='出力するSDTEまたはCMPTを選択してください。');return
    col,record,index=row;host=editor.host;data=host.data;ident=record['id'];snapshot=copy.deepcopy(record)
    kind='SDTE' if col=='catalog_details' else 'CMPT'
    try:
        choices=macro_destinations.options(data,kind)
        companion_macro.creation_text(data,col,ident,choices[0] if choices else '')
    except ValueError as exc:messagebox.showerror('出力できません',str(exc),parent=host);return
    win=tk.Toplevel(host);win.title(kind+'：マクロ出力');win.geometry('800x600');win.transient(host);win.grab_set()
    ttk.Label(win,text=record['name']+'\n'+('CMPTYPEと配下のCMPDATAをまとめて出力します。' if kind=='CMPT' else '単独SDTEXTを出力します。'),padding=12).pack(anchor='w')
    bar=ttk.Frame(win,padding=(12,0,12,8));bar.pack(fill='x');ttk.Label(bar,text='登録先').pack(side='left')
    win.destination=tk.StringVar(value=choices[0] if choices else '')
    combo=ttk.Combobox(bar,textvariable=win.destination,values=choices,state='readonly' if choices else 'disabled');combo.pack(side='left',fill='x',expand=True,padx=8)
    if not choices:ttk.Label(bar,text='未登録：現在要素に作成',style='Muted.TLabel').pack(side='left')
    win.lock=tk.BooleanVar(value=False)
    option=ttk.Checkbutton(win,text='作成要素をロック（読込済みのLOCKは常に保持）',variable=win.lock);option.pack(anchor='w',padx=12)
    footer=ttk.Frame(win,padding=12);footer.pack(side='bottom',fill='x')
    area=ttk.Frame(win,padding=12);area.pack(fill='both',expand=True)
    win.source=tk.Text(area,wrap='none',font=('Consolas',10));win.source.grid(row=0,column=0,sticky='nsew')
    vertical=ttk.Scrollbar(area,command=win.source.yview);vertical.grid(row=0,column=1,sticky='ns')
    horizontal=ttk.Scrollbar(area,orient='horizontal',command=win.source.xview);horizontal.grid(row=1,column=0,sticky='ew')
    win.source.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set);area.columnconfigure(0,weight=1);area.rowconfigure(0,weight=1)
    def source():
        if host.data is not data or project.get(data,col,ident)!=snapshot:raise ValueError('出力対象が変更されています。閉じて開き直してください。')
        return companion_macro.creation_text(data,col,ident,win.destination.get(),win.lock.get())
    def refresh(_=None):
        try:text=source()
        except ValueError as exc:messagebox.showerror('出力できません',str(exc),parent=win);return
        win.source.configure(state='normal');win.source.delete('1.0','end');win.source.insert('1.0',text);win.source.configure(state='disabled')
    def save():
        path=filedialog.asksaveasfilename(parent=win,defaultextension='.mac',filetypes=[('E3D macro','*.mac')])
        if not path:return
        try:macro_export.save(path,source())
        except (ValueError,OSError) as exc:messagebox.showerror('出力できません',str(exc),parent=win);return
        win.destroy();host.status.configure(text='Shift-JIS（CP932）でマクロを保存しました。')
    option.configure(command=refresh);combo.bind('<<ComboboxSelected>>',refresh);refresh()
    win.save_button=ttk.Button(footer,text='保存',style='Primary.TButton',command=save);win.save_button.pack(side='right')
    ttk.Button(footer,text='取消',style='AttributeTool.TButton',command=win.destroy).pack(side='right',padx=8)
    return win
