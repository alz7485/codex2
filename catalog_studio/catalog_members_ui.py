"""Edit CATE members and related SPEC choices inside catalogue creation."""
import copy
import json
from tkinter import messagebox, ttk
from . import catalogue, catalog_workspace as workspace, presets, project


class CatalogMembers(ttk.Frame):
    def __init__(self, host, parent):
        super().__init__(parent, padding=10); self.host=host; self.selected=None
        self.columnconfigure(0,weight=1);self.rowconfigure(3,weight=3,minsize=90);self.rowconfigure(4,weight=2,minsize=90)
        self.owner=ttk.Label(self,text='',style='Heading.TLabel',wraplength=600);self.owner.grid(row=0,column=0,sticky='ew',pady=(0,8))
        buttons=ttk.Frame(self);buttons.grid(row=1,column=0,sticky='ew',pady=(0,6));self.add_buttons={}
        buttons.columnconfigure((0,1),weight=1,uniform='create')
        for index,kind in enumerate(('SDTE','TEXT','DETAIL','PROP')):
            button=ttk.Button(buttons,text=kind+' 追加',command=lambda k=kind:self.create(k),style='AttributeTool.TButton')
            button.grid(row=index//2,column=index%2,sticky='ew',padx=2,pady=2);self.add_buttons[kind]=button
        tools=ttk.Frame(self);tools.grid(row=2,column=0,sticky='ew',pady=(0,6))
        ttk.Button(tools,text='選択レコードを編集',command=self.edit).pack(side='left')
        ttk.Button(tools,text='削除',command=self.delete).pack(side='left',padx=5)
        records_frame=ttk.Frame(self);records_frame.grid(row=3,column=0,sticky='nsew')
        self.table=host.table(records_frame,[('name','名前',260),('kind','種類',80),('revision','改訂',60)],height=6)
        self.table.bind('<<TreeviewSelect>>',self.select);self.table.bind('<Double-1>',lambda _:self.edit())
        attrs_frame=ttk.Frame(self);attrs_frame.grid(row=4,column=0,sticky='nsew',pady=(8,0))
        self.attributes=host.table(attrs_frame,[('key','属性・参照',110),('value','値',330)],height=5)
        note=ttk.Label(self,text='SDTE・TEXT は CATE の中身です。DETAIL・PROP はスペック登録で SCOM と組み合わせる関連データです。',style='Muted.TLabel',wraplength=600)
        note.grid(row=5,column=0,sticky='ew',pady=8)
        self.bind('<Configure>',lambda event:[label.configure(wraplength=max(180,event.width-24)) for label in (self.owner,note)] if event.widget is self else None)
        self.refresh()

    def records(self):
        result=[('texts',record,record['type']) for record in self.host.data.get('texts',[])
                if record['parent_id']==self.host.cate_id and record['type'] in ('SDTE','TEXT')]
        result.extend((collection,record,kind) for kind,collection in workspace.COLLECTIONS.items()
                      for record in self.host.data.get(collection,[]) if record['cate_id']==self.host.cate_id)
        return result

    def item(self):return next((item for item in self.records() if item[0]+':'+item[1]['id']==self.selected),None)

    def refresh(self):
        cate=project.get(self.host.data,'cates',self.host.cate_id)
        self.owner.configure(text='CATE：'+cate['name'] if cate else 'CATE を作成・選択してください。')
        for button in self.add_buttons.values():button.configure(state='normal' if cate else 'disabled')
        self.table.delete(*self.table.get_children())
        for collection,record,kind in self.records():self.table.insert('','end',iid=collection+':'+record['id'],values=(record['name'],kind,record['revision']))
        selected=getattr(self.host,'catalog_member_key',None)
        if selected and self.table.exists(selected):self.table.selection_set(selected)
        elif self.table.get_children():self.table.selection_set(self.table.get_children()[0])
        self.select()

    def select(self,_=None):
        items=self.table.selection();self.selected=items[0] if items else None;self.host.catalog_member_key=self.selected
        self.attributes.delete(*self.attributes.get_children());item=self.item()
        if not item:return
        collection,record,kind=item
        if not self.host.busy and self.host.page=='catalog' and getattr(self.host,'catalog_tab','scom')=='members':
            browser=self.host.registered_browser;browser.catalog_target=self.selected
            browser.catalog_context=(self.host.cate_id,self.host.scom_id,'members',self.selected);browser.refresh()
        if kind=='DETAIL':
            target=project.get(self.host.data,'texts',record.get('sdte_id',''))
            self.attributes.insert('','end',values=('参照SDTE',target['name'] if target else '未設定'))
        if collection!='texts':self.attributes.insert('','end',values=('説明',record['description']))
        for key,value in record['attrs'].items():self.attributes.insert('','end',values=(key,str(value)))

    def create(self,kind):
        cate=project.get(self.host.data,'cates',self.host.cate_id)
        if cate:return self.record_form(cate,kind)

    def edit(self):
        item=self.item();cate=project.get(self.host.data,'cates',self.host.cate_id)
        if item and cate:return self.record_form(cate,item[2],item[1])

    def record_form(self,cate,kind,record=None):
        data=self.host.data;collection='texts' if kind in ('SDTE','TEXT') else workspace.COLLECTIONS[kind]
        attrs=(record or {}).get('attrs',{})
        fields=[('name',kind+' 名',record['name'] if record else cate['name'].rstrip('/')+'/'+kind,None),
                ('revision','改訂',record['revision'] if record else '01',None),('owner','所属・関連 CATE',cate['name'],[cate['name']])]
        mapping={}
        if collection=='texts':
            keys=list(dict.fromkeys((*catalogue.TEXT_TYPES[kind],*attrs)))
            for key in keys:
                value=attrs.get(key,'');fields.append(('attr:'+key,key,value if isinstance(value,str) else json.dumps(value,ensure_ascii=False),None))
        else:
            fields.extend([('description','説明',(record or {}).get('description',''),None),('attrs','属性（JSON）',json.dumps(attrs,ensure_ascii=False),None)])
            if kind=='DETAIL':
                mapping={item['name']:item['id'] for item in data.get('texts',[]) if item['type']=='SDTE'};mapping['未設定']=''
                ident=(record or {}).get('sdte_id','')
                if ident and ident not in mapping.values():mapping['参照先不明：'+ident]=ident
                fields.append(('sdte_id','参照 SDTE',next((name for name,value in mapping.items() if value==ident),'未設定'),list(mapping)))
        def apply(values):
            if self.host.data is not data or project.get(data,'cates',cate['id']) is not cate:raise ValueError('CATE が変更されています。開き直してください。')
            if record and project.get(data,collection,record['id']) is not record:raise ValueError('編集対象が変更されています。')
            name=workspace.check_name(data,values['name'],record)
            updated=copy.deepcopy(attrs)
            if collection=='texts':
                for key in keys:
                    try:updated[key]=values['attr:'+key] if isinstance(attrs.get(key,''),str) else json.loads(values['attr:'+key])
                    except ValueError as exc:raise ValueError(key+' のJSON形式を確認してください。') from exc
            else:
                try:updated=json.loads(values['attrs'])
                except ValueError as exc:raise ValueError('属性のJSON形式を確認してください。') from exc
                if not isinstance(updated,dict):raise ValueError('属性はJSONオブジェクトです。')
            if record:item=record
            elif collection=='texts':item=catalogue.add_record(data,'texts',kind,name,cate['id'])
            else:item=workspace.add_association(data,kind,name,cate['id'],attrs=updated)
            item.update(name=name,revision=values['revision'],attrs=updated)
            if collection!='texts':item['description']=values['description']
            if kind=='DETAIL':item['sdte_id']=mapping[values['sdte_id']]
            self.host.catalog_member_key=collection+':'+item['id'];self.host.catalog_tab='members'
        return self.host.form(kind+' を編集' if record else kind+' を追加',fields,apply)

    def delete(self):
        item=self.item()
        if not item:return
        collection,record,kind=item;data=self.host.data;ident=record['id']
        referenced=workspace.used(data,collection,ident)
        if collection=='texts':referenced=referenced or any(entry.get(key)==ident for spec in data['specs'] for entry in spec['entries'] for key in ('sdte_id','smte_id')) or any(r.get('parent_id')==ident for key in ('tables','texts') for r in data.get(key,[]))
        if referenced:messagebox.showinfo('使用中','SPEC・DETAIL または子レコードから参照されています。',parent=self.host);return
        if messagebox.askyesno('削除',record['name']+' を削除しますか？',parent=self.host):
            data[collection].remove(record);self.host.catalog_member_key=None;self.host.mark();self.host.render_page()


def bundle_form(host):
    options={**host.choices('definitions','PTSET'),'未設定':''};geometries={**host.choices('definitions','GMSET'),'未設定':''};rules=presets.choices(host.data)
    fields=[('cate','CATE 名','',None),('description','説明','',None),('preset','PARAM プリセット',next(name for name,ident in rules.items() if ident==host.data.get('active_parameter_preset_id','')),list(rules)),
            ('pt','PTSET','未設定',list(options)),('gm','GMSET','未設定',list(geometries))]
    for kind in ('SDTE','TEXT','SCOM','DETAIL','PROP'):fields.append((kind,kind+' 名（空欄なら CATE名/'+kind+'）','',None))
    fields.extend([('rtex','SDTE：RTEX','',None),('stext','TEXT：STEXT','',None),('props','PROP 属性（JSON）','{}',None)])
    def apply(values):
        try:attrs=json.loads(values['props'])
        except ValueError as exc:raise ValueError('PROP属性のJSON形式を確認してください。') from exc
        if not isinstance(attrs,dict):raise ValueError('PROP属性はJSONオブジェクトです。')
        candidate,records=workspace.prepare_bundle(host.data,values['cate'],description=values['description'],preset_id=rules[values['preset']],ptset_id=options[values['pt']],gmset_id=geometries[values['gm']],names=values,rtex=values['rtex'],stext=values['stext'],prop_attrs=attrs)
        host.data=candidate;host.cate_id=records['CATE']['id'];host.scom_id=records['SCOM']['id'];host.catalog_tab='members'
        host.catalog_detail_id=records['DETAIL']['id'];host.catalog_prop_id=records['PROP']['id']
        host.catalog_seed_scom_id=records['SCOM']['id']
        host.catalog_member_key='texts:'+records['SDTE']['id']
    return host.form('CATE と関連データを一緒に作成',fields,apply)
