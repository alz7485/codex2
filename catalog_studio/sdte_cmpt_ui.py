"""Dedicated editing workspace for detail SDTE and CMPTYPE/CMPDATA."""
import tkinter as tk
from tkinter import ttk
import uuid
from . import project,catalog_workspace as workspace
from .catalog_inspector import record_fields,value_at,edit_value

class SdteCmptEditor(ttk.Frame):
    def __init__(self,host):
        super().__init__(host.content);self.host=host;self.rows={};self.fields={};self.editing=None
        self.pack(fill='both',expand=True)
        bar=ttk.Frame(self);bar.pack(fill='x',pady=(0,10))
        ttk.Label(bar,text='関連CATE').pack(side='left')
        self.cates={r['name']:r['id'] for r in host.data['cates']}
        self.cate=tk.StringVar(value=next((n for n,i in self.cates.items() if i==host.cate_id),next(iter(self.cates),'')))
        choice=ttk.Combobox(bar,textvariable=self.cate,values=list(self.cates),state='readonly',width=30);choice.pack(side='left',padx=8)
        choice.bind('<<ComboboxSelected>>',lambda _:self.refresh())
        for label,kind in (('＋ SDTE','SDTE'),('＋ CMPT','CMPT'),('＋ CMPDATA','CMPDATA')):
            ttk.Button(bar,text=label,command=lambda k=kind:self.add(k)).pack(side='left',padx=3)
        panes=ttk.Panedwindow(self,orient='horizontal');panes.pack(fill='both',expand=True)
        left=ttk.Frame(panes,padding=8,width=400);right=ttk.Frame(panes,padding=8)
        panes.add(left,weight=2);panes.add(right,weight=3)
        ttk.Label(left,text='SDTE / CMPT',style='Heading.TLabel').pack(anchor='w',pady=(0,8))
        self.tree=ttk.Treeview(left,show='tree',selectmode='browse');self.tree.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',lambda _:self.select())
        ttk.Label(right,text='属性・値',style='Heading.TLabel').pack(anchor='w',pady=(0,8))
        from .catalog_attribute_table import CatalogAttributeTable
        self.attrs=CatalogAttributeTable(right,host.ui_font);self.attrs.pack(fill='both',expand=True)
        self.attrs.bind('<ButtonRelease-1>',self.click)
        self.refresh()
    def refresh(self,selected=None):
        self.cancel();previous=selected or next(iter(self.tree.selection()),'');self.rows={};self.tree.delete(*self.tree.get_children())
        cate=self.cates.get(self.cate.get())
        for collection,label in (('catalog_details','SDTE'),('catalog_props','CMPT')):
            self.tree.insert('','end',iid=collection,text=label,open=True)
            for r in self.host.data.get(collection,[]):
                if r.get('cate_id')!=cate:continue
                self.tree.insert(collection,'end',iid=r['id'],text=r['name'],open=True);self.rows[r['id']]=(collection,r,None)
                for i,child in enumerate(r.get('children',[])):
                    self.tree.insert(r['id'],'end',iid=child['id'],text=child['name']);self.rows[child['id']]=(collection,r,i)
        if previous in self.rows:self.tree.selection_set(previous)
        self.select()
    def select(self):
        if self.editing and not self.finish():return
        self.cancel();self.fields={};self.attrs.delete(*self.attrs.get_children())
        item=next(iter(self.tree.selection()),'')
        if item not in self.rows:return
        col,r,index=self.rows[item]
        if index is None:
            fields=[('NAME',('name',),None)]+record_fields(self.host.data,col,r)
        else:
            child=r['children'][index]
            fields=[('NAME',('children',index,'name'),None)]+[(k,('children',index,'attrs',k),None) for k in child['attrs']]
        for label,path,_ in fields:
            iid=self.attrs.insert('','end',values=(label,str(value_at(r,path))),meaning={'SKEY':'シンボルキー','RTEX':'詳細説明','CWEI':'部品質量','NAME':'名前'}.get(label,''))
            self.fields[iid]=(col,r['id'],path)
    def click(self,event):
        if self.attrs.identify_column(event.x)!='#2':return
        iid=self.attrs.identify_row(event.y)
        if iid not in self.fields:return
        self.cancel();box=self.attrs.bbox(iid,'value')
        if not box:return
        var=tk.StringVar(value=self.attrs.item(iid,'values')[1]);entry=ttk.Entry(self.attrs,textvariable=var)
        x,y,w,h=box;entry.place(x=x,y=y,width=w,height=h);entry.focus_set();entry.selection_range(0,'end')
        self.editing=(entry,var,self.fields[iid])
        entry.bind('<Return>',lambda _:self.finish());entry.bind('<FocusOut>',lambda _:self.finish());entry.bind('<Escape>',lambda _:self.cancel())
    def finish(self):
        if not self.editing:return True
        entry,var,(col,ident,path)=self.editing
        try:edit_value(self.host.data,col,ident,path,var.get())
        except (ValueError,KeyError) as exc:self.host.status.configure(text=str(exc));return False
        self.cancel();self.host.mark();self.refresh();return True
    def cancel(self):
        if self.editing:
            entry=self.editing[0];self.editing=None;entry.destroy()
    def add(self,kind):
        if not self.finish():return
        cate=self.cates.get(self.cate.get())
        if not cate:self.host.status.configure(text='CATE作成で関連CATEを作成してください。');return
        def unique(stem):
            number=1
            while True:
                name='/'+stem+'('+str(number)+')'
                try:return workspace.check_name(self.host.data,name)
                except ValueError:number+=1
        if kind=='CMPDATA':
            row=self.rows.get(next(iter(self.tree.selection()),''))
            if not row or row[0]!='catalog_props':self.host.status.configure(text='CMPDATAを追加するCMPTを選択してください。');return
            child={'id':uuid.uuid4().hex,'name':unique('新しいCMPDATA'),'type':'CMPDATA','attrs':{'CWEI':0.0}}
            row[1].setdefault('children',[]).insert(0,child);selected=child['id']
        else:
            r=workspace.add_association(self.host.data,'DETAIL' if kind=='SDTE' else 'PROP',unique('新しい'+kind),cate,attrs={'SKEY':'','RTEX':''} if kind=='SDTE' else {})
            selected=r['id']
        self.host.mark();self.refresh(selected)
