"""Editor field lists supplied by the user, not a verified E3D command dictionary."""
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
    'SEXT': ('PX', 'PY', 'PZ', 'PAAX', 'PBAX', 'PHEI', 'PRAD'),
    'SREV': ('PX', 'PY', 'PZ', 'PAAX', 'PBAX', 'PANGLE', 'PRAD'),
}
GM_COMMON = ('LEVEL', 'CLFLA', 'TUFLA', 'OBST', 'DESC', 'GTYP', 'PURP')
NEGATIVE_EXTRA = ('PJOI', 'SJOI', 'SUBJ', 'SCOJ', 'PFIT', 'COFI', 'FITT', 'FIXI')
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


def known(kind):
    return kind in PT_TYPES or kind in GM_TYPES or kind in NEGATIVE_BASE


def fields(kind, section='main'):
    if kind in PT_TYPES:
        return PT_DETAIL if section == 'detail' else PT_COMMON + PT_TYPES[kind]
    if kind in GM_TYPES or kind in NEGATIVE_BASE:
        if section == 'common': return GM_COMMON
        if section == 'negative': return NEGATIVE_EXTRA if kind in NEGATIVE_BASE else ()
        positive = NEGATIVE_BASE[kind] if kind in NEGATIVE_BASE else kind
        return GM_TYPES.get(positive, ())
    return ()


def default_attrs(kind, number=1):
    attrs = {key: '' for section in ('main', 'detail', 'common', 'negative') for key in fields(kind, section)}
    if kind in PT_TYPES:
        attrs.update({key: 'unset' for key in PT_DETAIL})
        attrs['NUMB'] = str(number)
        for key in ('PX', 'PY', 'PZ', 'PDIS'):
            if key in attrs: attrs[key] = '0'
        if 'PAXI' in attrs: attrs['PAXI'] = 'X'
        if 'PTCDIR' in attrs: attrs['PTCDIR'] = 'X'
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
    if (kind in PT_TYPES) != (definition['kind'] == 'PTSET'): raise ValueError('定義と要素の種類が一致しません。')
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
