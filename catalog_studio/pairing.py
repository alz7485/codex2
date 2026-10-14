"""Editor associations between GMSET and PTSET, separate from E3D attributes."""
import re

PAIR_KEY='paired_ptset_id'
RULES_KEY='set_pairing_name_rules'
DEFAULT_RULES=tuple(
    {'ptset':'{name}'+separator+pt,'gmset':'{name}'+separator+gm}
    for separator in ('-','_','.') for pt,gm in (('PTSET','GMSET'),('PT','GM'),('POINTS','GEOM'),('POINTS','GEOMETRY'))
)+tuple(
    {'ptset':pt+separator+'{name}','gmset':gm+separator+'{name}'}
    for separator in ('-','_','.') for pt,gm in (('PTSET','GMSET'),('PT','GM'))
)


def validate_rules(rules):
    if not isinstance(rules,(list,tuple)) or len(rules)>50:raise ValueError('PTSET / GMSET の命名規則は50組以内で登録してください。')
    for rule in rules:
        if not isinstance(rule,dict):raise ValueError('命名規則の形式を確認してください。')
        for key in ('ptset','gmset'):
            value=rule.get(key)
            if not isinstance(value,str) or len(value)>200 or value.count('{name}')!=1 or re.search(r'[{}]',value.replace('{name}','')):
                raise ValueError('命名規則には {name} を1か所指定してください。')


def rules(data):return data.get(RULES_KEY,DEFAULT_RULES)
def normal(name):return name.strip().lstrip('/').casefold()


def candidates(data,gmset):
    name=normal(gmset['name']);points={}
    for pt in data['definitions']:
        if pt['kind']=='PTSET':points.setdefault(normal(pt['name']),[]).append(pt)
    found={pt['id']:pt for pt in points.get(name,[])}
    for rule in rules(data):
        prefix,suffix=normal(rule['gmset']).split('{name}')
        if not name.startswith(prefix) or not name.endswith(suffix):continue
        stop=len(name)-len(suffix) if suffix else len(name)
        stem=name[len(prefix):stop]
        if not stem:continue
        target=normal(rule['ptset']).replace('{name}',stem)
        for pt in points.get(target,[]):found[pt['id']]=pt
    return list(found.values())


def resolve(data,gmset):
    result={'pointset':None,'source':'none','candidates':[]}
    if not gmset or gmset['kind']!='GMSET':return result
    def point(ident):return next((d for d in data['definitions'] if d['id']==ident and d['kind']=='PTSET'),None)
    if PAIR_KEY in gmset:
        ident=gmset[PAIR_KEY];pt=point(ident)
        return dict(result,pointset=pt,source='manual' if pt else 'missing' if ident else 'unset')
    linked={s.get('ptset_id') for s in data.get('scoms',[]) if s.get('gmset_id')==gmset['id'] and s.get('ptset_id')}
    known=[pt for ident in linked if (pt:=point(ident))]
    if len(linked)>1:return dict(result,source='ambiguous',candidates=known)
    if len(linked)==1:
        pt=point(next(iter(linked)))
        return dict(result,pointset=pt,source='scom' if pt else 'missing')
    draft=data.get('creation_draft',{})
    if draft.get('gmset_id')==gmset['id'] and draft.get('ptset_id'):
        pt=point(draft['ptset_id'])
        return dict(result,pointset=pt,source='draft' if pt else 'missing')
    found=candidates(data,gmset)
    return dict(result,pointset=found[0] if len(found)==1 else None,source='name' if len(found)==1 else 'ambiguous' if found else 'none',candidates=found)


def assign(data,gmset,ident):
    if not gmset or gmset['kind']!='GMSET':raise ValueError('GMSET を選択してください。')
    if ident is None:gmset.pop(PAIR_KEY,None);return
    if not isinstance(ident,str):raise ValueError('PTSET の識別子を指定してください。')
    if ident and not any(d['id']==ident and d['kind']=='PTSET' for d in data['definitions']):raise ValueError('適用する PTSET が見つかりません。')
    gmset[PAIR_KEY]=ident


def users(data,ptset_id):
    return [d for d in data['definitions'] if d['kind']=='GMSET' and (resolve(data,d)['pointset'] or {}).get('id')==ptset_id]
