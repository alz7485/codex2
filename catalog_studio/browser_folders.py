"""Project-local organization; never E3D ownership or macro destinations."""
import copy
import uuid

PAGE_COLLECTIONS={'ptset':'definitions','gmset':'definitions','catalog':'cates','specs':'specs','structural':'definitions','texts':'texts','tables':'tables','books':'books','rules':'parameter_presets'}
PAGES=set(PAGE_COLLECTIONS)


def validate(data):
    folders=data.get('browser_folders',[]);places=data.get('browser_placements',{})
    if not isinstance(folders,list) or len(folders)>1000:raise ValueError('整理フォルダの形式・件数を確認してください。')
    seen={}
    for f in folders:
        if not isinstance(f,dict) or any(not isinstance(f.get(k),str) for k in ('id','page','name','parent_id')):raise ValueError('整理フォルダの項目を確認してください。')
        if not f['id'] or f['id'] in seen or f['page'] not in PAGES:raise ValueError('整理フォルダの識別子・画面を確認してください。')
        if check_name(f['name'])!=f['name']:raise ValueError('フォルダ名の前後の空白を削除してください。')
        seen[f['id']]=f
    for f in folders:
        visited=set();node=f
        while node:
            if node['id'] in visited or len(visited)>32:raise ValueError('フォルダの循環・深すぎる階層は作成できません。')
            visited.add(node['id']);parent=node['parent_id']
            if parent and (parent not in seen or seen[parent]['page']!=f['page']):raise ValueError('フォルダの親が不正です。')
            node=seen.get(parent)
        if sum(g['page']==f['page'] and g['parent_id']==f['parent_id'] and g['name'].casefold()==f['name'].casefold() for g in folders)>1:raise ValueError('同じ場所に同名のフォルダがあります。')
    if not isinstance(places,dict) or len(places)>20000:raise ValueError('フォルダ配置の形式・件数を確認してください。')
    for key,ident in places.items():
        if not isinstance(key,str) or len(key)>500 or '|' not in key or not isinstance(ident,str) or ident not in seen or key.split('|',1)[0]!=seen[ident]['page']:raise ValueError('フォルダ配置の参照が不正です。')
        page,record=key.split('|',1);collection,sep,rid=record.partition(':')
        if not sep or not rid or collection!=PAGE_COLLECTIONS[page]:raise ValueError('フォルダ配置の対象が不正です。')


def check_name(name):
    if not isinstance(name,str) or not name.strip() or len(name)>100 or any(c in name for c in '/\\\n\r\t') or name.strip() in ('.','..'):raise ValueError('フォルダ名は100文字以内で、/・改行を含めず入力してください。')
    return name.strip()


def candidate(data):
    result=dict(data)
    result['browser_folders']=copy.deepcopy(data.get('browser_folders',[]))
    result['browser_placements']=dict(data.get('browser_placements',{}))
    return result


def apply(data,result):
    validate(result)
    data['browser_folders']=result['browser_folders'];data['browser_placements']=result['browser_placements']


def add(data,page,name,parent=''):
    result=candidate(data);f=dict(id=str(uuid.uuid4()),page=page,name=check_name(name),parent_id=parent)
    result['browser_folders'].append(f);apply(data,result);return f['id']


def update(data,ident,*,name=None,parent=None):
    result=candidate(data);f=next((f for f in result['browser_folders'] if f['id']==ident),None)
    if f is None:raise ValueError('フォルダが見つかりません。')
    if name is not None:f['name']=check_name(name)
    if parent is not None:f['parent_id']=parent
    apply(data,result)


def move(data,page,key,folder=''):
    if page not in PAGES or not movable(page,key):raise ValueError('CATEの中身はCATE単位で整理してください。')
    collection,ident=key.split(':',1)
    record=next((r for r in data.get(collection,[]) if r['id']==ident),None)
    if record is None or collection!=PAGE_COLLECTIONS[page]:raise ValueError('移動対象が見つかりません。')
    if page in ('ptset','gmset') and record.get('kind')!=page.upper():raise ValueError('異なる種類の画面へ移動できません。')
    if page=='structural' and record.get('kind') in ('PTSET','GMSET'):raise ValueError('異なる種類の画面へ移動できません。')
    result=candidate(data);place=page+'|'+key
    if folder:result['browser_placements'][place]=folder
    else:result['browser_placements'].pop(place,None)
    apply(data,result)


def movable(page,key):
    collection,_,ident=key.partition(':')
    return bool(ident) and ident!='legacy' and (page!='catalog' or collection=='cates')


def remove(data,ident):
    result=candidate(data)
    if not any(f['id']==ident for f in result['browser_folders']):raise ValueError('フォルダが見つかりません。')
    if any(f['parent_id']==ident for f in result['browser_folders']):raise ValueError('空のフォルダだけ削除できます。')
    for key,value in result['browser_placements'].items():
        if value!=ident:continue
        _,record=key.split('|',1);collection,rid=record.split(':',1)
        if any(r['id']==rid for r in data.get(collection,[])):raise ValueError('空のフォルダだけ削除できます。')
    result['browser_folders']=[f for f in result['browser_folders'] if f['id']!=ident]
    result['browser_placements']={k:v for k,v in result['browser_placements'].items() if v!=ident};apply(data,result)


def choices(data,page):
    folders={f['id']:f for f in data.get('browser_folders',[]) if f['page']==page}
    result={'（最上位）':''}
    for f in folders.values():
        parts=[f['name']];parent=f['parent_id']
        while parent:parts.insert(0,folders[parent]['name']);parent=folders[parent]['parent_id']
        result['フォルダ：'+' / '.join(parts)]=f['id']
    return result
