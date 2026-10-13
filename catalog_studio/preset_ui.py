"""Manage parameter dictionaries without reinterpreting existing catalogue records."""
import copy
import re
import tkinter as tk
from tkinter import messagebox, ttk
from . import presets, project, model, expressions, element_schema


class PresetEditor(ttk.Frame):
    def __init__(self,host):
        super().__init__(host.content);self.host=host
        host.heading('PARAM プリセット','登録時期・コンポーネントごとに番号の説明を管理。選択したプリセットは新規作成用です。既存の割り当ては変わりません。',[('プリセットを追加',self.add),('選択を複製',self.duplicate)])
        self.pack(fill='both',expand=True)
        split=ttk.Panedwindow(self,orient='horizontal');split.pack(fill='both',expand=True)
        left=ttk.Frame(split,padding=8);right=ttk.Frame(split,padding=8);split.add(left,weight=2);split.add(right,weight=5);host.balance(split,(.3,))
        self.list=host.table(left,[('name','プリセット名',160),('period','登録時期',100),('component','コンポーネント',110)],height=12)
        self.list.insert('','end',iid='legacy',values=('既存規則（従来データ）','',''))
        for p in host.data.get('parameter_presets',[]):self.list.insert('','end',iid='preset:'+p['id'],values=(p['name'],p['period'],p['component']))
        active=presets.selected_id(host.data);self.list.selection_set('preset:'+active if active else 'legacy')
        self.list.bind('<<TreeviewSelect>>',self.select)
        actions=ttk.Frame(left);actions.pack(fill='x',pady=8)
        for label,fn in [('名前・適用範囲',self.edit),('削除',self.delete)]:ttk.Button(actions,text=label,command=fn).pack(side='left',padx=2)
        record=self.record();ident=presets.selected_id(host.data)
        text=presets.label(host.data)+'\n'+((record['description']+'\n') if record else '')+f'使用中：{len(presets.users(host.data,ident))} 件'
        ttk.Label(right,text=text,style='Heading.TLabel',wraplength=700).pack(anchor='w',pady=8)
        self.table=host.table(right,[('id','番号',65),('role','表示名・式用の役割名',170),('description','日本語説明・用途',250),('unit','単位',65),('type','値型',65)],height=12)
        for p in self.parameters():self.table.insert('','end',iid=p['id'],values=(p['id'],p['role'],p.get('description',''),p['unit'],p.get('value_type','number')))
        self.table.bind('<Double-1>',lambda _:self.edit_parameter())
        actions=ttk.Frame(right);actions.pack(fill='x',pady=10)
        for label,fn in [('番号を追加',self.parameter_form),('説明・役割を編集',self.edit_parameter),('未使用番号を削除',self.remove_parameter),('参照種類別の役割',self.reference_roles)]:ttk.Button(actions,text=label,command=fn).pack(side='left',padx=2)
        ttk.Label(right,text='SCOM と定義には使用するプリセットを個別に割り当てます。過去用を残す場合は複製して新規用を作成してください。\n説明の編集は同じプリセットを使うデータに反映します。番号と実数値は変更せず、発行済み冊子の内容も変わりません。',style='Muted.TLabel',wraplength=730).pack(anchor='w',pady=8)

    def record(self):return presets.get(self.host.data,presets.selected_id(self.host.data))
    def parameters(self):return presets.rules(self.host.data)
    def select(self,_=None):
        selection=self.list.selection()
        if not selection:return
        ident=selection[0][7:] if selection[0].startswith('preset:') else ''
        if ident != presets.selected_id(self.host.data):self.host.data['active_parameter_preset_id']=ident;self.host.mark();self.host.render_page()
    def add(self):
        source=presets.selected_id(self.host.data)
        def apply(v):
            p=presets.add(self.host.data,v['name'],source);p.update(period=v['period'],component=v['component'],description=v['description'])
            self.host.data['active_parameter_preset_id']=p['id']
        self.host.form('プリセットを追加（選択中の規則をコピー）',[('name','プリセット名','新規プリセット',None),('period','登録時期・世代','',None),('component','対象コンポーネント','',None),('description','説明・適用範囲','',None)],apply)
    def duplicate(self):self.add()
    def edit(self):
        p=self.record()
        if not p:messagebox.showinfo('既存規則','既存規則を複製すると名前や適用範囲を登録できます。',parent=self.host);return
        def apply(v):
            name=self.host.required(v['name'],'名前')
            if name=='既存規則（従来データ）' or any(q['id']!=p['id'] and q['name'].casefold()==name.casefold() for q in self.host.data.get('parameter_presets',[])):raise ValueError('名前が重複しています。')
            p.update(v)
        self.host.form('プリセットの適用範囲',[(k,label,p[k],None) for k,label in (('name','プリセット名'),('period','登録時期・世代'),('component','対象コンポーネント'),('description','説明・適用範囲'))],apply)
    def delete(self):
        p=self.record()
        if not p:return
        if presets.users(self.host.data,p['id']):messagebox.showinfo('使用中','SCOM または定義が使用しています。割り当てを変更してから削除してください。',parent=self.host);return
        if messagebox.askyesno('削除',p['name']+' を削除しますか？ 発行済み冊子は変わりません。',parent=self.host):presets.remove(self.host.data,p['id']);self.host.mark();self.host.render_page()
    def edit_parameter(self):
        selection=self.table.selection()
        if selection:self.parameter_form(next(p for p in self.parameters() if p['id']==selection[0]))
    def parameter_form(self,param=None):
        parameters=self.parameters();ident=presets.selected_id(self.host.data)
        next_id='P'+str(max([int(p['id'][1:]) for p in parameters]+[0])+1)
        fields=([('id','番号（再採番はしません）',next_id,None)] if param is None else [])+[(k,label,(param or {}).get(k,default),choices) for k,label,default,choices in (('role','表示名・式用の役割名','',''),('description','日本語説明・用途（任意）','',''),('unit','単位','mm',''),('value_type','値型','number',['number','word']))]
        fields=[(k,label,value,choices or None) for k,label,value,choices in fields]
        def apply(v):
            if not model.valid_role(v['role']) or any(p is not param and p['role']==v['role'] for p in parameters):raise ValueError('役割名の重複や空白・演算記号を確認してください。説明欄は自由に記入できます。')
            if param:
                if param.get('value_type','number')!=v['value_type'] and any(presets.selected_id(self.host.data,s)==ident and param['id'] in s['values'] for s in self.host.data['scoms']):raise ValueError('SCOM の値がある番号の値型は変更できません。別プリセットを作成してください。')
                presets.rename(self.host.data,param['id'],v['role'],ident);param.update(description=v['description'],unit=v['unit'],value_type=v['value_type'])
            else:
                if len(parameters)>=100 or not re.fullmatch(r'P[1-9]\d*',v['id']) or any(p['id']==v['id'] for p in parameters):raise ValueError('P1 のような未使用の番号を指定してください（最大100件）。')
                parameters.append({k:v[k] for k in ('id','role','description','unit','value_type')})
        self.host.form('プリセットの番号・説明',fields,apply)
    def remove_parameter(self):
        selection=self.table.selection()
        if not selection:return
        pid=selection[0];parameters=self.parameters();ident=presets.selected_id(self.host.data)
        def referenced(value):
            if not isinstance(value,str):return False
            if pid in model.references(value,parameters):return True
            try:return ('PARAM',pid) in expressions.refs(expressions.parse(value,parameters))
            except ValueError:return False
        if any(presets.selected_id(self.host.data,s)==ident and pid in s['values'] for s in self.host.data['scoms']) or any(presets.selected_id(self.host.data,d)==ident and referenced(value) for d in self.host.data['definitions'] for e in element_schema.walk(d['elements']) for value in e['attrs'].values()):messagebox.showinfo('使用中','このプリセットの番号は値または式で使われています。',parent=self.host);return
        if messagebox.askyesno('削除',pid+' を削除しますか？',parent=self.host):parameters[:]=[p for p in parameters if p['id']!=pid];self.host.mark();self.host.render_page()
    def reference_roles(self):
        from .companion_ui import json_dialog
        record=self.record();owner=record if record is not None else self.host.data
        def apply(value):project.validate_reference_roles(value);owner['reference_roles']=value
        json_dialog(self.host,'このプリセットの参照種類別の役割',owner.get('reference_roles',{}),apply)
