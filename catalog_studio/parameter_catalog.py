"""Transactional preset editing and explicit CATE TEXT/STEXT generation."""
import copy
import re
import string
import uuid
from . import presets, project, expressions, element_schema as schema


def ordered(parameters):return sorted(parameters,key=lambda p:int(p['id'][1:]))


def in_use(data,ident,pid):
    if any(presets.selected_id(data,s)==ident and pid in s['values'] for s in data['scoms']):return True
    parameters=presets.rules(data,{'parameter_preset_id':ident})
    literal={'NUMB','DESC','PURP','PSKEY','GTYP','SKEY','LEVEL','NAPP','OBST','PTS','TVISI','BVISI','CLFLA','TUFLA'}
    axes={'PAXI','PAAX','PBAX','PCAX','PLAXI','PTCDIR','PTCD'}
    role=next((p['role'] for p in parameters if p['id']==pid),'')
    for d in data['definitions']+data.get('element_presets',[]):
        if presets.selected_id(data,d)!=ident:continue
        for node in schema.walk(d['elements']):
            for key,value in node['attrs'].items():
                if key in literal or not isinstance(value,str):continue
                if key not in axes:
                    try:
                        if ('PARAM',pid) in expressions.refs(expressions.parse(value,parameters)):return True
                    except ValueError:pass
                for match in presets._DISPLAY_REFERENCE.finditer(value):
                    if match.group('quoted') is not None:continue
                    family=expressions.ALIASES.get((match.group('family') or '').upper(),match.group('family'))
                    number=match.group('bracket') or match.group('number') or match.group('short')
                    if family=='PARAM' and 'P'+number==pid:return True
                if key not in axes and role and re.search(r'(?<!\w)'+re.escape(role)+r'(?!\w)',value):return True
    return False


def save_preset(data,ident,working):
    original=presets.get(data,ident) if ident else None
    if ident and original is None:raise ValueError('保存先のプリセットが見つかりません。')
    parameters=copy.deepcopy(working['parameters']);project.validate_parameters(parameters)
    for p in parameters:
        if not presets.meaning(p).strip():raise ValueError(p['id']+' の日本語の意味を入力してください。')
    metadata={}
    if original is not None:
        metadata={k:str(working.get(k,'')).strip() for k in ('name','period','component','description')}
        name=metadata['name']
        if not name or name=='既存規則（従来データ）' or any(p['id']!=ident and p['name'].casefold()==name.casefold() for p in data.get('parameter_presets',[])):raise ValueError('プリセット名が空か重複しています。')
    old=presets.rules(data,{'parameter_preset_id':ident});by_id={p['id']:p for p in old};new_ids={p['id'] for p in parameters}
    for pid in set(by_id)-new_ids:
        if in_use(data,ident,pid):raise ValueError(pid+' は式・SCOM・要素プリセットで使用中のため削除・再採番できません。')
    for p in parameters:
        previous=by_id.get(p['id'])
        if previous and p['role']!=previous['role']:raise ValueError('既存の式用別名は保持してください。意味の欄で表示名を変更できます。')
        if previous and previous.get('value_type','number')!=p.get('value_type','number') and any(presets.selected_id(data,s)==ident and p['id'] in s['values'] for s in data['scoms']):raise ValueError(p['id']+' の値型は SCOM で使用中です。別プリセットを作成してください。')
    reference_roles=copy.deepcopy(working.get('reference_roles',{}));project.validate_reference_roles(reference_roles)
    result=[]
    for p in ordered(parameters):
        target=by_id.get(p['id'],{})
        target.clear();target.update(p);result.append(target)
    old[:]=result
    if original is not None:original.update(metadata,reference_roles=reference_roles)
    else:data['reference_roles']=reference_roles


def text_preview(data,working,cate_id,pattern='{cate}/PARAM{number}',combined=False,name='',separator='\n'):
    cate=project.get(data,'cates',cate_id)
    if not cate:raise ValueError('作成先の CATE を選択してください。')
    parameters=ordered(working['parameters']);project.validate_parameters(parameters)
    if not parameters:raise ValueError('PARAM を1つ以上登録してください。')
    if len(pattern)>2000:raise ValueError('TEXT 名の規則が長すぎます。')
    try:
        for _,key,spec,conversion in string.Formatter().parse(pattern):
            if key is not None and (key not in ('cate','number') or spec or conversion):raise ValueError('TEXT 名には {cate} と {number} を使用できます。')
    except ValueError as exc:raise ValueError('TEXT 名の規則を確認してください：'+str(exc)) from exc
    rows=[];names=set()
    for p in parameters:
        english=p.get('english_name','')
        if not english.strip():raise ValueError(p['id']+' の意味の英語名を入力してください。')
        if any(c in english for c in ('\n','\r','\x00')):raise ValueError(p['id']+' の英語名は1行で入力してください。')
        target=name.strip() if combined else pattern.format(cate=cate['name'].rstrip('/'),number=int(p['id'][1:])).strip()
        if not target or '\x00' in target or '\n' in target or '\r' in target:raise ValueError('TEXT 名を1行で入力してください。')
        if not combined and target in names:raise ValueError('TEXT 名が重複します。規則に {number} を含めてください。')
        names.add(target);rows.append({'name':target,'pid':p['id'],'STEXT':english})
    if combined:
        rows=[{'name':name.strip(),'pid':', '.join(p['id'] for p in parameters),'STEXT':separator.join(p.get('english_name','') for p in parameters)}]
    for row in rows:
        matches=[r for r in data.get('texts',[]) if r['name']==row['name']]
        if len(matches)>1:raise ValueError('同名のテキストが複数あります：'+row['name'])
        existing=matches[0] if matches else None
        if existing and (existing['type']!='TEXT' or existing['parent_id']!=cate_id):raise ValueError('別の種類または別 CATE の同名レコードがあります：'+row['name'])
        row.update(existing_id=existing['id'] if existing else '',old=existing['attrs'].get('STEXT','') if existing else '',action='更新' if existing else '新規')
    return rows


def write_texts(data,working,cate_id,expected=None,**options):
    rows=text_preview(data,working,cate_id,**options)
    if expected is not None and rows!=expected:raise ValueError('既存 TEXT または入力内容が変更されています。プレビューを更新してください。')
    if len(data.get('texts',[]))+sum(not r['existing_id'] for r in rows)>5000:raise ValueError('管理レコードの上限です。')
    staged=[]
    for row in rows:
        old=project.get(data,'texts',row['existing_id'])
        record=copy.deepcopy(old) if old else {'id':uuid.uuid4().hex,'type':'TEXT','name':row['name'],'parent_id':cate_id,'revision':'01','attrs':{}}
        if old and row['old']!=row['STEXT']:record.setdefault('stext_history',[]).append(row['old'])
        record['attrs']['STEXT']=row['STEXT']
        record['parameter_text_source']={'preset_id':working.get('id',''),'parameters':row['pid']}
        staged.append((old,record))
    result=[]
    for old,record in staged:
        if old is None:data.setdefault('texts',[]).append(record);result.append(record)
        else:old.clear();old.update(record);result.append(old)
    return result
