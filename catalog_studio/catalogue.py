"""Editable companion data and validation of catalogue definitions."""
import math
import re
import uuid
from . import element_schema as schema, expressions

TEXT_TYPES = {'SDTE': ('RTEX','STEX','TTEX','SKEY'), 'SMTE': ('XTEX','YTEX','ZTEX')}
TABLE_TYPES = {
    'CATA': (), 'SECT': (), 'CCTA': (), 'COCO': ('CTYPE',), 'COCDES': ('DESC','COCONNECTION'),
    'BTSE': (), 'BLTP': ('NUMBER','BDIA','BTHK','BTYPE'),
    'BLTAB': (), 'BLIST': (), 'SBOLT': ('NSTD','BITEM','BITL'), 'LTAB': (), 'DTAB': ('BLEN',),
    'TABWLD': (), 'NOMTAB': (), 'SNOTAB': (), 'SSNOTA': (),
    'BRTAB': ('PURP',), 'SRTAB': (), 'SBRTAB': (), 'SSBRTA': (), 'SSSBRT': (),
}
PARENTS = {'CATA':(), 'SECT':('CATA',), 'CCTA':(), 'COCO':('CCTA',),'COCDES':('CCTA',),
           'BTSE':('SECT',), 'BLTP':('BTSE',), 'BLTAB':(), 'BLIST':('BLTAB',), 'SBOLT':('BLIST',),
           'LTAB':('BLTAB',), 'DTAB':('LTAB',), 'TABWLD':(), 'NOMTAB':('TABWLD',), 'BRTAB':('TABWLD',),
           'SDTE':('CATE','SECT'), 'SMTE':('CATE','SECT')}

MEANINGS = {'CTYPE':'接続コードの組（2 コード）', 'COCONNECTION':'接続コードとの関連（原文保持）',
            'NUMBER':'ボルト穴の番号', 'BDIA':'ボルト直径', 'BTHK':'ボルト長さ', 'BTYPE':'ボルト種別',
            'NSTD':'標準長さ表の参照', 'BITEM':'長さ計算に加える付属品', 'BITL':'付属品の長さ',
            'BLEN':'標準ボルト長さの配列', 'RTEX':'ISODRAFT 説明', 'STEX':'詳細用テキスト',
            'TTEX':'詳細用テキスト', 'SKEY':'4 文字のシンボルキー', 'XTEX':'ISODRAFT 材質',
            'YTEX':'材質テキスト', 'ZTEX':'材質テキスト'}


def add_record(data, collection, kind, name, parent_id=''):
    allowed = TEXT_TYPES if collection == 'texts' else TABLE_TYPES
    if kind not in allowed: raise ValueError('作成する種類を選択してください。')
    records = data.setdefault(collection, [])
    if len(records) >= 5000: raise ValueError('管理レコードの上限です。')
    if not name.strip() or any(r['name'] == name for r in records): raise ValueError('名前が空か重複しています。')
    item = {'id':uuid.uuid4().hex, 'type':kind, 'name':name, 'parent_id':parent_id,
            'revision':'01', 'attrs':{k:'' for k in allowed[kind]}}
    records.append(item); return item


def definition_issues(definition, parameters=(), scom=None):
    result = []; numbers = set()
    allowed=schema.TYPES_BY_SET[definition['kind']]
    for element in definition['elements']:
        if schema.known(element['type']) and element['type'] not in allowed and not (definition['kind']=='GMSET' and element['type'] in schema.NEGATIVE_BASE):
            result.append(definition['name']+'：'+element['type']+' はこのセットの直接の子要素ではありません。')
    elements = list(schema.walk(definition['elements']))
    def report(element, key, message): result.append(definition['name'] + ' / ' + element['name'] + ' / ' + key + '：' + message)
    for element in elements:
        kind = element['type']; attrs = element['attrs']; base = schema.positive(kind)
        if not schema.known(kind): continue
        if not schema.child_kind(kind) and element.get('children'): report(element,'子要素','この要素型は子要素を持ちません。')
        if kind in schema.PT_TYPES:
            number = str(attrs.get('NUMB',''))
            if not re.fullmatch(r'[1-9]\d*',number): report(element,'NUMB','正の整数。P0 は自動生成される編集不可の基準点です。')
            elif number in numbers: report(element,'NUMB','ポイント番号が重複しています。')
            numbers.add(number)
        for flag in ('CLFLA','TUFLA','TVISI','BVISI'):
            value = str(attrs.get(flag,'')).strip()
            if value and value.upper() not in ('TRUE','FALSE','UNSET'): report(element,flag,'TRUE / FALSE を指定してください。')
        if str(attrs.get('OBST','')) not in ('','0','1','2','unset'): report(element,'OBST','0 / 1 / 2 を指定してください。')
        level = str(attrs.get('LEVEL','')).strip()
        if level and level.lower() != 'unset':
            try:
                pair = [float(v) for v in level.split()]
                if len(pair) != 2 or not all(math.isfinite(v) for v in pair) or pair[0] > pair[1]: raise ValueError()
            except ValueError: report(element,'LEVEL','下限 上限 の 2 数値を昇順で入力してください。')
        if kind in schema.NEGATIVE_BASE and str(attrs.get('NAPP','')).strip() not in tuple(map(str,range(8))): report(element,'NAPP','0〜7 の適用先の組み合わせです。')
        if base == 'LINE' and attrs.get('PTS'):
            points = str(attrs['PTS']).upper().split()
            if not 1 <= len(points) <= 6 or any(not re.fullmatch(r'[PT]\d+', v) for v in points): report(element,'PTS','P1 / T2 形式の点を順に最大 6 個指定します。')
        if base == 'LSNO':
            for diameter,radius in (('PTDM','PTRA'),('PBDM','PBRA')):
                if str(attrs.get(diameter,'')).strip() and str(attrs.get(radius,'')).strip(): report(element,diameter,'同じ面の直径と半径が両方設定されています。入力モードを選択してください。')
        if base in ('SEXT','SREV','SPRO','SLOO'):
            children = element.get('children',[]); expected = schema.child_kind(kind)
            if not children: report(element,'輪郭','輪郭または頂点がありません。')
            elif any(c['type'] != expected for c in children): report(element,'輪郭','子要素の種類は ' + expected + ' です。')
            if base in ('SLOO','SPRO') and len(children) < 3: report(element,'輪郭','輪郭には 3 点以上の頂点が必要です。')
        numeric_keys = set(schema.fields(kind)) - {'NUMB','PCON','PKEY','PAXI','PAAX','PBAX','PCAX','PLAXI','PTCDIR','PTCPOS','PTSPOS','PTEPOS','TVISI','BVISI','PTS'}
        for key in numeric_keys:
            expr = str(attrs.get(key,''))
            if not expr.strip() or expr.lower() == 'unset': continue
            try:
                root = expressions.parse(expr,parameters)
                for family,pid in expressions.refs(root):
                    if family == 'PARAM' and pid not in {p['id'] for p in parameters}: raise ValueError('未定義のパラメータ：' + pid)
                if scom is not None or not expressions.refs(root):
                    contexts = expressions.contexts_for(scom) if scom else {}
                    value = expressions.evaluate(expr,contexts,(scom or {}).get('component_attrs',{}),parameters)
                    if type(value) not in (int,float): raise ValueError('寸法・角度には数値が必要です。')
                    if key == 'PANGLE' and not -360 <= value <= 360: raise ValueError('回転角度は −360〜360 度です。')
                    if key == 'PANG' and not -180 <= value <= 180: raise ValueError('円環角度は −180〜180 度です。')
            except ValueError as exc: report(element,key,str(exc))
    if definition['kind'] == 'GMSSET' and sum(str(e['attrs'].get('OBST','')) in ('1','2') for e in definition['elements']) > 20:
        result.append(definition['name'] + '：OBST 1 / 2 の断面要素は 20 個以内にしてください（資料に基づく上限）。')
    if definition['kind'] == 'PTSSET':
        target = definition.get('attrs',{}).get('NAREF','')
        if target not in {e['id'] for e in definition['elements']} | {e['name'] for e in definition['elements']}:
            result.append(definition['name'] + '：中立軸 NAREF の PLINE を選択してください。')
    return result


def companion_issues(data):
    result = []
    cates = {c['id'] for c in data['cates']}
    tables = {r['id']:r for r in data.get('tables',[])}
    for text in data.get('texts',[]):
        if text['parent_id'] not in cates and tables.get(text['parent_id'],{}).get('type') != 'SECT': result.append(text['name'] + '：所属 CATE / SECT が見つかりません。')
        skey = text['attrs'].get('SKEY','')
        if skey and len(str(skey)) != 4: result.append(text['name'] + '：SKEY は 4 文字です。')
        if text.get('isodraft') and text['type'] == 'SDTE' and (not text['attrs'].get('RTEX') or not skey): result.append(text['name'] + '：ISODRAFT 用には RTEX と SKEY を設定してください。')
    for record in tables.values():
        parent = record.get('parent_id','')
        if parent and parent not in tables and parent not in cates: result.append(record['name'] + '：親レコードが見つかりません。')
        allowed=PARENTS.get(record['type'])
        if allowed is not None:
            parent_type='CATE' if parent in cates else tables.get(parent,{}).get('type')
            if allowed and parent_type not in allowed: result.append(record['name']+'：親の種類は '+ ' / '.join(allowed)+' です。')
            if not allowed and parent:result.append(record['name']+'：WORLD の直下に配置してください。')
        seen = {record['id']}; current = parent
        while current in tables:
            if current in seen: result.append(record['name'] + '：階層が循環しています。'); break
            seen.add(current); current = tables[current].get('parent_id','')
        if record['type'] == 'COCO' and len(str(record['attrs'].get('CTYPE','')).split()) != 2: result.append(record['name'] + '：CTYPE は 2 つの接続コードです。')
    return result
