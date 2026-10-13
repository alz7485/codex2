"""Text and project table editors; preserve unresolved record names and attributes."""
import copy
import json
import tkinter as tk
from tkinter import messagebox, ttk
from . import catalogue, project


class CompanionEditor(ttk.Frame):
    def __init__(self,host,collection):
        super().__init__(host.content);self.host=host;self.collection=collection
        self.selected=None;self.allowed=catalogue.TEXT_TYPES if collection=='texts' else catalogue.TABLE_TYPES
        title='説明・材質テキスト' if collection=='texts' else '接続・ボルト・共通テーブル'
        host.heading(title,'親レコードと属性を管理します。未確定のテーブル型・属性は原文のまま保持できます。', [('追加',self.add)])
        self.pack(fill='both',expand=True)
        self.records=host.data.setdefault(collection,[])
        split=ttk.Panedwindow(self,orient='horizontal');split.pack(fill='both',expand=True)
        left=ttk.Frame(split,padding=6);right=ttk.Frame(split,padding=10);split.add(left,weight=3);split.add(right,weight=4);host.balance(split,(.45,))
        self.table=host.table(left,[('name','名前',210),('type','種類',95),('parent','親',180)],height=14)
        self.table.bind('<<TreeviewSelect>>',self.select);self.table.bind('<Double-1>',lambda _:self.edit())
        actions=ttk.Frame(left);actions.pack(fill='x',pady=10)
        for label,fn in [('編集',self.edit),('削除',self.delete),('属性 JSON',self.raw)]:ttk.Button(actions,text=label,command=fn).pack(side='left',padx=3)
        self.details=host.table(right,[('key','属性',90),('meaning','役割',210),('value','値',240)],height=12)
        self.note=ttk.Label(right,text='',style='Muted.TLabel',wraplength=490);self.note.pack(anchor='w',pady=10)
        ttk.Label(right,text='ボルトの BTHK は長さ、NUMBER は穴番号です。\n公称径・分岐表の階層名は未確定のため原文を保持。\nこの画面は管理用で、E3D 実行マクロへの変換は確認待ちです。',style='Muted.TLabel',wraplength=490).pack(anchor='w',pady=10)
        self.refresh()

    def item(self): return next((r for r in self.records if r['id']==self.selected),None)
    def parents(self,item=None):
        parents={'WORLD / 未設定':''}
        parents.update({c['name']:c['id'] for c in self.host.data['cates']})
        parents.update({r['name']+' ['+r['type']+']':r['id'] for r in self.host.data.get('tables',[]) if item is None or r['id'] != item['id']})
        if item and item.get('parent_id') and item['parent_id'] not in parents.values(): parents['参照先不明：'+item['parent_id']]=item['parent_id']
        return parents
    def refresh(self):
        self.table.delete(*self.table.get_children());parents=self.parents()
        for record in self.records:
            parent=next((name for name,ident in parents.items() if ident==record['parent_id']),record['parent_id'])
            self.table.insert('','end',iid=record['id'],values=(record['name'],record['type'],parent))
        if self.selected and self.table.exists(self.selected):self.table.selection_set(self.selected)
        elif self.records:self.table.selection_set(self.records[0]['id'])
        self.select()
    def select(self,_=None):
        selected=self.table.selection();self.selected=selected[0] if selected else None
        self.details.delete(*self.details.get_children());item=self.item()
        if not item:return
        for key,value in item['attrs'].items():self.details.insert('','end',values=(key,catalogue.MEANINGS.get(key,'原文の属性'),str(value)))
        self.note.configure(text=item['name']+' / Rev.'+item['revision']+('\nISODRAFT 用として検証' if item.get('isodraft') else ''))
    def add(self):
        parents=self.parents()
        def apply(v):
            item=catalogue.add_record(self.host.data,self.collection,v['type'],v['name'],parents[v['parent']]);self.selected=item['id']
        self.host.form('管理レコードを追加',[('type','種類',next(iter(self.allowed)),list(self.allowed)),('name','名前','/NEW-RECORD',None),('parent','親レコード',next(iter(parents)),list(parents))],apply)
    def edit(self):
        item=self.item()
        if not item:return
        parents=self.parents(item);parent=next((name for name,ident in parents.items() if ident==item['parent_id']),next(iter(parents)))
        fields=[('name','名前',item['name'],None),('revision','改訂',item['revision'],None),('parent','親レコード',parent,list(parents))]
        if item['type'] in catalogue.TEXT_TYPES:fields.append(('isodraft','ISODRAFT 用','はい' if item.get('isodraft') else 'いいえ',['いいえ','はい']))
        for key in dict.fromkeys(list(self.allowed.get(item['type'],()))+list(item['attrs'])):
            value=item['attrs'].get(key,'');initial=json.dumps(value,ensure_ascii=False) if not isinstance(value,str) else value
            fields.append(('attr:'+key,key+'：'+catalogue.MEANINGS.get(key,'原文属性'),initial,None))
        def apply(v):
            name=self.host.required(v['name'],'名前')
            if any(r['id']!=item['id'] and r['name']==name for r in self.records):raise ValueError('名前が重複しています。')
            candidate=copy.deepcopy(item);candidate.update(name=name,revision=v['revision'],parent_id=parents[v['parent']])
            for key in [k[5:] for k in v if k.startswith('attr:')]:
                raw=v['attr:'+key]
                candidate['attrs'][key]=raw if isinstance(item['attrs'].get(key,''),str) else json.loads(raw)
            if 'isodraft' in v:candidate['isodraft']=v['isodraft']=='はい'
            current=candidate['parent_id'];visited={item['id']};tables={r['id']:r for r in self.host.data.get('tables',[])}
            while current in tables:
                if current in visited:raise ValueError('親階層が循環します。')
                visited.add(current);current=tables[current]['parent_id']
            item.update(candidate)
        self.host.form(item['type']+' を編集',fields,apply)
    def raw(self):
        item=self.item()
        if not item:return
        json_dialog(self.host,'属性 JSON（未確定の属性も保持）',item['attrs'],lambda v:item.update(attrs=v))
    def delete(self):
        item=self.item()
        if not item:return
        ident=item['id']
        if any(e.get(k)==ident for spec in self.host.data['specs'] for e in spec['entries'] for k in ('sdte_id','smte_id')) or any(r.get('parent_id')==ident for key in ('tables','texts') for r in self.host.data.get(key,[])):
            messagebox.showinfo('使用中','SPEC または子レコードから参照されています。',parent=self.host);return
        if messagebox.askyesno('削除',item['name']+' を削除しますか？',parent=self.host):self.records.remove(item);self.host.mark();self.refresh()


def json_dialog(host,title,data,apply):
    win=tk.Toplevel(host);win.title(title);win.transient(host);win.grab_set()
    entry=tk.Text(win,width=80,height=20);entry.pack(padx=14,pady=14,fill='both',expand=True)
    entry.insert('1.0',json.dumps(data,ensure_ascii=False,indent=2))
    error=ttk.Label(win,text='',foreground='#b34e30',wraplength=700);error.pack(padx=14)
    def commit():
        try:
            value=json.loads(entry.get('1.0','end'))
            if not isinstance(value,dict):raise ValueError('JSON オブジェクトを指定してください。')
            apply(value)
        except (ValueError,TypeError) as exc:error.configure(text=str(exc));return
        host.mark();win.destroy();host.render_page()
    ttk.Button(win,text='保存',command=commit).pack(pady=12)
