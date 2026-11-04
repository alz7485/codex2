"""Transactional SCOM sheet edits and bounded Excel reads; never run formulas."""
import copy
import re
from . import project,presets,catalog_workspace as workspace

FIXED=('NAME','GTYP','PTRE','GMRE','SIZE')

def columns(data,cate_id,seed):
    records=[seed] if seed else []
    records += [s for s in data['scoms'] if s['cate_id']==cate_id]
    ids={p['id'] for r in records or [None] for p in presets.rules(data,r)}
    return list(FIXED)+sorted(ids,key=lambda p:int(p[1:]))

def row(data,scom):
    result={'id':scom['id'],'NAME':scom['name'],'GTYP':scom.get('attrs',{}).get('GTYP',''),'SIZE':scom.get('size','')}
    for attr,key in (('PTRE','ptset_id'),('GMRE','gmset_id')):
        target=project.get(data,'definitions',scom.get(key));result[attr]=target['name'] if target else scom.get(key,'')
    result.update({k:str(v) for k,v in scom['values'].items()});return result

def apply(data,cate_id,rows,seed_id=None,preset_id=None):
    if not project.get(data,'cates',cate_id):raise ValueError('CATEを選択してください。')
    if not rows or len(rows)>5000:raise ValueError('表は1〜5000行で指定してください。')
    candidate=copy.deepcopy(data);seed=project.get(candidate,'scoms',seed_id);seen=set();ids=[]
    for number,raw in enumerate(rows,1):
        try:
            ident=raw.get('id');old=project.get(candidate,'scoms',ident)
            if ident and (not old or old['cate_id']!=cate_id):raise ValueError('元のSCOMが変更されています。')
            if ident in seen:raise ValueError('同じSCOMが複数行にあります。')
            if ident:seen.add(ident)
            name=str(raw.get('NAME','')).strip()
            if not name.startswith('/'):name='/'+name if name else ''
            if name=='/':raise ValueError('SCOM名を入力してください。')
            workspace.check_name(candidate,name,exclude=old)
            if old:target=old
            else:
                target=project.add_scom(candidate,cate_id,name)
                if seed:
                    for key in ('ptset_id','gmset_id','parameter_preset_id'):target[key]=seed.get(key,'')
            if preset_id is not None:target['parameter_preset_id']=preset_id
            target['name']=name;target['size']=str(raw.get('SIZE',''))
            gtyp=str(raw.get('GTYP','')).strip()
            if gtyp and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*',gtyp):raise ValueError('GTYPはwordで入力してください。')
            if gtyp:target.setdefault('attrs',{})['GTYP']=gtyp
            else:target.setdefault('attrs',{}).pop('GTYP',None)
            for attr,key,kind in (('PTRE','ptset_id','PTSET'),('GMRE','gmset_id','GMSET')):
                value=str(raw.get(attr,'')).strip()
                definition=next((d for d in candidate['definitions'] if value in (d['id'],d['name'])),None)
                if value and not definition and old and value==old.get(key) and value.startswith('/'):continue
                if value and (not definition or definition['kind']!=kind):raise ValueError(attr+'の参照先が見つかりません。')
                if definition:presets.require_compatible(candidate,target,definition)
                target[key]=definition['id'] if definition else ''
            rules={p['id']:p for p in presets.rules(candidate,target)}
            values={}
            for pid in set(rules)|set(target['values']):
                value=raw.get(pid,'')
                if value!='' and value is not None:values[pid]=project.parse_value(rules[pid],str(value)) if pid in rules else target['values'][pid]
            for pid,value in raw.items():
                if re.fullmatch(r'P\d+',pid) and pid not in rules and str(value).strip():raise ValueError(pid+'はこの行のPARAMプリセットにありません。')
            target['values']=values;ids.append(target['id'])
        except (ValueError,KeyError) as exc:raise ValueError(f'{number}行目：{exc}') from exc
    project.validate(candidate);return candidate,ids

def open_excel(path):
    from openpyxl import load_workbook
    from zipfile import BadZipFile
    from openpyxl.utils.exceptions import InvalidFileException
    try:return load_workbook(path,read_only=True,data_only=False,keep_links=False)
    except (BadZipFile,InvalidFileException) as exc:raise ValueError('有効な.xlsx/.xlsmファイルを選択してください。') from exc


def sheet_names(path):
    book=open_excel(path)
    try:return list(book.sheetnames)
    finally:book.close()


def read_excel(path,sheet=None,aliases=None):
    book=open_excel(path)
    try:
        ws=book[sheet] if sheet else book.worksheets[0]
        if ws.max_row>5001 or ws.max_column>110:raise ValueError('Excelは見出し＋5000行・110列以内にしてください。')
        iterator=ws.iter_rows();header=next(iterator,None)
        if not header:raise ValueError('Excelが空です。')
        keys=[]
        for c in header:
            value=str(c.value or '').strip();value=(aliases or {}).get(value,{'名前':'NAME','SCOM名':'NAME','SCOM':'NAME','サイズ':'SIZE'}.get(value,value.upper()))
            value=re.sub(r'^(?:PARAM|PARA|PA)\s*(\d+)$',r'P\1',value)
            if value and value not in FIXED and not re.fullmatch(r'P[1-9]\d*',value):raise ValueError('未対応の見出し：'+value)
            keys.append(value)
        used=[k for k in keys if k]
        if 'NAME' not in used or len(set(used))!=len(used):raise ValueError('NAME列が必要です。見出しの重複はできません。')
        result=[]
        for number,cells in enumerate(iterator,2):
            if all(c.value is None for c in cells):continue
            if any(c.data_type in ('f','e') for c in cells):raise ValueError(f'Excel {number}行目：数式・エラー値は値に変換してください。')
            if any(c.value is not None and not keys[i] for i,c in enumerate(cells)):raise ValueError(f'Excel {number}行目：見出しのない列に値があります。')
            result.append({key:('' if cell.value is None else cell.value) for key,cell in zip(keys,cells) if key})
        return result,book.sheetnames
    finally:book.close()


def text_columns(data,cate_id,preset_id,create=False):
    from . import catalogue
    working=copy.deepcopy(data);rules=presets.rules(working,{'parameter_preset_id':preset_id})
    cate=project.get(working,'cates',cate_id);labels={'NAME':'名前'}
    if not cate:raise ValueError('CATEを選択してください。')
    for p in rules:
        matches=[r for r in working['texts'] if r['type']=='TEXT' and r['parent_id']==cate_id and r.get('parameter_text_source',{}).get('preset_id')==preset_id and r.get('parameter_text_source',{}).get('parameters')==p['id']]
        if len(matches)>1:raise ValueError(p['id']+'に対応するTEXTが複数あります。')
        if matches:
            labels[p['id']]=matches[0]['attrs'].get('STEXT','').strip() or 'PA'+p['id'][1:]+'（STEXT未設定）'
            continue
        name=cate['name'].rstrip('/')+'/PARAM'+p['id'][1:];base=name
        if len(base)>990:raise ValueError('CATE名が長すぎるためTEXT名を生成できません。')
        for number in range(2,5003):
            try:workspace.check_name(working,name);break
            except ValueError:name=base+'-'+str(number)
        else:raise ValueError('重複しないTEXT名を生成できません。')
        labels[p['id']]=(p.get('english_name','').strip() or 'PA'+p['id'][1:]+'（STEXT未設定）') if create else 'PA'+p['id'][1:]+'（TEXT未作成）'
        if create:
            record=catalogue.add_record(working,'texts','TEXT',name,cate_id)
            record['attrs']['STEXT']=p.get('english_name','')
            record['parameter_text_source']={'preset_id':preset_id,'parameters':p['id']}
    counts={v:list(labels.values()).count(v) for v in labels.values()}
    labels={k:(v+'（PA'+k[1:]+'）' if k!='NAME' and counts[v]>1 else v) for k,v in labels.items()}
    return working,labels
