"""Reusable element groups and atomic, reference-aware point renumbering."""
import copy
import re
import uuid
from . import element_schema as schema, presets, pairing

POINT_AXES={'PAXI','PAAX','PBAX','PCAX','PLAXI','PTCDIR','PTCD'}
POINT_TOKEN=re.compile(r'\b([PT])([0-9]+)\b',re.IGNORECASE)


def point_numbers(elements):
    numbers={}
    for element in elements:
        value=str(element['attrs'].get('NUMB',''))
        if element['type'] not in schema.PT_TYPES or not value.isdigit() or int(value)<=0 or int(value) in numbers:
            raise ValueError('並べ替えには、各ポイントの重複しない正の NUMB が必要です。')
        numbers[int(value)]=element['id']
    return numbers


def remap_points(element,mapping):
    updates={}
    for key,text in element['attrs'].items():
        if not isinstance(text,str):continue
        # P/T in LINE is a point identifier, not the numeric PARAM shorthand.
        if element['type']=='LINE' and key=='PTS':
            updated=POINT_TOKEN.sub(lambda m:m[1]+str(mapping.get(int(m[2]),int(m[2]))),text)
        elif key in POINT_AXES and re.fullmatch(r'\s*[PT]\d+(?:\s+[PT]\d+)*\s*',text,re.IGNORECASE):
            updated=POINT_TOKEN.sub(lambda m:m[1]+str(mapping.get(int(m[2]),int(m[2]))),text)
        else:continue
        if updated!=text:updates[key]=updated
    return updates


def reorder(data,definition,ident,target):
    def locate(items):
        if any(e['id']==ident for e in items):return items
        for element in items:
            found=locate(element.get('children',[]))
            if found is not None:return found
        return None
    siblings=locate(definition['elements'])
    if siblings is None:raise ValueError('要素が見つかりません。')
    index=next(i for i,e in enumerate(siblings) if e['id']==ident)
    target=max(0,min(len(siblings)-1,int(target)))
    if index==target:return False
    ordered=list(siblings);ordered.insert(target,ordered.pop(index));updates=[]
    if definition['kind']=='PTSET' and siblings is definition['elements']:
        old=point_numbers(siblings);by_id={e['id']:i+1 for i,e in enumerate(ordered)}
        mapping={number:by_id[eid] for number,eid in old.items()}
        linked={s.get(key) for s in data['scoms'] if s.get('ptset_id')==definition['id'] for key in ('gmset_id','ngmset_id') if s.get(key)}
        linked.update(d['id'] for d in pairing.users(data,definition['id']))
        for other in data['definitions']:
            if other is not definition and other['id'] not in linked:continue
            changes=[(e,remap_points(e,mapping)) for e in schema.walk(other['elements'])]
            changes=[(e,attrs) for e,attrs in changes if attrs]
            bound=pairing.resolve(data,other)['pointset'] if other is not definition else None
            conflict=bound and bound['id']!=definition['id']
            if changes and other is not definition and (conflict or any(s.get('ptset_id')!=definition['id'] and other['id'] in (s.get('gmset_id'),s.get('ngmset_id')) for s in data['scoms'])):
                raise ValueError('点を参照する GMSET が別の PTSET と共有されています。GMSET を複製して参照を分けてから並べ替えてください。')
            updates.extend(changes)
        for element in ordered:updates.append((element,{'NUMB':str(by_id[element['id']])}))
    if definition['kind']=='PTSET':
        from .point_preview import remember
        remember(data,definition)
    elif definition['kind']=='GMSET':
        from .geometry_preview import remember
        remember(data,definition)
    siblings[:]=ordered
    for element,attrs in updates:element['attrs'].update(attrs)
    return True


def get(data,ident):return next((p for p in data.get('element_presets',[]) if p['id']==ident),None)


def check_name(data,kind,name,exclude=None):
    name=name.strip()
    if not name or any(p['id']!=exclude and p['kind']==kind and p['name'].casefold()==name.casefold() for p in data.get('element_presets',[])):
        raise ValueError('プリセット名が空か、同じ種類のプリセット名と重複しています。')
    return name


def fresh_elements(elements):
    result=copy.deepcopy(elements)
    for node in schema.walk(result):node['id']=uuid.uuid4().hex
    return result


def register(data,definition,name,description=''):
    if definition['kind'] not in ('PTSET','GMSET') or not definition['elements']:raise ValueError('登録する PTSET / GMSET の要素一覧がありません。')
    name=check_name(data,definition['kind'],name)
    if len(data.get('element_presets',[]))>=1000:raise ValueError('要素プリセット数の上限です。')
    record={'id':uuid.uuid4().hex,'name':name,'kind':definition['kind'],'description':description,
            'parameter_preset_id':presets.selected_id(data,definition),'elements':fresh_elements(definition['elements'])}
    if definition['kind']=='PTSET':
        from .point_preview import PointPreview, DIMENSIONS_KEY
        record[DIMENSIONS_KEY]=PointPreview(data,definition).snapshot()
    else:
        from .geometry_preview import GeometryPreview, DIMENSIONS_KEY
        record[DIMENSIONS_KEY]=GeometryPreview(data,definition).snapshot()
    data.setdefault('element_presets',[]).append(record);return record


def update(data,ident,working,name,description=''):
    record=get(data,ident)
    if not record or record['kind']!=working['kind']:raise ValueError('編集する要素プリセットが見つかりません。')
    if not working['elements']:raise ValueError('要素を1つ以上登録してください。')
    name=check_name(data,record['kind'],name,ident)
    metadata={}
    if working['kind']=='PTSET':
        from .point_preview import PointPreview, DIMENSIONS_KEY
        metadata[DIMENSIONS_KEY]=PointPreview(data,working).snapshot()
    else:
        from .geometry_preview import GeometryPreview, DIMENSIONS_KEY
        metadata[DIMENSIONS_KEY]=GeometryPreview(data,working).snapshot()
    record.update(name=name,description=description,parameter_preset_id=presets.selected_id(data,working),elements=fresh_elements(working['elements']),**metadata)
    return record


def recall(data,definition,ident,replace=False):
    record=get(data,ident)
    if not record or record['kind']!=definition['kind']:raise ValueError('同じ種類の要素プリセットを選んでください。')
    profile=record['parameter_preset_id']
    if profile and not presets.get(data,profile):raise ValueError('要素プリセットの PARAM プリセットが見つかりません。編集で規則を選び直してください。')
    if definition['elements'] and not replace and presets.selected_id(data,definition)!=profile:
        raise ValueError('PARAM の規則が異なります。空のセットへ呼び出すか、同じ PARAM プリセットを選んでください。')
    result=fresh_elements(record['elements']);existing=[] if replace else definition['elements']
    if len(existing)+len(result)>200:raise ValueError('要素数は最大200です。')
    if definition['kind']=='PTSET':
        point_numbers(result)
        old_numbers=point_numbers(existing) if existing else {}
        first=max(old_numbers,default=0)+1
        mapping={int(e['attrs']['NUMB']):first+i for i,e in enumerate(result)}
        for i,element in enumerate(result):
            element['attrs'].update(remap_points(element,mapping));element['attrs']['NUMB']=str(first+i)
    names={e['name'] for e in existing}
    for element in result:
        base=element['name'];name=base;n=1
        while name in names:n+=1;name=base+' '+str(n)
        element['name']=name;names.add(name)
    dimensions=None
    if definition['kind']=='PTSET':
        from .point_preview import PointPreview, DIMENSIONS_KEY, merged_dimensions
        dimensions=PointPreview(data,record).snapshot()
        if existing:dimensions=merged_dimensions(PointPreview(data,definition).snapshot(),dimensions)
    else:
        from .geometry_preview import GeometryPreview, DIMENSIONS_KEY, merged_dimensions, pointset_for
        dimensions=GeometryPreview(data,record).snapshot()
        target=dict(definition,elements=existing)
        if replace or not definition['elements']:
            target['parameter_preset_id']=profile
            if presets.selected_id(data,definition)!=profile:target.pop(DIMENSIONS_KEY,None)
        if existing or pointset_for(data,target):dimensions=merged_dimensions(GeometryPreview(data,target).snapshot(),dimensions)
    if replace or not definition['elements']:
        definition['parameter_preset_id']=profile
        definition['element_preset_id']=ident
    else:definition.pop('element_preset_id',None)
    if replace:definition['elements'][:]=result
    else:definition['elements'].extend(result)
    if definition['kind']=='GMSET':
        from .geometry_preview import store
        store(data,definition,dimensions)
    else:definition[DIMENSIONS_KEY]=dimensions
    return result


def validate_library(data):
    from . import project
    records=data.get('element_presets',[])
    project._records(records,'要素プリセット',('name','kind','description','parameter_preset_id'),1000)
    names=set()
    for record in records:
        key=(record['kind'],record['name'].casefold())
        if record['kind'] not in ('PTSET','GMSET') or not record['name'].strip() or key in names:raise ValueError('要素プリセットの名前・種類を確認してください。')
        names.add(key);project.validate_elements(record.get('elements'))
        from .point_geometry import DIMENSIONS_KEY, validate_dimensions
        if DIMENSIONS_KEY in record:validate_dimensions(record[DIMENSIONS_KEY])
