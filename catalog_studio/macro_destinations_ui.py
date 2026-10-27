"""Edit per-kind macro destinations in a compact, cancellable dialog."""
import tkinter as tk
from tkinter import ttk
from . import macro_destinations as destinations


def edit_destinations(editor):
    host=editor.host
    if host.grab_current():
        host.grab_current().lift();return
    data=host.data;kind=editor.kind
    try:values=destinations.options(data,kind)
    except ValueError:
        values=[destinations.get(data,kind)]
    win=tk.Toplevel(host);win.title(kind+'：登録先編集');win.geometry('460x340');win.minsize(360,260)
    win.transient(host);win.grab_set();win.variables=[]
    body=ttk.Frame(win,padding=12);body.pack(fill='both',expand=True)
    ttk.Label(body,text=kind+'の登録先',style='Heading.TLabel').pack(anchor='w')
    ttk.Label(body,text='＋で入力欄を追加します。先頭の / は自動補完します。',style='Muted.TLabel').pack(anchor='w',pady=(4,8))
    footer=ttk.Frame(body);footer.pack(side='bottom',fill='x',pady=(8,0))
    error=ttk.Label(body,text='',foreground='#bb6440',wraplength=410);error.pack(side='bottom',fill='x')
    area=ttk.Frame(body);area.pack(fill='both',expand=True)
    canvas=tk.Canvas(area,height=150,highlightthickness=0);canvas.pack(side='left',fill='both',expand=True)
    scroll=ttk.Scrollbar(area,command=canvas.yview);scroll.pack(side='right',fill='y');canvas.configure(yscrollcommand=scroll.set)
    rows=ttk.Frame(canvas);item=canvas.create_window(0,0,window=rows,anchor='nw')
    rows.bind('<Configure>',lambda _:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
    def add(value=''):
        row=ttk.Frame(rows);row.pack(fill='x',pady=3)
        variable=tk.StringVar(value=value);win.variables.append(variable)
        entry=ttk.Entry(row,textvariable=variable);entry.pack(side='left',fill='x',expand=True)
        def remove():win.variables.remove(variable);row.destroy()
        ttk.Button(row,text='×',width=2,command=remove).pack(side='left',padx=(6,0))
        entry.bind('<FocusOut>',lambda _:variable.set(destinations.normalize(variable.get(),strict=False)))
        if not value:
            entry.focus_set();host.after_idle(lambda:canvas.yview_moveto(1) if canvas.winfo_exists() else None)
    def save():
        if host.data is not data:error.configure(text='プロジェクトが変更されています。閉じて開き直してください。');return
        try:destinations.save_options(data,kind,[v.get() for v in win.variables])
        except ValueError as exc:error.configure(text=str(exc));return
        host.mark('登録先リストを保存しました。');win.destroy()
    win.add_button=ttk.Button(footer,text='＋',width=3,command=add);win.add_button.pack(side='left')
    win.save_button=ttk.Button(footer,text='保存',command=save,style='Primary.TButton');win.save_button.pack(side='right')
    ttk.Button(footer,text='取消',command=win.destroy).pack(side='right',padx=6)
    for value in values or ['']:add(value)
    return win
