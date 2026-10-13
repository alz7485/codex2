"""Catalogue editing rules; unverified syntax and original extra fields remain intact."""
import copy
import uuid

PT_COMMON = ('NUMB', 'PCON', 'PBOR')
PT_DETAIL = ('PSKEY', 'DESC', 'PURP')
PT_TYPES = {
    'PTAXI': ('PAXI', 'PDIS'),
    'PTCAR': ('PX', 'PY', 'PZ', 'PTCDIR'),
    'PTMIX': ('PX', 'PY', 'PZ', 'PAXI'),
    'PTPOS': ('PTCPOS', 'PTCDIR'),
}
PT_GUIDES = {
    'PTAXI': {'name':'軸と距離で定義する点', 'position':'位置：PAXI の軸に沿う距離を PDIS で指定します。', 'direction':'方向：PAXI の軸方向を使います。', 'usage':'軸上の接続点や基準点を作るときに選びます。'},
    'PTCAR': {'name':'XYZ 座標と方向式で定義する点', 'position':'位置：PX・PY・PZ を個別に指定します。', 'direction':'方向：PTCDIR の方向式で指定します。', 'usage':'位置と向きをそれぞれ明示したいときに選びます。'},
    'PTMIX': {'name':'XYZ 座標と軸で定義する点', 'position':'位置：PX・PY・PZ を個別に指定します。', 'direction':'方向：PAXI の軸指定を使います。', 'usage':'座標で置き、向きは軸で指定したいときに選びます。'},
    'PTPOS': {'name':'位置式と方向式で定義する点', 'position':'位置：PTCPOS に位置式を指定します。', 'direction':'方向：PTCDIR（PTCD と同じ）の方向式を指定します。', 'usage':'位置を一つの位置式で表したいときに選びます。'},
}
GM_TYPES = {
    'SBOX': ('PXLE', 'PYLE', 'PZLE', 'PX', 'PY', 'PZ'),
    'BOXI': ('PXLE', 'PZLE', 'PAXI', 'TVISI', 'BVISI'),
    'SCON': ('PAXI', 'PDIS', 'PDIA'),
    'LCYL': ('PAXI', 'PDIA', 'PBDI', 'PTDI', 'TVISI', 'BVISI'),
    'SCYL': ('PAXI', 'PHEI', 'PDIA', 'PDIS', 'TVISI', 'BVISI'),
    'SSLC': ('PAXI', 'PHEI', 'PDIA', 'PXTS', 'PYTS', 'PXBS', 'PYBS', 'PDIS', 'TVISI', 'BVISI'),
    'SDIS': ('PAXI', 'PDIS', 'PDIA'),
    'SDSH': ('PAXI', 'PDIS', 'PDIA', 'PHEI', 'PRAD'),
    'SLINE': ('PTSPOS', 'PTEPOS'),
    'LINE': ('PTS',),
    'LPYR': ('PAAX', 'PBAX', 'PCAX', 'PBTP', 'PCTP', 'PBBT', 'PCBT', 'PBOF', 'PCOF', 'PTDI', 'PBDI', 'TVISI', 'BVISI'),
    'SCTO': ('PAAX', 'PBAX', 'PDIA', 'TVISI', 'BVISI'),
    'SRTO': ('PAAX', 'PBAX', 'PDIA', 'PHEI', 'TVISI', 'BVISI'),
    'LSNO': ('PAAX', 'PBAX', 'PTDI', 'PBDI', 'PTDM', 'PBDM', 'POFF', 'TVISI', 'BVISI', 'PTRA', 'PBRA'),
    'SSPH': ('PAXI', 'PDIS', 'PDIA'),
    'TUBE': ('PDIAM', 'TVISI', 'BVISI'),
    'SEXT': ('PX', 'PY', 'PZ', 'PAAX', 'PBAX', 'PHEI'),
    'SREV': ('PX', 'PY', 'PZ', 'PAAX', 'PBAX', 'PANGLE'),
}
GM_COMMON = ('LEVEL', 'CLFLA', 'TUFLA', 'OBST', 'DESC', 'GTYP', 'PURP')
NEGATIVE_EXTRA = ('NAPP',)
# UI working correspondence only; no executable command is generated from it.
NEGATIVE_BASE = {
    'NSBO': 'SBOX', 'NBOX': 'BOXI', 'NSCO': 'SCON', 'NLCY': 'LCYL',
    'NSCY': 'SCYL', 'NSSL': 'SSLC', 'NLPY': 'LPYR', 'NSCT': 'SCTO',
    'NSRT': 'SRTO', 'NLSN': 'LSNO', 'NSSP': 'SSPH', 'NTUB': 'TUBE',
    'NSEX': 'SEXT', 'NSRE': 'SREV', 'NSRU': None,
}
REFERENCE_TYPES = ('PARAM', 'IPARAM', 'APARAM', 'OPARAM', 'DES PARAM', 'DES APARAM', 'DES OPARAM')
REFERENCE_LABELS = {
    'PARAM': 'Parameter', 'IPARAM': 'Insulation', 'APARAM': 'Attached', 'OPARAM': 'Owning',
    'DES PARAM': 'Design', 'DES APARAM': 'Design Attached', 'DES OPARAM': 'Design Owning',
}
DESCRIPTIONS = {
    'NUMB': 'ポイント番号', 'PCON': '接続形式', 'PBOR': '接続口径',
    'PAXI': '軸方向', 'PDIS': '軸上の距離', 'PX': 'X 座標', 'PY': 'Y 座標', 'PZ': 'Z 座標',
    'PTCPOS': '位置式', 'PTCDIR': '方向式', 'TVISI': '上面の表示', 'BVISI': '下面の表示',
    'OBST': '干渉チェック', 'DESC': '説明', 'PURP': '用途', 'PSKEY': '通常非表示',
}
OBST_CHOICES = {'未設定': '', '0：対象外': '0', '1：ソフト': '1', '2：ハード': '2'}
DIRECTIONS = ('X', '-X', 'Y', '-Y', 'Z', '-Z', 'E', 'W', 'U', 'D')


PARENT_FIELDS = {'PTSET': ('DESC', 'GTYP', 'SKEY', 'PURP'), 'GMSET': (), 'NGMSET': (),
                 'PTSSET': ('NAREF',), 'GMSSET': ()}
STRUCTURAL_TYPES = {
    'PLINE': ('PKEY', 'PX', 'PY', 'PLAXI'),
    'SREC': ('PXLE', 'PYLE', 'DXLE', 'DYLE', 'PX', 'PY', 'DX', 'DY', 'PLAXI'),
    'SANN': ('PX', 'PY', 'DX', 'DY', 'PRAD', 'DRAD', 'PWID', 'DWID', 'PANG', 'PLAXI'),
    'SPRO': ('PLAXI',),
}
CHILD_TYPES = {'SLOO': (), 'SVER': ('PX', 'PY', 'PRAD'),
               'SPVE': ('PX', 'PY', 'DX', 'DY', 'PRAD', 'DRAD')}
TYPES_BY_SET = {'PTSET': PT_TYPES, 'GMSET': GM_TYPES, 'NGMSET': NEGATIVE_BASE,
                'PTSSET': {'PLINE': STRUCTURAL_TYPES['PLINE']},
                'GMSSET': {k: STRUCTURAL_TYPES[k] for k in ('SREC','SANN','SPRO')}}
LABELS = dict(zip(GM_TYPES, ('箱', '矩形の暗黙チューブ', '円錐', '円筒：両端位置', '円筒：底面＋高さ',
                            '傾斜端面円筒', '円板：厚さゼロ', '皿形', '始終点の線', '点を結ぶ線',
                            '矩形レデューサー', '円形断面トーラス', '矩形断面トーラス', '円形レデューサー',
                            '球', '円形の暗黙チューブ', '輪郭の押出し', '輪郭の回転')))
LABELS.update(PTAXI='軸＋距離の点', PTCAR='XYZ＋方向式の点', PTMIX='XYZ＋軸の点',
              PTPOS='位置式＋方向式の点', PLINE='構造材の基準線', SREC='矩形断面',
              SANN='円環断面', SPRO='任意断面', SLOO='輪郭', SVER='輪郭の頂点', SPVE='断面の頂点')
DESCRIPTIONS.update({
    'PXLE':'X 方向の寸法', 'PYLE':'Y 方向の寸法', 'PZLE':'Z 方向の寸法',
    'PDIA':'直径', 'PHEI':'高さ', 'PBDI':'底面の軸上位置', 'PTDI':'上面の軸上位置',
    'PAAX':'A 軸', 'PBAX':'B 軸', 'PCAX':'C 軸', 'PBTP':'上面 B 方向寸法', 'PCTP':'上面 C 方向寸法',
    'PBBT':'底面 B 方向寸法', 'PCBT':'底面 C 方向寸法', 'PBOF':'上面 B 方向オフセット', 'PCOF':'上面 C 方向オフセット',
    'PTDM':'上面直径', 'PBDM':'底面直径', 'PTRA':'上面半径（直径の代替）', 'PBRA':'底面半径（直径の代替）',
    'POFF':'偏心量', 'PDIAM':'チューブ直径', 'PANGLE':'回転角度（−360〜360 度）',
    'PXTS':'上面 X 方向傾斜', 'PYTS':'上面 Y 方向傾斜', 'PXBS':'底面 X 方向傾斜', 'PYBS':'底面 Y 方向傾斜',
    'LEVEL':'表示レベルの範囲（下限 上限）', 'CLFLA':'中心線描画フラグ', 'TUFLA':'チューブ描画フラグ',
    'GTYP':'汎用部品種別', 'PSKEY':'端部条件キー（通常 unset）', 'SKEY':'シンボルキー',
    'NAPP':'除去する適用先の組み合わせ', 'PTS':'順序付き P/T ポイント（最大 6）',
    'PTSPOS':'始点の位置式', 'PTEPOS':'終点の位置式', 'NAREF':'中立軸 PLINE の参照',
    'PKEY':'基準線の文字識別キー', 'PLAXI':'断面内の方向', 'DX':'終端までの X 座標差', 'DY':'終端までの Y 座標差',
    'DXLE':'終端までの X 寸法差', 'DYLE':'終端までの Y 寸法差', 'PRAD':'半径',
    'DRAD':'終端までの半径差', 'PWID':'円環の半径方向幅', 'DWID':'終端までの幅差', 'PANG':'円環角度（−180〜180 度）',
})
TYPE_MEANINGS = {
    'PTAXI': {'PDIS':'軸に沿うポイント位置'},
    'SCON': {'PDIS':'頂点から底面までの高さ', 'PDIA':'底面直径'},
    'SCYL': {'PDIS':'底面中心の軸上位置', 'PHEI':'底面からの高さ'},
    'SSLC': {'PDIS':'底面と軸の交点までの距離', 'PHEI':'軸上の上下端面間距離'},
    'SDIS': {'PDIS':'円板中心の軸上位置'},
    'SDSH': {'PDIS':'面中心の軸上距離（基準面は要確認）', 'PHEI':'底面からの最大盛上がり', 'PRAD':'隅半径：0 球面／正値 楕円面'},
    'SSPH': {'PDIS':'球中心の軸上位置'},
    'BOXI': {'PXLE':'断面 X 方向寸法', 'PZLE':'断面 Z 方向寸法', 'PAXI':'端面中心を通る法線の位置・方向'},
    'SRTO': {'PDIA':'矩形断面の幅', 'PHEI':'矩形断面の高さ'},
    'SCTO': {'PDIA':'円形断面直径', 'PAAX':'一方の端面の法線', 'PBAX':'他方の端面の法線'},
    'LSNO': {'PBAX':'偏心方向', 'PAAX':'上面法線・A 軸'},
    'SREC': {'PLAXI':'矩形のローカル Y 方向'}, 'SANN': {'PLAXI':'円環の開始方向', 'PRAD':'外半径'},
    'SPRO': {'PLAXI':'断面のローカル Y 方向'}, 'PLINE': {'PLAXI':'XY 面内で基準線から向く方向'},
    'SVER': {'PRAD':'頂点のフィレット半径'}, 'SPVE': {'PRAD':'頂点のフィレット半径', 'DRAD':'終端までのフィレット半径差'},
    'SEXT': {'PAAX':'輪郭のローカル X 軸', 'PBAX':'輪郭のローカル Y 軸', 'PHEI':'輪郭の押出し距離'},
    'SREV': {'PAAX':'輪郭 X 軸・回転軸', 'PBAX':'輪郭のローカル Y 軸'},
}
NOTES = {
    'LINE':'P は通常点、T は接線点。例：P1 P2 T3。対応 PTSET を参照します。',
    'SEXT':'SLOO の下に SVER を順番に並べます。PRAD は頂点に設定します。',
    'SREV':'輪郭を PAAX（ローカル X 軸）まわりに回転。角度は −360〜360 度。',
    'LSNO':'上面・底面はそれぞれ直径か半径を選択。同じ面の両方を同時に指定しません。',
    'SCTO':'円弧は 180 度以内。曲率の確定には端面の軸情報が必要です。',
    'BOXI':'GTYPE=TUBE の暗黙チューブ。長さ・配置は設計側の前後部品に依存します。',
    'TUBE':'GTYPE=TUBE の暗黙チューブ。独立した円筒の高さ入力はありません。',
    'PLINE':'線自体は部品 Z 軸と平行。位置と方向は XY 面内で定義します。',
    'SDSH':'PDIS の基準面は確認待ち。プレビューで基準面を推測しません。',
}


def positive(kind): return NEGATIVE_BASE.get(kind, kind)
def meaning(kind, key): return TYPE_MEANINGS.get(positive(kind), {}).get(key, DESCRIPTIONS.get(key, '未確認の属性'))
def known(kind): return kind in PT_TYPES or kind in GM_TYPES or kind in NEGATIVE_BASE or kind in STRUCTURAL_TYPES or kind in CHILD_TYPES

def fields(kind, section='main'):
    if kind in PT_TYPES:
        if section == 'detail': return PT_DETAIL
        return PT_COMMON + PT_TYPES[kind] if section == 'main' else ()
    if kind in STRUCTURAL_TYPES:
        if section == 'common': return ('LEVEL','CLFLA','TUFLA','DESC','PURP') if kind == 'PLINE' else GM_COMMON
        return STRUCTURAL_TYPES[kind] if section == 'main' else ()
    if kind in CHILD_TYPES: return CHILD_TYPES[kind] if section == 'main' else ()
    if kind in GM_TYPES or kind in NEGATIVE_BASE:
        if section == 'common': return GM_COMMON
        if section == 'negative': return NEGATIVE_EXTRA if kind in NEGATIVE_BASE else ()
        return GM_TYPES.get(positive(kind), ()) if section == 'main' else ()
    return ()


def walk(elements):
    for element in elements:
        yield element
        yield from walk(element.get('children', []))


def child_kind(kind):
    kind = positive(kind)
    return {'SEXT':'SLOO', 'SREV':'SLOO', 'SLOO':'SVER', 'SPRO':'SPVE'}.get(kind)


def add_child(element):
    kind = child_kind(element['type'])
    if not kind: raise ValueError('この要素には頂点・輪郭を追加できません。')
    children = element.setdefault('children', [])
    if kind == 'SLOO' and children: raise ValueError('既存の輪郭を選択して頂点を追加してください。')
    if len(children) >= 200: raise ValueError('子要素の上限です。')
    child = {'id':uuid.uuid4().hex, 'type':kind, 'name':LABELS[kind] + ' ' + str(len(children)+1), 'attrs':default_attrs(kind)}
    children.append(child); return child

def default_attrs(kind, number=1):
    attrs = {key: '' for section in ('main', 'detail', 'common', 'negative') for key in fields(kind, section)}
    if kind in PT_TYPES:
        attrs.update({key: 'unset' for key in PT_DETAIL})
        attrs['NUMB'] = str(number)
        for key in ('PX', 'PY', 'PZ', 'PDIS'):
            if key in attrs: attrs[key] = '0'
        if 'PAXI' in attrs: attrs['PAXI'] = 'X'
        if 'PTCDIR' in attrs: attrs['PTCDIR'] = 'X'
    if kind in NEGATIVE_BASE: attrs['NAPP'] = '1'
    return attrs


def value(element, key):
    """Display PTCD as its confirmed alias, without rewriting imported data."""
    attrs = element['attrs']
    if key == 'PTCDIR' and key not in attrs and 'PTCD' in attrs: return str(attrs['PTCD'])
    raw = attrs.get(key, '')
    return str(raw)


def set_value(element, key, text):
    attrs = element['attrs']
    if key == 'PTCDIR' and key not in attrs and 'PTCD' in attrs: key = 'PTCD'
    attrs[key] = text


def add_element(definition, kind):
    if not known(kind): raise ValueError('未対応の要素型です。')
    allowed = TYPES_BY_SET.get(definition['kind'], {})
    if kind not in allowed and not (definition['kind'] == 'GMSET' and kind in NEGATIVE_BASE): raise ValueError('定義と要素の種類が一致しません。')
    if len(definition['elements']) >= 200: raise ValueError('要素数は最大 200 です。')
    existing = {e['name'] for e in definition['elements']}
    n = 1
    while f'{kind} {n}' in existing: n += 1
    number = 1
    if definition['kind'] == 'PTSET':
        numbers = [int(e['attrs']['NUMB']) for e in definition['elements']
                   if str(e['attrs'].get('NUMB', '')).isdigit()]
        number = max(numbers + [0]) + 1
    element = {'id': uuid.uuid4().hex, 'type': kind, 'name': f'{kind} {n}', 'attrs': default_attrs(kind, number)}
    definition['elements'].append(element)
    return element


def change_type(element, kind):
    """Retain original fields/history; only fill missing fields of the new type."""
    if not known(kind): raise ValueError('未対応の要素型です。')
    if kind == element['type']: return
    element.setdefault('type_history', []).append({'type': element['type'], 'attrs': copy.deepcopy(element['attrs'])})
    element['type'] = kind
    for key, val in default_attrs(kind).items():
        if key == 'PTCDIR' and 'PTCD' in element['attrs']: continue
        element['attrs'].setdefault(key, val)


def demo_definitions():
    pt = {'id': 'ui-ptset', 'kind': 'PTSET', 'name': '/UI-POINTS', 'revision': '01', 'elements': []}
    for kind, name in zip(PT_TYPES, ('接続点 1', '接続点 2', '補助点', '基準点')):
        e = add_element(pt, kind); e['name'] = name
        e['attrs'].update(PCON='PARAM[5]', PBOR='PARAM[1]')
    pt['elements'][0]['attrs'].update(PAXI='-X', PDIS='PARAM[2] + 1.5 + DES PARAM[2]')
    pt['elements'][1]['attrs']['PY'] = '0.5 * APARAM[3]'
    gm = {'id': 'ui-gmset', 'kind': 'GMSET', 'name': '/UI-GEOMETRY', 'revision': '01', 'elements': []}
    for kind, name in (('SCYL', '胴部'), ('SCYL', 'フランジ'), ('SBOX', '補助形状'), ('NSCY', '切り欠き')):
        e = add_element(gm, kind); e['name'] = name
        if kind in ('SCYL', 'NSCY'): e['attrs'].update(PAXI='X', PHEI='PARAM[3]', PDIA='PARAM[1]', PDIS='PARAM[2]')
    gm['elements'][0]['attrs']['OBST'] = '2'
    return [pt, gm]
