"""Create CATE, SDTE, preset TEXT records and one SCOM atomically."""
import copy
import tkinter as tk
from tkinter import ttk
from . import project, catalogue, presets, catalog_workspace, catalog_text_batch, browser_folders


def prepare(data,preset_id,anchor=''):
    candidate=copy.deepcopy(data)
    if preset_id and not presets.get(candidate,preset_id):raise ValueError('PARAMプリセットが見つかりません。')
    number=1
    while True:
        name=f'新しいCATE({number})'
        names=(name,name+'/SDTE',name+'/SCOM')
        try:
            for n in names:catalog_workspace.check_name(candidate,n)
            break
        except ValueError:number+=1
    cate=project.add_cate(candidate,name)
    browser_folders.place_created(candidate,'catalog','cates:'+cate['id'],anchor)
    sdte=catalogue.add_record(candidate,'texts','SDTE',name+'/SDTE',cate['id'])
    rows,texts=catalog_text_batch.prepare(candidate,cate['id'],preset_id)
    candidate['texts'].extend(texts)
    scom=project.add_scom(candidate,cate['id'],name+'/SCOM')
    scom.update(parameter_preset_id=preset_id,gmset_id='',ptset_id='',values={})
    project.validate(candidate)
    return candidate,{'CATE':cate,'SDTE':sdte,'TEXT':texts,'SCOM':scom},rows


def open_bundle(host,anchor=''):
    if host.grab_current():host.grab_current().lift();return
    data=host.data;options=presets.choices(data)
    win=tk.Toplevel(host);win.title('CATE一式作成');win.geometry('560x350');win.minsize(460,280)
    win.transient(host);win.grab_set()
    body=ttk.Frame(win,padding=12);body.pack(fill='both',expand=True)
    ttk.Label(body,text='PARAMプリセット',style='Heading.TLabel').pack(anchor='w')
    choice=tk.StringVar(value=next((n for n,i in options.items() if i==presets.selected_id(data)),next(iter(options))))
    win.preset_choice=ttk.Combobox(body,textvariable=choice,values=list(options),state='readonly');win.preset_choice.pack(fill='x',pady=(6,12))
    info=ttk.Label(body,text='',wraplength=510);info.pack(fill='x')
    ttk.Label(body,text='名前は作成後に左リストで変更できます。',style='Muted.TLabel').pack(anchor='w',pady=10)
    error=ttk.Label(body,text='',foreground='#bb6440',wraplength=510);error.pack(fill='x')
    footer=ttk.Frame(body);footer.pack(side='bottom',fill='x')
    state={}
    def preview(_=None):
        state.clear();error.configure(text='')
        try:
            candidate,records,rows=prepare(data,options[choice.get()],anchor)
            state.update(snapshot=copy.deepcopy(data),preset=options[choice.get()])
            info.configure(text=records['CATE']['name']+'\nSDTE：1件　TEXT：'+str(len(rows))+'件　SCOM：1件')
            win.create_button.configure(state='normal')
        except (ValueError,KeyError) as exc:
            info.configure(text='');error.configure(text=str(exc));win.create_button.configure(state='disabled')
    def create():
        if not state:return
        if host.data is not data or data!=state['snapshot']:
            error.configure(text='データが変更されています。プリセットを選び直してください。');return
        try:candidate,records,rows=prepare(data,state['preset'],anchor)
        except ValueError as exc:error.configure(text=str(exc));return
        data.clear();data.update(candidate)
        host.cate_id=records['CATE']['id'];host.scom_id=records['SCOM']['id'];host.catalog_tab='scom'
        key='cates:'+host.cate_id;host.registered_browser.catalog_target=key
        win.destroy();host.render_page();host.registered_browser.reveal_created(key)
        host.status.configure(text='CATE一式を作成しました。TEXT：'+str(len(rows))+'件')
    win.create_button=ttk.Button(footer,text='一式作成',command=create,style='Primary.TButton');win.create_button.pack(side='right')
    ttk.Button(footer,text='取消',command=win.destroy).pack(side='right',padx=6)
    win.preset_choice.bind('<<ComboboxSelected>>',preview);preview()
    return win
