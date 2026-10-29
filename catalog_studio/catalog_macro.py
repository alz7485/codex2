"""Conservative CATE / SDTE / TEXT / SCOM creation macros; never execute commands."""
import copy
import re
from . import project,catalogue,catalog_workspace as workspace,macro_destinations


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
    # Application description/revision are not assumed to be E3D attributes.
    for r in data['texts']:
        if r['parent_id']!=cate_id:continue
        if r['type'] not in ('SDTE','TEXT'):raise ValueError('このCATEには未対応の文字要素があります。')
        lines+=['NEW '+r['type']+' '+name(r['name'])]
        for key,value in r['attrs'].items():
            if key not in catalogue.TEXT_TYPES[r['type']]:raise ValueError('未対応の属性：'+key)
            if value:lines.append(key+' '+quote(value))
        lines.append('END')
    for r in data['scoms']:
        if r['cate_id']!=cate_id:continue
        if r.get('size') or any(r.get(k) for k in ('ngmset_id','gmsset_id','ptsset_id')):raise ValueError('SIZE・構造材参照の出力構文は未確認です。')
        if r.get('attrs'):raise ValueError('SCOMの追加属性の出力構文は未確認です。')
        lines+=['NEW SCOM '+name(r['name'])]
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
                if not target:raise ValueError('参照先が見つかりません：'+attr)
                lines.append(attr+' '+name(target['name']))
        lines.append('END')
    lines.append('END')
    return '\n'.join(lines)+'\n'


def import_text(data,text):
    candidate=copy.deepcopy(data);stack=[];created=[]
    aliases={'CATEGORY':'CATE','SDTEXT':'SDTE','SCOMPONENT':'SCOM'}
    for number,line in enumerate(text.splitlines(),1):
        line=line.strip()
        if not line or line.startswith('$*'):continue
        try:
            if line.upper() in ('INPUT BEGIN','INPUT FINISH') or line.upper().startswith('INPUT END '):continue
            if line=='END':
                if not stack:raise ValueError('ENDに対応する要素がありません。')
                stack.pop();continue
            if line.startswith('/') and not stack:name(line);continue
            words=line.split(None,2);command=words[0].upper()
            if command=='NEW':
                if len(words)!=3:raise ValueError('NEWには種類と名前が必要です。')
                kind=aliases.get(words[1].upper(),words[1].upper());n=name(words[2]);workspace.check_name(candidate,n)
                if kind=='CATE' and not stack:r=project.add_cate(candidate,n);created.append(r['id'])
                elif stack and stack[-1][0]=='CATE' and kind in ('SDTE','TEXT','SCOM'):
                    owner=stack[-1][1]['id']
                    r=project.add_scom(candidate,owner,n) if kind=='SCOM' else catalogue.add_record(candidate,'texts',kind,n,owner)
                    if kind=='SCOM':r.update(gmset_id='',ptset_id='')
                else:raise ValueError('対応するCATE配下のSDTE・TEXT・SCOMを指定してください。')
                stack.append((kind,r));continue
            if not stack:raise ValueError('作成対象が選択されていません。')
            kind,r=stack[-1];value=line[len(words[0]):].strip()
            if kind in ('SDTE','TEXT') and command in catalogue.TEXT_TYPES[kind]:
                if len(value)<2 or value[0]!="'" or value[-1]!="'":raise ValueError('文字列を単引用符で囲んでください。')
                r['attrs'][command]=value[1:-1];quote(r['attrs'][command])
            elif kind=='SCOM' and command in ('PARA','PARAM'):
                tokens=re.findall(r"'[^']*'|[^\s]+",value);r['values']={}
                for i,token in enumerate(tokens,1):
                    r['values']['P'+str(i)]=token[1:-1] if token.startswith("'") else float(token)
            elif kind=='SCOM' and command=='ANGL':r.setdefault('component_attrs',{})['ANGL']=float(value)
            elif kind=='SCOM' and command in ('GMRE','PTRE','NGMSET','GMSSET','PTSSET'):
                target=next((d for d in candidate['definitions'] if d['name']==value),None)
                expected={'GMRE':'GMSET','PTRE':'PTSET'}.get(command,command)
                if not target or target['kind']!=expected:raise ValueError('参照先を先に読み込んでください：'+value)
                r[{'GMRE':'gmset_id','PTRE':'ptset_id'}.get(command,command.lower()+'_id')]=target['id']
            else:raise ValueError('未対応の命令・属性：'+command)
        except ValueError as exc:raise ValueError(f'{number}行目：{exc}') from exc
    if stack:raise ValueError('ENDが不足しています。')
    if not created:raise ValueError('CATEがありません。')
    project.validate(candidate)
    return candidate,created
