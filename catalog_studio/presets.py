"""Numbered parameter dictionaries selected independently for each catalogue record."""
import copy
import re
import uuid
from . import model, element_schema


def selected_id(data, record=None):
    return record.get('parameter_preset_id','') if record is not None else data.get('active_parameter_preset_id','')


def get(data, ident):
    return next((p for p in data.get('parameter_presets',[]) if p['id']==ident),None)


def rules(data, record=None):
    ident=selected_id(data,record)
    if not ident:return data['parameters']
    preset=get(data,ident)
    return preset['parameters'] if preset else []


def reference_roles(data,record=None):
    ident=selected_id(data,record)
    if not ident:return data.get('reference_roles',{})
    return (get(data,ident) or {}).get('reference_roles',{})


def label(data,record=None):
    ident=selected_id(data,record)
    if not ident:return '既存規則（従来データ）'
    preset=get(data,ident)
    return preset['name'] if preset else '参照先不明：'+ident


def caption(parameter):
    description=parameter.get('description','')
    return parameter['role'] + ('：'+description if description else '')


_DISPLAY_REFERENCE = re.compile(
    r"(?P<quoted>\"[^\"\n]*\"|'[^'\n]*')|"
    r'(?<!\w)(?P<reference>(?P<family>DES\s+(?:APARAM|OPARAM|PARAM|APARA|OPARA|PARA)|'
    r'IPARAM|APARAM|OPARAM|PARAM|IPARA|APARA|OPARA|PARA|DESP|DESA|DESO)'
    r'\b(?:\s*\[\s*(?P<bracket>[1-9]\d*)\s*\]|\s+(?P<number>[1-9]\d*)\b)|'
    r'P(?P<short>[1-9]\d*)\b)', re.IGNORECASE)


def display_expression(data, record, text):
    """Add preset names for display only, keeping spelling and stored text intact."""
    from .expressions import ALIASES
    names={p['id']:p['role'] for p in rules(data,record)}
    others=reference_roles(data,record)
    def annotate(match):
        if match.group('quoted') is not None:return match[0]
        raw_family=' '.join((match.group('family') or 'PARAM').upper().split())
        if raw_family.startswith('DES '):
            family='DES '+ALIASES.get(raw_family[4:],raw_family[4:])
        else:family=ALIASES.get(raw_family,raw_family)
        pid='P'+(match.group('bracket') or match.group('number') or match.group('short'))
        name=names.get(pid) if family=='PARAM' else others.get(family,{}).get(pid)
        return match['reference']+'（'+(name or '設定名未登録')+'）'
    return _DISPLAY_REFERENCE.sub(annotate,str(text))


def choices(data):
    return {'既存規則（従来データ）':'', **{p['name']:p['id'] for p in data.get('parameter_presets',[])}}


def require_compatible(data,scom,definition):
    for record in (scom,definition):
        ident=selected_id(data,record)
        if ident and not get(data,ident):raise ValueError('PARAM プリセットが見つかりません：'+ident)
    if selected_id(data,scom) != selected_id(data,definition):
        raise ValueError('PARAM プリセットが異なります：SCOM '+label(data,scom)+' / 定義 '+label(data,definition))


def add(data,name,source=None):
    records=data.setdefault('parameter_presets',[])
    if len(records)>=1000:raise ValueError('プリセット数の上限です。')
    if not name.strip() or name=='既存規則（従来データ）' or any(p['name'].casefold()==name.casefold() for p in records):raise ValueError('プリセット名が空か重複しています。')
    source_record={'parameter_preset_id':source or ''}
    if source and not get(data,source):raise ValueError('複製元プリセットが見つかりません。')
    record={'id':uuid.uuid4().hex,'name':name,'period':'','component':'','description':'',
            'parameters':copy.deepcopy(rules(data,source_record)),
            'reference_roles':copy.deepcopy(reference_roles(data,source_record))}
    records.append(record);return record


def stamp(data,record):
    ident=selected_id(data)
    if ident:record['parameter_preset_id']=ident
    return record


def users(data,ident):
    return [r for collection in ('scoms','definitions') for r in data[collection] if selected_id(data,r)==ident]


def remove(data,ident):
    if not get(data,ident):raise ValueError('削除するプリセットがありません。')
    if users(data,ident):raise ValueError('SCOM または定義が使用しています。先に割り当てを変更してください。')
    data['parameter_presets']=[p for p in data['parameter_presets'] if p['id']!=ident]
    if selected_id(data)==ident:data['active_parameter_preset_id']=''


def _rewrite_aliases(definition,mapping):
    literals={'方向','PAXI','PAAX','PBAX','PCAX','PLAXI','PTCDIR','PTCD','DESC','PURP','PSKEY','GTYP','SKEY','NUMB','NAPP','PKEY','LEVEL','PTS','CLFLA','TUFLA','TVISI','BVISI','OBST'}
    for element in element_schema.walk(definition['elements']):
        fields=set(model.SCHEMAS.get(element['type'],('',()))[1]) | set(element_schema.fields(element['type']))
        for key,value in element['attrs'].items():
            if isinstance(value,str) and key in fields and key not in literals:
                element['attrs'][key]=re.sub(r'[^\s+*/()\-]+',lambda m:mapping.get(m[0],m[0]),value)


def bind(data,record,ident):
    """Change only the explicit binding. Never remap numbers or numerical values.

    Role aliases are converted to their old number before changing a dictionary,
    so two dictionaries with swapped Japanese names cannot change expression meaning.
    """
    if ident and not get(data,ident):raise ValueError('プリセットが見つかりません。')
    if selected_id(data,record)==ident:return
    old_rules=rules(data,record)
    if 'values' in record:
        from . import project
        for parameter in rules(data,{'parameter_preset_id':ident}):
            if parameter['id'] in record['values']:
                value=record['values'][parameter['id']]
                if parameter.get('value_type','number')=='number' and not project._finite(value):raise ValueError(parameter['id']+' の値型が合いません。値を変更せず割り当てを中止しました。')
                project.parse_value(parameter,value)
    history={'preset_id':selected_id(data,record)}
    if 'elements' in record:
        history['elements']=copy.deepcopy(record['elements'])
        _rewrite_aliases(record,{p['role']:p['id'] for p in old_rules})
    record.setdefault('parameter_preset_history',[]).append(history)
    record['parameter_preset_id']=ident


def rename(data,pid,new_role,ident=''):
    parameters=rules(data,{'parameter_preset_id':ident})
    if not model.valid_role(new_role) or any(p['id']!=pid and p['role']==new_role for p in parameters):raise ValueError('役割名の重複や空白・演算記号を確認してください。')
    parameter=next((p for p in parameters if p['id']==pid),None)
    if not parameter:raise ValueError('パラメータがありません。')
    for definition in data['definitions']:
        if selected_id(data,definition)==ident:_rewrite_aliases(definition,{parameter['role']:new_role})
    parameter['role']=new_role
