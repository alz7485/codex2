"""Selection-driven catalogue attribute grid and transactional cell edits."""
import copy
import json
import tkinter as tk
from tkinter import ttk
from . import project, presets, catalogue, catalog_workspace as workspace


def record_fields(data,collection,record):
    """Return (label, storage path, choice map) for known and retained attributes."""
    result=[('NAME',('name',),None),('REVISION',('revision',),None)]
    if collection=='cates':result.append(('DESCRIPTION',('description',),None))
    if collection=='scoms':
        result.append(('SIZE',('size',),None))
        result.append(('PARAM プリセット',('parameter_preset_id',),{name:ident for name,ident in presets.choices(data).items()}))
        for label,key,kind in (('GMRE','gmset_id','GMSET'),('PTRE','ptset_id','PTSET'),('NGMSET','ngmset_id','NGMSET'),('GMSSET','gmsset_id','GMSSET'),('PTSSET','ptsset_id','PTSSET')):
            choices={'未設定':''}|{r['name']:r['id'] for r in data['definitions'] if r['kind']==kind}
            if record.get(key,'') not in choices.values():choices['不明：'+record[key]]=record[key]
            result.append((label,(key,),choices))
        rules=presets.rules(data,record)
        result += [(p['id']+' / '+presets.caption(p),('values',p['id']),None) for p in rules]
        result += [(pid,('values',pid),None) for pid in record['values'] if pid not in {p['id'] for p in rules}]
        result += [(key,('component_attrs',key),None) for key in dict.fromkeys(('ANGL',*record.get('component_attrs',{})))]
    elif collection=='texts':
        result += [(key,('attrs',key),None) for key in dict.fromkeys((*catalogue.TEXT_TYPES.get(record['type'],()),*record['attrs']))]
    elif collection in workspace.COLLECTIONS.values():
        result.append(('DESCRIPTION',('description',),None))
        if collection=='catalog_details':result.append(('参照SDTE',('sdte_id',),{'未設定':''}|{r['name']:r['id'] for r in data['texts'] if r['type']=='SDTE'}))
    if collection=='catalog_props':
        for i,child in enumerate(record.get('children',[])):
            result.append(('CMPDATA NAME',('children',i,'name'),None))
            result.extend((child['name']+' / '+key,('children',i,'attrs',key),None) for key in child.get('attrs',{}))
    if collection!='texts':result += [(key,('attrs',key),None) for key in record.get('attrs',{})]
    return result


def value_at(record,path):
    value=record
    for part in path:
        if isinstance(value,dict):value=value.get(part,'')
        elif isinstance(value,list) and isinstance(part,int) and part<len(value):value=value[part]
        else:return ''
    return value


def edit_value(data,collection,ident,path,value):
    original=project.get(data,collection,ident)
    if not original:raise ValueError('選択項目が削除されています。')
    candidate=copy.deepcopy(data);record=project.get(candidate,collection,ident)
    if path not in [p for _,p,_ in record_fields(data,collection,original)]:raise ValueError('編集できない属性です。')
    old=value_at(record,path)
    if path[0]=='children':
        target=record
        for part in path[:-1]:target=target[part]
        target[path[-1]]=workspace.check_name(candidate,value,exclude=target) if path[-1]=='name' else json.loads(value)
        project.validate(candidate)
        original.clear();original.update(record);return
    if path==('name',):value=workspace.check_name(candidate,value,exclude=record)
    if collection=='scoms':
        if path[0]=='values':
            rule=next((p for p in presets.rules(candidate,record) if p['id']==path[1]),None)
            if value=='':record['values'].pop(path[1],None)
            else:record['values'][path[1]]=project.parse_value(rule,value) if rule else json.loads(value) if not isinstance(old,str) else value
        elif path[0]=='component_attrs':
            if value=='':record.setdefault('component_attrs',{}).pop(path[1],None)
            else:record.setdefault('component_attrs',{})[path[1]]=project.parse_value({'id':'ANGL','unit':'degrees'},value) if path[1]=='ANGL' else value if isinstance(old,str) else json.loads(value)
        elif path[0]=='attrs':record.setdefault('attrs',{})[path[1]]=value if isinstance(old,str) else json.loads(value)
        else:record[path[0]]=value
        for key,kind in (('gmset_id','GMSET'),('ptset_id','PTSET'),('ngmset_id','NGMSET'),('gmsset_id','GMSSET'),('ptsset_id','PTSSET')):
            if record.get(key) and path[0] in (key,'parameter_preset_id'):
                target=project.get(candidate,'definitions',record[key])
                if not target or target['kind']!=kind:raise ValueError('参照先の種類が不正です。')
                presets.require_compatible(candidate,record,target)
    elif len(path)==1:record[path[0]]=value
    else:record.setdefault(path[0],{})[path[1]]=value if isinstance(old,str) else json.loads(value)
    project.validate(candidate)
    original.clear();original.update(record)


class CatalogInspector(ttk.Frame):
    def __init__(self,host,parent):
        super().__init__(parent);self.host=host;self.fields={};self.editing=None
        self.title=ttk.Label(self,text='',style='Heading.TLabel');self.title.pack(anchor='w',pady=(0,8))
        self.tree=host.table(self,[('attribute','属性',240),('value','値',500)],height=18)
        self.tree.bind('<ButtonRelease-1>',self.click);self.tree.bind('<Return>',lambda _:self.begin(self.tree.focus()))
        self.tree.bind('<Configure>',lambda _:self.cancel())
        self.error=ttk.Label(self,text='',foreground='#bb6440',wraplength=650);self.error.pack(fill='x',pady=6)
        self.refresh()

    def targets(self):
        h=self.host;data=h.data;cate=project.get(data,'cates',h.cate_id)
        key=getattr(h.registered_browser,'catalog_target','')
        if getattr(h,'catalog_tab','scom')=='members':key=getattr(h,'catalog_member_key',None) or ''
        if cate and key=='cates:'+cate['id']:
            return [('cates',cate)]+[('texts',r) for r in data['texts'] if r['parent_id']==cate['id']]+[('scoms',r) for r in data['scoms'] if r['cate_id']==cate['id']]
        collection,_,ident=key.partition(':');record=project.get(data,collection,ident) if collection in ('texts','catalog_details','catalog_props') else None
        if record and getattr(h,'catalog_tab','scom')=='members':return [(collection,record)]
        if not cate:return []
        scom=project.get(data,'scoms',h.scom_id)
        return [('scoms',scom)] if scom else [('cates',cate)]

    def refresh(self):
        self.cancel();self.fields={};self.tree.delete(*self.tree.get_children())
        targets=self.targets();self.title.configure(text='カタログ属性：'+(targets[0][1]['name'] if targets else '左リストでCATEを選択してください'))
        for collection,record in targets:
            kind=record.get('type',{'cates':'CATE','scoms':'SCOM','catalog_details':'DETAIL','catalog_props':'PROP'}.get(collection,''))
            group=self.tree.insert('','end',values=(kind,record['name']),tags=('section',))
            for label,path,choices in record_fields(self.host.data,collection,record):
                value=value_at(record,path)
                display=next((n for n,v in choices.items() if v==value),str(value)) if choices is not None else value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)
                iid=self.tree.insert('','end',values=(label,display))
                self.fields[iid]=(collection,record['id'],path,choices)
        self.tree.tag_configure('section',background='#edf3fc',foreground='#2864dc')

    def click(self,event):
        if self.tree.identify_column(event.x)=='#2':self.begin(self.tree.identify_row(event.y))

    def begin(self,iid):
        field=self.fields.get(iid)
        if not self.finish() or field is None:return
        iid=next((i for i,f in self.fields.items() if f==field),None)
        if iid is None:return
        field=self.fields[iid];value=self.tree.item(iid,'values')[1];self.tree.see(iid)
        box=self.tree.bbox(iid,'value')
        if not box:return
        variable=tk.StringVar(value=value);choices=field[3]
        entry=ttk.Combobox(self.tree,textvariable=variable,values=list(choices),state='readonly') if choices is not None else ttk.Entry(self.tree,textvariable=variable)
        self.editing=dict(entry=entry,variable=variable,initial=value,field=field,data=self.host.data,original=copy.deepcopy(project.get(self.host.data,field[0],field[1])))
        x,y,w,h=box;entry.place(x=x,y=y,width=w,height=h);entry.focus_set()
        entry.bind('<Return>',lambda _:(self.finish(),'break')[1]);entry.bind('<Escape>',lambda _:self.cancel());entry.bind('<FocusOut>',self.blur)
        if choices is not None:entry.bind('<<ComboboxSelected>>',lambda _:self.finish())
        else:entry.selection_range(0,'end')

    def blur(self,_=None):
        if self.editing and isinstance(self.editing['entry'],ttk.Combobox):
            entry=self.editing['entry'];popup=entry.tk.call('ttk::combobox::PopdownWindow',str(entry))
            if entry.tk.call('winfo','ismapped',popup):return
        self.finish()

    def finish(self):
        state=self.editing
        if not state:return True
        collection,ident,path,choices=state['field'];value=state['variable'].get()
        if value==state['initial']:self.cancel();return True
        try:
            if self.host.data is not state['data'] or project.get(self.host.data,collection,ident)!=state['original']:raise ValueError('データが変更されています。編集をやり直してください。')
            edit_value(self.host.data,collection,ident,path,choices[value] if choices is not None else value)
        except (ValueError,KeyError) as exc:self.error.configure(text=str(exc));return False
        self.cancel();self.error.configure(text='');self.host.mark();self.refresh()
        self.host.fill_scom_table();self.host.update_scom_preview();return True

    def cancel(self):
        if self.editing:
            entry=self.editing['entry'];self.editing=None;entry.destroy()
        return 'break'
