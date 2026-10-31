"""Conservative compact macros for standalone SDTEXT and CMPTYPE/CMPDATA."""
import math
from . import project,macro_destinations,catalog_macro


def creation_text(data,collection,ident,destination='',lock_created=False):
    if collection not in ('catalog_details','catalog_props'):raise ValueError('SDTEまたはCMPTを選択してください。')
    record=project.get(data,collection,ident)
    if not record:raise ValueError('出力するSDTEまたはCMPTがありません。')
    # Record names may contain spaces in the database, but not command separators.
    def name(value):return macro_destinations.normalize(value)
    lines=[macro_destinations.normalize(destination)] if destination else []
    def emit(r,kind,allowed):
        attrs=r.get('attrs',{})
        unknown=set(attrs)-set(allowed)
        if unknown:raise ValueError('未対応属性を保持できないため出力できません：'+', '.join(sorted(unknown)))
        lines.append('NEW '+kind+' '+name(r['name']))
        for key,value in attrs.items():
            if key=='CWEI':
                if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('CWEIは有限数値です。')
                lines.append('CWEI ('+str(value)+')')
            else:lines.append(key+' '+catalog_macro.quote(value))
    if collection=='catalog_details':
        emit(record,'SDTEXT',('SKEY','RTEX','TTEX','STEX'))
        if lock_created or record.get('macro_locked'):lines.append('LOCK')
        lines.append('END')
    else:
        emit(record,'CMPTYPE',())
        for child in record.get('children',[]):
            if child.get('type')!='CMPDATA':raise ValueError('CMPT配下の種類を確認してください。')
            emit(child,'CMPDATA',('CWEI',))
            if lock_created or child.get('macro_locked'):lines.append('LOCK')
            lines.append('END')
        if lock_created or record.get('macro_locked'):lines.append('LOCK')
        lines.append('END')
    return '\n'.join(lines)+'\n'


def import_text(data,text,cate_id):
    if not project.get(data,'cates',cate_id):raise ValueError('関連CATEを選択してください。')
    candidate,roots=catalog_macro.import_text(data,text,cate_id)
    targets=[(col,r['id']) for col in ('catalog_details','catalog_props') for r in candidate.get(col,[]) if r['id'] in roots]
    if len(targets)!=len(roots):raise ValueError('この画面では単独SDTEXTとCMPTYPEのマクロを読み込めます。CATEはCATE作成で読み込んでください。')
    return candidate,targets
