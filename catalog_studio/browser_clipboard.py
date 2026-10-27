"""In-project cut/copy/paste for authoring sets and their organizing folders."""
import copy
import uuid
from . import browser_folders as folders, element_schema as schema, project


class Clipboard:
    def __init__(self,data,page,key,cut=False):
        self.data=data;self.page=page;self.key=key;self.cut=cut
        if key.startswith('folder:'):
            ident=key.split(':',1)[1]
            source=next((f for f in data.get('browser_folders',[]) if f['id']==ident and f['page']==page),None)
            if not source:raise ValueError('フォルダが見つかりません。')
            ids={ident}
            while True:
                more={f['id'] for f in data.get('browser_folders',[]) if f['parent_id'] in ids}
                if more<=ids:break
                ids|=more
            self.folders=copy.deepcopy([f for f in data['browser_folders'] if f['id'] in ids])
            places=data.get('browser_placements',{})
            keys={k.split('|',1)[1] for k,v in places.items() if k.startswith(page+'|') and v in ids}
            self.root=ident
        else:
            if not folders.movable(page,key):raise ValueError('この項目は移動できません。')
            collection,ident=key.split(':',1)
            if collection!=folders.PAGE_COLLECTIONS.get(page) or not any(r['id']==ident for r in data.get(collection,[])):raise ValueError('対象が見つかりません。')
            self.folders=[];self.root=None;keys={key}
        if not cut and page not in ('ptset','gmset'):raise ValueError('コピーはPTSET・GMSET画面で使用できます。')
        self.records=copy.deepcopy([r for r in data.get('definitions',[]) if 'definitions:'+r['id'] in keys])
        if not cut and not self.root and not self.records:raise ValueError('コピーするセットが見つかりません。')
        if not cut and any(r['kind']!=page.upper() for r in self.records):raise ValueError('異なる種類のセットはコピーできません。')
        self.places=dict(data.get('browser_placements',{}))
        self.order=folders.ordered_keys(data,page) if not cut else []

    def paste(self,data,page,target=''):
        if data is not self.data:raise ValueError('プロジェクトが変わりました。もう一度コピーしてください。')
        if page!=self.page:raise ValueError('同じ種類の画面へ貼り付けてください。')
        if target and not any(f['id']==target and f['page']==page for f in data.get('browser_folders',[])):raise ValueError('貼り付け先のフォルダが見つかりません。')
        if self.cut:
            if self.root:
                folders.update(data,self.root,parent=target)
            else:folders.move(data,page,self.key,target)
            return self.key
        candidate=copy.deepcopy(data)
        copied_folders=copy.deepcopy(self.folders)
        ids={f['id']:uuid.uuid4().hex for f in copied_folders}
        copied_keys={'folder:'+old:'folder:'+new for old,new in ids.items()}
        def unique(name,used):
            base=name+'-COPY';value=base;i=2
            while value.casefold() in used:value=base+str(i);i+=1
            used.add(value.casefold());return value
        for f in copied_folders:
            old=f['id'];f['id']=ids[old]
            if old==self.root:
                used={g['name'].casefold() for g in candidate.get('browser_folders',[]) if g['page']==page and g['parent_id']==target}
                f['name']=unique(f['name'],used);f['parent_id']=target
            else:f['parent_id']=ids[f['parent_id']]
        candidate.setdefault('browser_folders',[]).extend(copied_folders)
        new_records=copy.deepcopy(self.records);used={r['name'].casefold() for r in data['definitions']}
        places=candidate.setdefault('browser_placements',{})
        for r in new_records:
            old=r['id'];r['id']=uuid.uuid4().hex;r['name']=unique(r['name'],used)
            copied_keys['definitions:'+old]='definitions:'+r['id']
            for node in schema.walk(r['elements']):node['id']=uuid.uuid4().hex
            destination=ids[self.places[page+'|definitions:'+old]] if self.root else target
            if destination:places[page+'|definitions:'+r['id']]=destination
        candidate['definitions'].extend(new_records)
        if 'browser_order' in data:
            order=folders.ordered_keys(data,page)
            order.extend(copied_keys[k] for k in self.order if k in copied_keys)
            candidate.setdefault('browser_order',{})[page]=order
        project.validate(candidate)
        data['definitions'].extend(new_records)
        data['browser_folders']=candidate['browser_folders'];data['browser_placements']=places
        if 'browser_order' in candidate:data['browser_order']=candidate['browser_order']
        return 'folder:'+ids[self.root] if self.root else 'definitions:'+new_records[0]['id']
