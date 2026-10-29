"""Create CATE, SDTE, preset TEXT records and one SCOM atomically."""
import copy
import tkinter as tk
from tkinter import ttk
from . import project, catalogue, presets, catalog_workspace, catalog_text_batch, browser_folders, pairing


def prepare(data,preset_id,anchor='',ptset_id='',gmset_id=''):
    candidate=copy.deepcopy(data)
    if preset_id and not presets.get(candidate,preset_id):raise ValueError('PARAMプリセットが見つかりません。')
    for ident,kind in ((ptset_id,'PTSET'),(gmset_id,'GMSET')):
        if not ident:continue
        definition=project.get(candidate,'definitions',ident)
        if not definition or definition['kind']!=kind:raise ValueError(kind+'が見つかりません。')
        presets.require_compatible(candidate,{'parameter_preset_id':preset_id},definition)
    if gmset_id and ptset_id:
        resolved=pairing.resolve(candidate,project.get(candidate,'definitions',gmset_id))
        if resolved['pointset'] and resolved['pointset']['id']!=ptset_id:raise ValueError('GMSETに対応するPTSETと選択内容が異なります。')
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
    scom.update(parameter_preset_id=preset_id,gmset_id=gmset_id,ptset_id=ptset_id,values={})
    project.validate(candidate)
    return candidate,{'CATE':cate,'SDTE':sdte,'TEXT':texts,'SCOM':scom},rows


def linked_selection(data,source,ident,other=''):
    definition=project.get(data,'definitions',ident)
    if not definition or definition['kind']!=source:return '', '', '', []
    preset=presets.selected_id(data,definition)
    if source=='PTSET':
        candidates=[d for d in pairing.users(data,ident) if presets.selected_id(data,d)==preset]
        if not candidates:
            candidates=[d for d in data['definitions'] if d['kind']=='GMSET' and presets.selected_id(data,d)==preset and pairing.resolve(data,d)['source'] in ('none',)]
    else:
        resolved=pairing.resolve(data,definition)
        candidates=[resolved['pointset']] if resolved['pointset'] else resolved['candidates']
        if not candidates and resolved['source'] in ('none',):
            candidates=[d for d in data['definitions'] if d['kind']=='PTSET' and presets.selected_id(data,d)==preset]
        candidates=[d for d in candidates if presets.selected_id(data,d)==preset]
    chosen=next((d for d in candidates if d['id']==other),None)
    if chosen is None and len(candidates)==1:chosen=candidates[0]
    counterpart=chosen['id'] if chosen else ''
    return (ident,counterpart,preset,candidates) if source=='PTSET' else (counterpart,ident,preset,candidates)


def open_bundle(host,anchor=''):
    if host.grab_current():host.grab_current().lift();return
    data=host.data;options=presets.choices(data)
    win=tk.Toplevel(host);win.title('CATE一式作成');win.geometry('600x440');win.minsize(500,380)
    win.transient(host);win.grab_set()
    body=ttk.Frame(win,padding=12);body.pack(fill='both',expand=True)
    selected={'PTSET':'','GMSET':'','preset':presets.selected_id(data)}
    choices={kind:{'未選択':''}|{d['name']:d['id'] for d in data['definitions'] if d['kind']==kind} for kind in ('PTSET','GMSET')}
    variables={kind:tk.StringVar(value='未選択') for kind in choices}
    for kind in choices:
        ttk.Label(body,text=kind,style='Heading.TLabel').pack(anchor='w')
        combo=ttk.Combobox(body,textvariable=variables[kind],values=list(choices[kind]),state='readonly');combo.pack(fill='x',pady=(4,8))
        setattr(win,kind.lower()+'_choice',combo)
    ttk.Label(body,text='PARAMプリセット',style='Heading.TLabel').pack(anchor='w')
    choice=tk.StringVar(value=next((n for n,i in options.items() if i==selected['preset']),next(iter(options))))
    win.preset_choice=ttk.Combobox(body,textvariable=choice,values=list(options),state='readonly');win.preset_choice.pack(fill='x',pady=(4,10))
    info=ttk.Label(body,text='',wraplength=510);info.pack(fill='x')
    ttk.Label(body,text='名前は作成後に左リストで変更できます。',style='Muted.TLabel').pack(anchor='w',pady=10)
    error=ttk.Label(body,text='',foreground='#bb6440',wraplength=510);error.pack(fill='x')
    footer=ttk.Frame(body);footer.pack(side='bottom',fill='x')
    state={}
    def preview(_=None):
        state.clear();error.configure(text='')
        try:
            if not selected['PTSET'] or not selected['GMSET']:raise ValueError('PTSETとGMSETを選択してください。対応候補が複数ある場合は手動で選択します。')
            candidate,records,rows=prepare(data,options[choice.get()],anchor,selected['PTSET'],selected['GMSET'])
            state.update(snapshot=copy.deepcopy(data),preset=options[choice.get()],ptset_id=selected['PTSET'],gmset_id=selected['GMSET'])
            info.configure(text=records['CATE']['name']+'\nSDTE：1件　TEXT：'+str(len(rows))+'件　SCOM：1件')
            win.create_button.configure(state='normal')
        except (ValueError,KeyError) as exc:
            info.configure(text='');error.configure(text=str(exc));win.create_button.configure(state='disabled')
    def create():
        if not state:return
        if host.data is not data or data!=state['snapshot']:
            error.configure(text='データが変更されています。プリセットを選び直してください。');return
        try:candidate,records,rows=prepare(data,state['preset'],anchor,state['ptset_id'],state['gmset_id'])
        except ValueError as exc:error.configure(text=str(exc));return
        data.clear();data.update(candidate)
        host.cate_id=records['CATE']['id'];host.scom_id=records['SCOM']['id'];host.catalog_tab='scom'
        key='cates:'+host.cate_id;host.registered_browser.catalog_target=key
        win.destroy();host.render_page();host.registered_browser.reveal_created(key)
        host.status.configure(text='CATE一式を作成しました。TEXT：'+str(len(rows))+'件')
    win.create_button=ttk.Button(footer,text='一式作成',command=create,style='Primary.TButton');win.create_button.pack(side='right')
    ttk.Button(footer,text='取消',command=win.destroy).pack(side='right',padx=6)
    def change(kind):
        ident=choices[kind].get(variables[kind].get(),'')
        other='GMSET' if kind=='PTSET' else 'PTSET'
        pt,gm,preset,candidates=linked_selection(data,kind,ident,selected[other])
        selected.update(PTSET=pt,GMSET=gm,preset=preset)
        for k in choices:
            variables[k].set(next((n for n,i in choices[k].items() if i==selected[k]),'未選択'))
        choice.set(next((n for n,i in options.items() if i==preset),next(iter(options))))
        getattr(win,other.lower()+'_choice').configure(values=list(choices[other]))
        getattr(win,kind.lower()+'_choice').configure(values=list(choices[kind]))
        preview()
    def preset_changed(_=None):
        selected['preset']=options[choice.get()]
        for kind in choices:
            current=project.get(data,'definitions',selected[kind])
            if current and presets.selected_id(data,current)!=selected['preset']:
                selected[kind]='';variables[kind].set('未選択')
            getattr(win,kind.lower()+'_choice').configure(values=list(choices[kind]))
        preview()
    for kind in choices:getattr(win,kind.lower()+'_choice').bind('<<ComboboxSelected>>',lambda _,k=kind:change(k))
    win.preset_choice.bind('<<ComboboxSelected>>',preset_changed)
    scom=project.get(data,'scoms',host.scom_id)
    gm=project.get(data,'definitions',(scom or {}).get('gmset_id'))
    if gm and gm['kind']=='GMSET' and presets.selected_id(data,gm)==selected['preset']:
        selected['PTSET']=(scom or {}).get('ptset_id','')
        variables['GMSET'].set(gm['name']);change('GMSET')
    else:
        candidates=[d for d in data['definitions'] if d['kind']=='PTSET' and presets.selected_id(data,d)==selected['preset']]
        if len(candidates)==1:variables['PTSET'].set(candidates[0]['name']);change('PTSET')
        else:preset_changed()
    return win
