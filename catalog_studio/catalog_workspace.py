"""Catalogue creation and SPEC associations; no assumed E3D DETAIL/PROP commands."""
import copy
import uuid

from . import catalogue, presets

COLLECTIONS = {'DETAIL':'catalog_details', 'PROP':'catalog_props'}
ENTRY_REFS = {'detail_id':'catalog_details', 'prop_id':'catalog_props'}


def find(data, collection, ident):
    return next((record for record in data.get(collection,[]) if record['id']==ident),None)


def check_name(data, name, exclude=None):
    name = name.strip()
    if not name or len(name)>1000 or any(char in name for char in '\x00\r\n'):
        raise ValueError('名前を1行・1000文字以内で入力してください。')
    for collection in ('cates','scoms','definitions','specs','texts','tables',*COLLECTIONS.values()):
        if any(record is not exclude and record['name'].casefold()==name.casefold() for record in data.get(collection,[])):
            raise ValueError('同じ名前のレコードがあります：'+name)
    for prop in data.get('catalog_props',[]):
        if any(child is not exclude and child['name'].casefold()==name.casefold() for child in prop.get('children',[])):
            raise ValueError('同じ名前のCMPDATAがあります：'+name)
    return name


def add_association(data, kind, name, cate_id, *, description='', attrs=None, sdte_id=''):
    if kind not in COLLECTIONS: raise ValueError('DETAIL または PROP を指定してください。')
    if not find(data,'cates',cate_id): raise ValueError('関連する CATE を選択してください。')
    name = check_name(data,name)
    if attrs is not None and not isinstance(attrs,dict): raise ValueError('属性はJSONオブジェクトです。')
    if sdte_id and (find(data,'texts',sdte_id) or {}).get('type')!='SDTE': raise ValueError('SDTE の参照先を確認してください。')
    collection = COLLECTIONS[kind]
    if len(data.get(collection,[]))>=5000: raise ValueError('関連レコード数の上限です。')
    record = {'id':uuid.uuid4().hex, 'name':name, 'cate_id':cate_id, 'revision':'01',
              'description':description, 'attrs':copy.deepcopy(attrs or {})}
    if kind=='DETAIL': record['sdte_id']=sdte_id
    data.setdefault(collection,[]).append(record)
    return record


def validate(data):
    from . import project
    for collection in COLLECTIONS.values():
        project._records(data.get(collection,[]),collection,('name','cate_id','revision','description'),5000)
        for record in data.get(collection,[]):
            if not isinstance(record.get('attrs'),dict): raise ValueError('DETAIL / PROP の属性は辞書です。')
            if not isinstance(record.get('sdte_id',''),str): raise ValueError('DETAIL のSDTE参照は識別子です。')
    child_ids=set();child_names=set()
    for prop in data.get('catalog_props',[]):
        children=prop.get('children',[])
        if not isinstance(children,list) or len(children)>5000:raise ValueError('CMPDATAの件数・形式が不正です。')
        for child in children:
            if not isinstance(child,dict) or any(not isinstance(child.get(k),str) or not child[k] for k in ('id','name')) or child.get('type')!='CMPDATA' or not isinstance(child.get('attrs'),dict):raise ValueError('CMPDATAの形式が不正です。')
            if child['id'] in child_ids or child['name'].casefold() in child_names:raise ValueError('CMPDATAが重複しています。')
            check_name(data,child['name'],exclude=child)
            child_ids.add(child['id']);child_names.add(child['name'].casefold())
            if 'CWEI' in child['attrs'] and not project._finite(child['attrs']['CWEI']):raise ValueError('CWEIは有限数値です。')
    for spec in data.get('specs',[]):
        for entry in spec.get('entries',[]):
            if any(key in entry and not isinstance(entry[key],str) for key in ENTRY_REFS):
                raise ValueError('SPEC のDETAIL / PROP参照は識別子です。')


def issues(data):
    result=[]
    for kind,collection in COLLECTIONS.items():
        for record in data.get(collection,[]):
            if not find(data,'cates',record['cate_id']): result.append(record['name']+'：関連する CATE が見つかりません。')
            ident=record.get('sdte_id','')
            if ident and (find(data,'texts',ident) or {}).get('type')!='SDTE': result.append(record['name']+'：SDTE の参照先が不正です。')
    for spec in data['specs']:
        for entry in spec['entries']:
            if not any(key in entry for key in ENTRY_REFS):continue
            for key,collection in ENTRY_REFS.items():
                if not find(data,collection,entry.get(key,'')):
                    result.append(spec['name']+'：'+key.removesuffix('_id').upper()+' が未選択または見つかりません。')
    return result


def used(data, collection, ident):
    if any(entry.get(key)==ident for spec in data['specs'] for entry in spec['entries']
           for key,target in ENTRY_REFS.items() if target==collection): return True
    return collection=='texts' and any(record.get('sdte_id')==ident for record in data.get('catalog_details',[]))


def prepare_bundle(data, name, *, description='', preset_id='', gmset_id='', ptset_id='',
                   names=None, rtex='', stext='', prop_attrs=None):
    """Build all six related records in a copy, so any error leaves data untouched."""
    from . import project
    name=check_name(data,name); candidate=copy.deepcopy(data)
    if preset_id and not presets.get(candidate,preset_id): raise ValueError('PARAM プリセットが見つかりません。')
    for ident,kind in ((gmset_id,'GMSET'),(ptset_id,'PTSET')):
        if not ident:continue
        definition=find(candidate,'definitions',ident)
        if not definition or definition['kind']!=kind:raise ValueError(kind+' の参照先が不正です。')
        presets.require_compatible(candidate,{'parameter_preset_id':preset_id},definition)
    cate=project.add_cate(candidate,name); cate['description']=description
    chosen={kind:((names or {}).get(kind,'').strip() or name.rstrip('/')+'/'+kind) for kind in ('SDTE','TEXT','SCOM','DETAIL','PROP')}
    if len({value.casefold() for value in chosen.values()})!=len(chosen):raise ValueError('一緒に作成するレコードの名前が重複しています。')
    for kind in ('SDTE','TEXT','SCOM','DETAIL','PROP'):
        check_name(candidate,chosen[kind])
        if list(chosen.values()).count(chosen[kind])>1:raise ValueError('一緒に作成するレコードの名前が重複しています。')
    sdte=catalogue.add_record(candidate,'texts','SDTE',chosen['SDTE'],cate['id']); sdte['attrs']['RTEX']=rtex
    text=catalogue.add_record(candidate,'texts','TEXT',chosen['TEXT'],cate['id']); text['attrs']['STEXT']=stext
    scom=project.add_scom(candidate,cate['id'],chosen['SCOM'])
    scom.update(gmset_id=gmset_id,ptset_id=ptset_id,parameter_preset_id=preset_id)
    detail=add_association(candidate,'DETAIL',chosen['DETAIL'],cate['id'],sdte_id=sdte['id'])
    prop=add_association(candidate,'PROP',chosen['PROP'],cate['id'],attrs=prop_attrs)
    project.validate(candidate)
    return candidate, {'CATE':cate,'SDTE':sdte,'TEXT':text,'SCOM':scom,'DETAIL':detail,'PROP':prop}
