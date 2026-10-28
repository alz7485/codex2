"""Create TEXT records from a PARAM preset with preview and collision protection."""
import copy
import tkinter as tk
from tkinter import ttk
from . import project,presets,parameter_catalog,catalog_workspace


def prepare(data,cate_id,preset_id):
    working=presets.get(data,preset_id) if preset_id else {'id':'','parameters':presets.rules(data,{'parameter_preset_id':''})}
    if not working:raise ValueError('PARAMプリセットが見つかりません。')
    rows=parameter_catalog.text_preview(data,working,cate_id)
    for row in rows:catalog_workspace.check_name(data,row['name'])
    candidate=copy.deepcopy(data)
    created=parameter_catalog.write_texts(candidate,working,cate_id,expected=rows)
    project.validate(candidate)
    return rows,created


def open_batch(host):
    if host.grab_current():host.grab_current().lift();return
    cate=project.get(host.data,'cates',host.cate_id)
    if not cate:return
    data=host.data;cate_id=cate['id'];window=tk.Toplevel(host)
    window.title('PARAMプリセットからTEXTを一括作成');window.geometry('660x460');window.minsize(500,340);window.transient(host);window.grab_set()
    body=ttk.Frame(window,padding=12);body.pack(fill='both',expand=True)
    ttk.Label(body,text='作成先 CATE：'+cate['name'],style='Heading.TLabel').pack(anchor='w')
    ttk.Label(body,text='各PARAMのSTEXTを使い、CATE名/PARAM番号 のTEXTを作成します。',style='Muted.TLabel').pack(anchor='w',pady=6)
    options=presets.choices(data);choice=tk.StringVar(value=next((n for n,i in options.items() if i==presets.selected_id(data)),next(iter(options),'')))
    window.preset_choice=ttk.Combobox(body,textvariable=choice,values=list(options),state='readonly');window.preset_choice.pack(fill='x')
    footer=ttk.Frame(body);footer.pack(side='bottom',fill='x',pady=(8,0))
    error=ttk.Label(body,text='',foreground='#bb6440',wraplength=610);error.pack(side='bottom',fill='x')
    table=host.table(body,[('param','PARAM',80),('name','TEXT名',260),('value','STEXT',260)],height=9)
    state={}
    def preview(_=None):
        state.clear();table.delete(*table.get_children());error.configure(text='')
        try:
            rows,created=prepare(data,cate_id,options[choice.get()])
            state.update(rows=rows,created=created,preset=options[choice.get()],snapshot=copy.deepcopy(data))
            for row in rows:table.insert('','end',values=(row['pid'],row['name'],row['STEXT']))
            window.create_button.configure(state='normal')
        except (ValueError,KeyError) as exc:error.configure(text=str(exc));window.create_button.configure(state='disabled')
    def create():
        if not state:return
        if host.data is not data or data!=state['snapshot']:
            error.configure(text='データが変更されています。プリセットを選び直してください。');return
        rows,created=prepare(data,cate_id,state['preset'])
        data['texts'].extend(created)
        host.catalog_member_key='texts:'+created[0]['id'];host.catalog_tab='members';host.cate_id=cate_id
        host.registered_browser.search.set('');window.destroy();host.mark('TEXTを'+str(len(created))+'件作成しました。');host.render_page()
    window.create_button=ttk.Button(footer,text='一括作成',command=create,style='Primary.TButton');window.create_button.pack(side='right')
    ttk.Button(footer,text='取消',command=window.destroy).pack(side='right',padx=6)
    window.preset_choice.bind('<<ComboboxSelected>>',preview);preview()
    return window
