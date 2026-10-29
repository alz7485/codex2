"""Read observed ALP catalogue declarations without executing any command."""
import copy
import math
import re
import uuid
from . import project, catalogue, catalog_workspace as workspace, presets

ALIASES={'CATEGORY':'CATE','SDTEXT':'SDTE','SCOMPONENT':'SCOM','CMPTYPE':'CMPTYPE','CMPDATA':'CMPDATA',
         'CATE':'CATE','SDTE':'SDTE','TEXT':'TEXT','SCOM':'SCOM'}
REFS={'GMRE':('gmset_id','GMSET'),'PTRE':('ptset_id','PTSET')}
NUMBER=re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?\Z')
WORD=re.compile(r'[A-Za-z][A-Za-z0-9_.-]*\Z')


def statements(text):
    if not isinstance(text,str) or '\x00' in text or len(text.encode('utf-8'))>8*1024*1024:
        raise ValueError('読込テキストは8 MB以内・NULなしで指定してください。')
    pending='';start=0
    for number,line in enumerate(text.removeprefix('\ufeff').splitlines(),1):
        line=line.strip()
        if not line or line.startswith('$*'):continue
        if not pending:start=number
        # Only a terminal dollar outside quoted strings is a continuation.
        continued=line.endswith('$') and line[:-1].count("'")%2==0
        pending+=(' ' if pending else '')+(line[:-1].rstrip() if continued else line)
        if not continued:
            yield start,pending
            pending=''
    if pending:raise ValueError(f'{start}行目：継続行が完了していません。')


def tokens(value):
    result=[];pos=0
    for match in re.finditer(r"'[^']*'|[^\s']+",value):
        if value[pos:match.start()].strip():raise ValueError('引用符または値の区切りが不正です。')
        token=match[0]
        if result and pos==match.start():raise ValueError('値を空白で区切ってください。')
        result.append(token);pos=match.end()
    if value[pos:].strip():raise ValueError('引用符が閉じていません。')
    return result


def scalar(token):
    if token.startswith("'"):return token[1:-1]
    if NUMBER.fullmatch(token):
        value=float(token)
        if not math.isfinite(value):raise ValueError('有限の数値を指定してください。')
        return value
    if WORD.fullmatch(token):return token
    raise ValueError('未対応のPARAM値：'+token)


def element_name(value):
    if not value.startswith('/') or len(value)>1000 or any(c in value for c in '\r\n\x00\t'):
        raise ValueError('名前は / で始まる1行で指定してください。')
    return value


def import_text(data,text,cate_id=''):
    candidate=copy.deepcopy(data);stack=[];current=None;roots=[];created={};block=None;finished=False
    imported_scoms=[];derived={}
    def register(kind,record,collection):
        key=record['name'].casefold()
        if key in created:raise ValueError('作成名が重複しています。')
        created[key]=(kind,record)
        return kind,record
    for number,line in statements(text):
        try:
            words=line.split(None,2);command=words[0].upper()
            if finished:raise ValueError('INPUT FINISH後に命令があります。')
            if command=='INPUT':
                action=words[1].upper() if len(words)>1 else ''
                if action=='BEGIN' and len(words)==2:
                    if block is not None or stack:raise ValueError('INPUT BEGINが重複しています。')
                    block=[];current=None
                elif action=='END' and len(words)==3:
                    if block is None or stack:raise ValueError('INPUT ENDの前に作成階層を閉じてください。')
                    spec=words[2].split(None,1)
                    if len(spec)!=2 or len(block)!=1 or block[0]!=(ALIASES.get(spec[0].upper()),spec[1].casefold()):
                        raise ValueError('INPUT ENDの種類・名前が作成ルートと一致しません。')
                    block=None;current=None
                elif action=='FINISH' and len(words)==2:
                    if block is not None or stack:raise ValueError('INPUT ENDまたはENDが不足しています。')
                    finished=True
                else:raise ValueError('未対応のINPUT構文です。')
                continue
            if command=='END':
                if len(words)!=1 or not stack:raise ValueError('ENDに対応する作成階層がありません。')
                stack.pop();current=stack[-1] if stack else None;continue
            if command=='NEW':
                if len(words)!=3:raise ValueError('NEWには種類と名前が必要です。')
                kind=ALIASES.get(words[1].upper());n=element_name(words[2]);workspace.check_name(candidate,n)
                if n.casefold() in created:raise ValueError('名前が重複しています。')
                parent=stack[-1] if stack else None
                if not parent:
                    if kind=='CATE':r=project.add_cate(candidate,n);collection='cates'
                    elif kind in ('CMPTYPE','SDTE'):
                        collection='catalog_props' if kind=='CMPTYPE' else 'catalog_details'
                        r={'id':uuid.uuid4().hex,'name':n,'cate_id':cate_id,'revision':'01','description':'','attrs':{},'e3d_type':kind}
                        if kind=='CMPTYPE':r['children']=[]
                        else:r['sdte_id']=''
                        candidate.setdefault(collection,[]).append(r)
                    else:raise ValueError('ルートにはCATE・SDTEXT・CMPTYPEを指定してください。')
                    roots.append(r['id'])
                    if block is not None:block.append((kind,n.casefold()))
                elif parent[0]=='CATE' and kind in ('SDTE','TEXT','SCOM'):
                    if kind=='SCOM':
                        collection='scoms';r=project.add_scom(candidate,parent[1]['id'],n)
                        r.update(gmset_id='',ptset_id='');r['parameter_preset_id']='';imported_scoms.append(r)
                    else:collection='texts';r=catalogue.add_record(candidate,collection,kind,n,parent[1]['id'])
                elif parent[0]=='CMPTYPE' and kind=='CMPDATA':
                    r={'id':uuid.uuid4().hex,'name':n,'type':'CMPDATA','attrs':{}}
                    parent[1]['children'].append(r);collection='cmpdata'
                else:raise ValueError('この親の下には作成できない種類です。')
                current=register(kind,r,collection);stack.append(current);continue
            if command=='OLD':
                if len(words)!=3:raise ValueError('OLDには種類と名前が必要です。')
                found=created.get(words[2].casefold())
                if not found or found[0]!=ALIASES.get(words[1].upper()):raise ValueError('OLDはこのファイルで作成した同じ種類の要素だけ選択できます。')
                current=found;continue
            if command=='LOCK':
                if len(words)!=1 or current is None:raise ValueError('LOCKの対象がありません。')
                current[1]['macro_locked']=True;continue
            if command.startswith('/'):
                element_name(line)
                if stack:raise ValueError('作成階層の途中では外部要素を選択できません。')
                current=created.get(line.casefold());continue
            if current is None:raise ValueError('属性の設定対象がありません。')
            kind,r=current;value=line[len(words[0]):].strip()
            if kind in ('SDTE','TEXT') and command in (*catalogue.TEXT_TYPES[kind],'STEX'):
                parsed=tokens(value)
                if len(parsed)!=1 or not parsed[0].startswith("'"):raise ValueError('テキスト値を単引用符で囲んでください。')
                r['attrs']['STEXT' if kind=='TEXT' and command=='STEX' else command]=parsed[0][1:-1]
            elif kind=='CATE' and command in ('PURP','GTYP') or kind=='SCOM' and command=='GTYP':
                if not WORD.fullmatch(value):raise ValueError('属性をwordで指定してください。')
                r.setdefault('attrs',{})[command]=value
            elif kind=='SCOM' and command in ('PARA','PARAM'):
                values=tokens(value)
                if not values or len(values)>project.LIMITS['parameters']:raise ValueError('PARAMの件数を確認してください。')
                r['values']={'P'+str(i):scalar(token) for i,token in enumerate(values,1)}
            elif kind=='SCOM' and command=='ANGL':
                v=scalar(value)
                if not isinstance(v,float):raise ValueError('ANGLは数値です。')
                r.setdefault('component_attrs',{})['ANGL']=v
            elif kind=='SCOM' and command in REFS:
                key,expected=REFS[command];ref=value.split(None,1)
                if not value.startswith('/') and len(ref)==2:
                    if ref[0].upper()!=expected:raise ValueError('参照先の種類が一致しません。')
                    value=ref[1]
                n=element_name(value)
                target=next((d for d in candidate['definitions'] if d['name'].casefold()==n.casefold()),None)
                if target and target['kind']!=expected:raise ValueError('参照先の種類が不正です。')
                r[key]=target['id'] if target else n
            elif kind=='CMPDATA' and command=='CWEI':
                if not (value.startswith('(') and value.endswith(')')):raise ValueError('CWEIの括弧付き数値を指定してください。')
                v=scalar(value[1:-1].strip())
                if not isinstance(v,float):raise ValueError('CWEIは有限数値です。')
                r['attrs']['CWEI']=v
            else:raise ValueError('未対応の命令・属性：'+command)
        except ValueError as exc:raise ValueError(f'{number}行目：{exc}') from exc
    if stack or block is not None:raise ValueError('ENDまたはINPUT ENDが不足しています。')
    if not roots:raise ValueError('CATE・SDTEXT・CMPTYPEがありません。')
    # Imported numbers/words do not acquire the unrelated active preset's meanings or units.
    for r in imported_scoms:
        signature=tuple('word' if isinstance(v,str) else 'number' for v in r['values'].values())
        if signature:
            if signature not in derived:
                base='マクロ読込PARAM';number=1
                while any(p['name']==f'{base}({number})' for p in candidate.get('parameter_presets',[])):number+=1
                p=presets.add(candidate,f'{base}({number})',empty=True)
                p['parameters']=[{'id':'P'+str(i),'role':'PARAM'+str(i),'unit':'','value_type':t} for i,t in enumerate(signature,1)]
                derived[signature]=p['id']
            r['parameter_preset_id']=derived[signature]
    project.validate(candidate)
    return candidate,roots
