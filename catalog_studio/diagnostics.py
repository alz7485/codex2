"""Read-only issues with stable editor targets, plus direct navigation."""
import re
from . import project, element_schema as schema, presets


def collect(data):
    rows=[];seen=set()
    def add(message,collection='',record=None,node=None,field=''):
        target=(collection,(record or {}).get('id',''),(node or {}).get('id',''),field,message)
        if target in seen:return
        seen.add(target)
        rows.append(dict(message=message,collection=collection,record_id=target[1],element_id=target[2],field=field,
                         target=' / '.join(r['name'] for r in (record,node) if r)+((' / '+field) if field else '')))
    records=[(c,r) for c in ('definitions','scoms','cates','texts','specs','tables','catalog_details','catalog_props') for r in data.get(c,[])]
    for message in project.issues(data):
        matches=[(c,r) for c,r in records if message.startswith(r['name']+'：') or message.startswith(r['name']+' / ')]
        if not matches:add(message);continue
        length=max(len(r['name']) for c,r in matches);matches=[(c,r) for c,r in matches if len(r['name'])==length]
        if len(matches)!=1:add(message);continue
        collection,record=matches[0];node=None;field=''
        if collection=='definitions':
            nodes=[n for n in schema.walk(record['elements']) if message.startswith(record['name']+' / '+n['name']+' / ')]
            if len(nodes)==1:
                node=nodes[0];tail=message[len(record['name']+' / '+node['name']+' / '):];field=tail.split('：')[0]
        elif collection=='scoms':
            match=re.search(r'：\s*(P[1-9]\d*)\b',message)
            if match:field=match[1]
            elif 'GMSET' in message:field='gmset_id'
            elif 'PTSET' in message:field='ptset_id'
        add(message,collection,record,node,field)
    for d in data['definitions']:
        for node in schema.walk(d['elements']):
            for key in schema.missing_fields(node):add('必須項目が未入力です。','definitions',d,node,key)
        if d['kind']=='PTSET':
            from .point_preview import PointPreview
            model=PointPreview(data,d)
            for number,message in model.problems.items():
                node=model.nodes[number][0]
                key=next((k for k in ('PAXI','PTCDIR','PDIS','PX','PY','PZ') if k in message),'')
                add(message,'definitions',d,node,key)
    return rows


def navigate(host,row):
    if host.commit_definition_name() is False:return False
    collection=row['collection'];record=project.get(host.data,collection,row['record_id']) if collection else None
    if not record:host.status.configure(text='編集先を特定できません。問題の説明を確認してください。');return False
    if collection=='definitions':
        host.definition_id=record['id'];host.switch(record['kind'].lower())
        editor=host.geometry_editor
        if row['element_id'] and editor.elements.exists(row['element_id']):
            editor.element_id=row['element_id'];editor.show_optional_attrs=True
            editor.elements.selection_set(editor.element_id);editor.refresh_element();editor.draw();editor.redraw_points()
            key=row['field'];table=editor.tables['main']
            if key and table.exists(key):
                editor.field=key;table.selection_set(key);table.see(key);table.canvas.focus_set()
    elif collection in ('scoms','cates','texts','catalog_details','catalog_props'):
        if collection=='scoms':host.scom_id=record['id'];host.cate_id=record['cate_id'];host.catalog_tab='scom'
        else:
            host.cate_id=record['id'] if collection=='cates' else record.get('parent_id',record.get('cate_id'))
            host.scom_id=None;host.catalog_tab='members' if collection!='cates' else 'scom'
            host.catalog_member_key=collection+':'+record['id']
        host.registered_browser.catalog_target=collection+':'+record['id'];host.switch('catalog')
        def focus_cell():
            if host.page!='catalog':return
            inspector=host.catalog_inspector
            for iid,(col,ident,path,_) in inspector.fields.items():
                if ident==record['id'] and (not row['field'] or path[-1]==row['field']):
                    inspector.tree.selection_set(iid);inspector.tree.see(iid);inspector.tree.canvas.focus_set();break
        host.after_idle(focus_cell)
    elif collection=='specs':host.spec_id=record['id'];host.switch('specs')
    else:host.switch('tables')
    host.status.configure(text=row['message']);return True


def build(host,parent):
    from tkinter import ttk
    bar=ttk.Frame(parent);bar.pack(fill='x',pady=(0,8))
    info=ttk.Label(bar,text='',style='Muted.TLabel');info.pack(side='left')
    host.diagnostic_rows={}
    tree=host.table(parent,[('target','編集先',330),('message','内容',650)],height=12);host.diagnostic_table=tree
    def refresh():
        tree.delete(*tree.get_children());host.diagnostic_rows={}
        for i,row in enumerate(collect(host.data)):
            iid=str(i);host.diagnostic_rows[iid]=row
            tree.insert('','end',iid=iid,values=(row['target'] or 'プロジェクト',row['message']))
        info.configure(text=str(len(host.diagnostic_rows))+'件。行を選択し「編集箇所へ移動」またはダブルクリック。')
    def goto(_=None):
        chosen=tree.selection()
        if chosen:navigate(host,host.diagnostic_rows[chosen[0]])
    ttk.Button(bar,text='再確認',command=refresh).pack(side='right')
    ttk.Button(bar,text='編集箇所へ移動',command=goto,style='Primary.TButton').pack(side='right',padx=6)
    tree.bind('<Double-1>',goto);tree.bind('<Return>',goto);refresh()
