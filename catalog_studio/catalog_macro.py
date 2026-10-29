"""Conservative CATE / SDTE / TEXT / SCOM creation macros; never execute commands."""
import re
from . import project,catalogue,macro_destinations


def quote(value):
    if not isinstance(value,str) or any(c in value for c in "'\r\n\x00"):
        raise ValueError('文字列は引用符・改行を含まない1行で指定してください。')
    return "'"+value+"'"


def name(value):
    value=macro_destinations.normalize(value)
    if not value:raise ValueError('要素名が空です。')
    return value


def creation_text(data,cate_id,destination=''):
    cate=project.get(data,'cates',cate_id)
    if not cate:raise ValueError('出力するCATEを選択してください。')
    lines=[macro_destinations.normalize(destination)] if destination else []
    lines+=['NEW CATE '+name(cate['name'])]
    for key,value in cate.get('attrs',{}).items():
        if key not in ('PURP','GTYP'):raise ValueError('未対応のCATE属性：'+key)
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*',value):raise ValueError('CATE属性はwordです。')
        lines.append(key+' '+value)
    # Application description/revision are not assumed to be E3D attributes.
    for r in data['texts']:
        if r['parent_id']!=cate_id:continue
        if r['type'] not in ('SDTE','TEXT'):raise ValueError('このCATEには未対応の文字要素があります。')
        lines+=['NEW '+r['type']+' '+name(r['name'])]
        for key,value in r['attrs'].items():
            if key not in catalogue.TEXT_TYPES[r['type']]:raise ValueError('未対応の属性：'+key)
            if value:lines.append(('STEX' if r['type']=='TEXT' and key=='STEXT' else key)+' '+quote(value))
        lines.append('END')
    for r in data['scoms']:
        if r['cate_id']!=cate_id:continue
        if r.get('size') or any(r.get(k) for k in ('ngmset_id','gmsset_id','ptsset_id')):raise ValueError('SIZE・構造材参照の出力構文は未確認です。')
        if any(key!='GTYP' for key in r.get('attrs',{})):raise ValueError('SCOMの追加属性の出力構文は未確認です。')
        lines+=['NEW SCOM '+name(r['name'])]
        if 'GTYP' in r.get('attrs',{}):
            value=r['attrs']['GTYP']
            if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*',value):raise ValueError('GTYPはwordです。')
            lines.append('GTYP '+value)
        values=r['values']
        if values:
            last=max(int(k[1:]) for k in values)
            parts=[]
            for i in range(1,last+1):
                v=values.get('P'+str(i),0)
                parts.append(quote(v) if isinstance(v,str) else str(v))
            lines.append('PARA '+' '.join(parts))
        for key,value in r.get('component_attrs',{}).items():
            if key!='ANGL':raise ValueError('未対応のSCOM属性：'+key)
            lines.append('ANGL '+str(float(value)))
        for key,attr in (('gmset_id','GMRE'),('ptset_id','PTRE'),('ngmset_id','NGMSET'),('gmsset_id','GMSSET'),('ptsset_id','PTSSET')):
            if r.get(key):
                target=project.get(data,'definitions',r[key])
                if not target and not r[key].startswith('/'):raise ValueError('参照先が見つかりません：'+attr)
                lines.append(attr+' '+name(target['name'] if target else r[key]))
        lines.append('END')
    lines.append('END')
    return '\n'.join(lines)+'\n'


def import_text(data,text,cate_id=''):
    from .catalog_macro_reader import import_text as read
    return read(data,text,cate_id)
