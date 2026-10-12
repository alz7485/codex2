"""Integrated catalogue mockup model, independent of the desktop UI.

Parameters describe roles only. Actual numbers belong to SCOM records; GMSET
and PTSET hold reusable expressions. SPEC entries are a conceptual mockup
schema, not an implementation of the unverified E3D selection syntax.
"""
import ast
import copy
import json
import math
import re
import uuid
from pathlib import Path

from . import model

FORMAT = 'catalog-studio-integrated'
VERSION = 2
LIMITS = {'parameters': 100, 'cates': 1000, 'definitions': 1000,
          'scoms': 5000, 'specs': 1000, 'books': 1000}


def sample():
    """A shared reducer definition with three numerical SCOM sizes."""
    return {
        'format': FORMAT, 'version': VERSION, 'name': '配管カタログ管理',
        'parameters': [
            {'id': 'P1', 'role': '大径側外径', 'unit': 'mm'},
            {'id': 'P2', 'role': '小径側外径', 'unit': 'mm'},
            {'id': 'P3', 'role': '全長', 'unit': 'mm'},
            {'id': 'P4', 'role': '大径側呼び径', 'unit': 'mm'},
            {'id': 'P5', 'role': '小径側呼び径', 'unit': 'mm'}],
        'cates': [{'id': 'cate-reducer', 'name': '/REDUCER-CATE',
                   'description': '同心レデューサー（モックアップ参考値）', 'revision': '01'}],
        'definitions': [
            {'id': 'gm-reducer', 'name': '/REDUCER-GEOM', 'kind': 'GMSET',
             'revision': '01', 'elements': [
                 {'id': 'cone-body', 'type': 'cone', 'name': '円錐台 本体',
                  'attrs': {'大径': '大径側外径', '小径': '小径側外径',
                            '長さ': '全長', '位置': '全長 / 2', '方向': 'Z'}}]},
            {'id': 'pt-reducer', 'name': '/REDUCER-POINTS', 'kind': 'PTSET',
             'revision': '01', 'elements': [
                 {'id': 'point-large', 'type': 'point', 'name': '接続点 1',
                  'attrs': {'位置': '0', '方向': '-Z', '接続口径': '大径側呼び径'}},
                 {'id': 'point-small', 'type': 'point', 'name': '接続点 2',
                  'attrs': {'位置': '全長', '方向': 'Z', '接続口径': '小径側呼び径'}}]}],
        'scoms': [
            {'id': 'scom-65-40', 'name': '/REDUCER-65X40', 'cate_id': 'cate-reducer',
             'size': '65 × 40', 'revision': '01', 'gmset_id': 'gm-reducer',
             'ptset_id': 'pt-reducer', 'values': {'P1': 76.3, 'P2': 48.6, 'P3': 89, 'P4': 65, 'P5': 40}},
            {'id': 'scom-80-50', 'name': '/REDUCER-80X50', 'cate_id': 'cate-reducer',
             'size': '80 × 50', 'revision': '01', 'gmset_id': 'gm-reducer',
             'ptset_id': 'pt-reducer', 'values': {'P1': 89.1, 'P2': 60.5, 'P3': 89, 'P4': 80, 'P5': 50}},
            {'id': 'scom-100-65', 'name': '/REDUCER-100X65', 'cate_id': 'cate-reducer',
             'size': '100 × 65', 'revision': '01', 'gmset_id': 'gm-reducer',
             'ptset_id': 'pt-reducer', 'values': {'P1': 114.3, 'P2': 76.3, 'P3': 102, 'P4': 100, 'P5': 65}}],
        'specs': [{'id': 'spec-cs150', 'name': '/CS-150-SPEC',
                   'description': '炭素鋼クラスの選択表（仮データ・E3D選択構文は未検証）',
                   'revision': '01', 'entries': [
                       {'id': 'entry-65-40', 'type': 'REDU', 'bore1': '65', 'bore2': '40',
                        'scom_id': 'scom-65-40', 'description': '同心レデューサー'},
                       {'id': 'entry-80-50', 'type': 'REDU', 'bore1': '80', 'bore2': '50',
                        'scom_id': 'scom-80-50', 'description': '同心レデューサー'},
                       {'id': 'entry-100-65', 'type': 'REDU', 'bore1': '100', 'bore2': '65',
                        'scom_id': 'scom-100-65', 'description': '同心レデューサー'}]}],
        'books': []}


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _records(records, label, fields, limit):
    if not isinstance(records, list) or len(records) > limit:
        raise ValueError(label + 'の件数・形式を確認してください。')
    ids = set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get('id'), str) or not record['id']:
            raise ValueError(label + 'の識別子を確認してください。')
        if record['id'] in ids:
            raise ValueError(label + 'の識別子が重複しています。')
        ids.add(record['id'])
        if any(not isinstance(record.get(field), str) for field in fields):
            raise ValueError(label + 'の項目を確認してください。')


def validate(data):
    """Validate storage structure, while allowing incomplete editing drafts.

    Domain problems such as dangling references and invalid expressions are
    reported by issues(). Unrecognised metadata and element types are kept.
    """
    if not isinstance(data, dict) or data.get('format') != FORMAT or data.get('version') != VERSION:
        raise ValueError('対応する統合プロジェクト JSON ではありません。')
    if not isinstance(data.get('name'), str):
        raise ValueError('プロジェクト名がありません。')
    _records(data.get('parameters'), 'パラメータ', ('role', 'unit'), LIMITS['parameters'])
    roles = set()
    for p in data['parameters']:
        if (not re.fullmatch(r'P[1-9]\d*', p['id']) or not model.valid_role(p['role'])
                or p['role'] in roles or 'value' in p):
            raise ValueError('パラメータ番号・役割を確認してください。実数値は SCOM に保存します。')
        roles.add(p['role'])
    _records(data.get('cates'), 'CATE', ('name', 'description', 'revision'), LIMITS['cates'])
    _records(data.get('definitions'), '共通定義', ('name', 'kind', 'revision'), LIMITS['definitions'])
    for definition in data['definitions']:
        if definition['kind'] not in ('GMSET', 'PTSET'):
            raise ValueError('共通定義の種別を確認してください。')
        _records(definition.get('elements'), '要素', ('type', 'name'), 200)
        for e in definition['elements']:
            if not e['type'] or not isinstance(e.get('attrs'), dict):
                raise ValueError('要素型・属性の形式を確認してください。')
            if e['type'] in model.SCHEMAS and any(
                    not isinstance(e['attrs'].get(k), str) for k in model.SCHEMAS[e['type']][1]):
                raise ValueError('要素の式・方向は文字列で保存してください。')
    _records(data.get('scoms'), 'SCOM', ('name', 'cate_id', 'size', 'revision', 'gmset_id', 'ptset_id'), LIMITS['scoms'])
    for scom in data['scoms']:
        if (not isinstance(scom.get('values'), dict) or
                any(not isinstance(key, str) or not _finite(value) for key, value in scom['values'].items())):
            raise ValueError('SCOM のパラメータ値は有限の実数値で保存してください。')
    _records(data.get('specs'), 'SPEC', ('name', 'description', 'revision'), LIMITS['specs'])
    for spec in data['specs']:
        _records(spec.get('entries'), 'SPEC 選択行',
                 ('type', 'bore1', 'bore2', 'scom_id', 'description'), 5000)
    if not isinstance(data.get('books'), list) or len(data['books']) > LIMITS['books']:
        raise ValueError('カタログ本の構成を確認してください。')
    book_ids=set()
    for book in data['books']:
        if not isinstance(book,dict):raise ValueError('カタログ本の形式を確認してください。')
        # Preserve anonymous legacy metadata, but validate usable edition snapshots.
        if 'id' not in book:continue
        if not isinstance(book['id'],str) or not book['id'] or book['id'] in book_ids:
            raise ValueError('カタログ本の識別子が不正または重複しています。')
        book_ids.add(book['id'])
        if any(not isinstance(book.get(k),str) for k in ('title','edition','created_at','project_name')):
            raise ValueError('カタログ本のタイトル・版・日付を確認してください。')
        frozen={key:book.get(key) for key in ('parameters','cates','definitions','scoms','specs')}
        frozen.update(format=FORMAT,version=VERSION,name=book['project_name'],books=[])
        validate(frozen)
    return data


def get(data, collection, record_id):
    return next((record for record in data[collection] if record['id'] == record_id), None)


def parameters_for(data, scom):
    """Adapt an SCOM for the legacy safe expression evaluator and preview."""
    if isinstance(scom, str):
        scom = get(data, 'scoms', scom)
    if not scom:
        raise ValueError('表示する SCOM を選択してください。')
    parameters = []
    for p in data['parameters']:
        if p['id'] not in scom['values']:
            raise ValueError(scom['name'] + '：' + p['id'] + ' ' + p['role'] + 'の実数値がありません。')
        value = scom['values'][p['id']]
        if not _finite(value):
            raise ValueError(p['id'] + 'の実数値を確認してください。')
        parameters.append({**copy.deepcopy(p), 'value': value})
    return parameters


def _id():
    return uuid.uuid4().hex


def _name(records, stem):
    names = {record['name'] for record in records}
    candidate, index = stem, 2
    while candidate in names:
        candidate = stem + '-' + str(index)
        index += 1
    return candidate


def _append(data, collection, record):
    if len(data[collection]) >= LIMITS[collection]:
        raise ValueError(collection + 'の件数上限に達しました。')
    data[collection].append(record)
    return record


def add_cate(data, name=None):
    return _append(data, 'cates', {'id': _id(), 'name': _name(data['cates'], name or '/NEW-CATE'),
                                 'description': '', 'revision': '01'})


def add_scom(data, cate_id=None, name=None):
    gm = next((d for d in data['definitions'] if d['kind'] == 'GMSET'), None)
    pt = next((d for d in data['definitions'] if d['kind'] == 'PTSET'), None)
    return _append(data, 'scoms', {
        'id': _id(), 'name': _name(data['scoms'], name or '/NEW-SCOM'),
        'cate_id': cate_id if cate_id is not None else (data['cates'][0]['id'] if data['cates'] else ''),
        'size': '', 'revision': '01', 'gmset_id': gm['id'] if gm else '',
        'ptset_id': pt['id'] if pt else '', 'values': {}})


def _role(data, names, fallback_index=0):
    for name in names:
        parameter = next((p for p in data['parameters'] if p['role'] == name), None)
        if parameter:
            return parameter['role']
    if data['parameters']:
        return data['parameters'][min(fallback_index, len(data['parameters']) - 1)]['role']
    return ''


def add_element(data, definition, kind):
    """Create expression defaults; numerical part dimensions never live here."""
    if isinstance(definition, str):
        definition = get(data, 'definitions', definition)
    if not definition or kind not in model.SCHEMAS:
        raise ValueError('追加する定義・要素を選択してください。')
    if (definition['kind'] == 'PTSET') != (kind == 'point'):
        raise ValueError('形状は GMSET、ポイントは PTSET に追加してください。')
    if len(definition['elements']) >= 200:
        raise ValueError('要素数は最大 200 です。')
    outer = _role(data, ('外径', '大径側外径', '幅'))
    inner = _role(data, ('小径側外径', '奥行き'), 1)
    length = _role(data, ('全長', '長さ', '高さ'), 2)
    bore = _role(data, ('接続口径', '大径側呼び径', '呼び径'))
    attrs = {
        'cone': {'大径': outer, '小径': inner, '長さ': length, '位置': '0', '方向': 'Z'},
        'cylinder': {'直径': outer, '長さ': length, '位置': '0', '方向': 'Z'},
        'box': {'幅': outer, '奥行き': inner, '高さ': length, '位置': '0', '方向': 'Z'},
        'point': {'位置': '0', '方向': 'Z', '接続口径': bore}}[kind]
    element = {'id': _id(), 'type': kind,
               'name': _name(definition['elements'], model.SCHEMAS[kind][0]), 'attrs': attrs}
    definition['elements'].append(element)
    return element


def add_definition(data, kind='GMSET', name=None):
    if kind not in ('GMSET', 'PTSET'):
        raise ValueError('共通定義は GMSET または PTSET を選択してください。')
    definition = _append(data, 'definitions', {
        'id': _id(), 'name': _name(data['definitions'], name or '/NEW-' + kind),
        'kind': kind, 'revision': '01', 'elements': []})
    if kind == 'GMSET':
        add_element(data, definition, 'cone')
    else:
        start = add_element(data, definition, 'point')
        start['name'] = '接続点 1'
        start['attrs']['方向'] = '-Z'
        end = add_element(data, definition, 'point')
        end['name'] = '接続点 2'
        end['attrs']['位置'] = _role(data, ('全長', '長さ'), 2)
        end['attrs']['接続口径'] = _role(data, ('小径側呼び径', '接続口径', '呼び径'), 1)
    return definition


def add_spec(data, name=None):
    return _append(data, 'specs', {'id': _id(), 'name': _name(data['specs'], name or '/NEW-SPEC'),
                                 'description': '', 'revision': '01', 'entries': []})


def add_spec_entry(data, spec, scom_id=None):
    if isinstance(spec, str):
        spec = get(data, 'specs', spec)
    if not spec:
        raise ValueError('追加先の SPEC を選択してください。')
    if len(spec['entries']) >= 5000:
        raise ValueError('SPEC の選択行数は最大 5000 です。')
    scom = get(data, 'scoms', scom_id) if scom_id else (data['scoms'][0] if data['scoms'] else None)
    def bore_value(roles):
        parameter = next((p for p in data['parameters'] if p['role'] in roles), None)
        return str(scom['values'].get(parameter['id'], '')) if scom and parameter else ''
    # Numbers have catalogue-specific roles; do not assume P4/P5 are bores.
    bore1 = bore_value(('大径側呼び径', '呼び径', '接続口径'))
    bore2 = bore_value(('小径側呼び径',))
    entry = {'id': _id(), 'type': 'REDU', 'bore1': bore1, 'bore2': bore2,
             'scom_id': scom['id'] if scom else (scom_id or ''), 'description': ''}
    spec['entries'].append(entry)
    return entry


def duplicate_scom(data, scom):
    if isinstance(scom, str):
        scom = get(data, 'scoms', scom)
    if not scom:
        raise ValueError('複製する SCOM を選択してください。')
    duplicate = copy.deepcopy(scom)
    duplicate.update(id=_id(), name=_name(data['scoms'], scom['name'] + '-COPY'), revision='01')
    return _append(data, 'scoms', duplicate)


def rename_parameter(data, pid, new_role):
    if not model.valid_role(new_role) or any(p['id'] != pid and p['role'] == new_role for p in data['parameters']):
        raise ValueError('役割名は重複や空白、演算記号を含めずに入力してください。')
    parameter = get(data, 'parameters', pid)
    if not parameter:
        raise ValueError('変更するパラメータがありません。')
    old = parameter['role']
    for definition in data['definitions']:
        for element in definition['elements']:
            for key, value in element['attrs'].items():
                if isinstance(value, str) and key != '方向':
                    element['attrs'][key] = re.sub(
                        r'[^\s+*/()\-]+', lambda match: new_role if match[0] == old else match[0], value)
    parameter['role'] = new_role


def _expression_issue(expression, parameters):
    """Check expression syntax even when a definition has no SCOM yet."""
    known = {name for p in parameters for name in (p['id'], p['role'])}
    root = model.parse(expression)
    nodes = list(ast.walk(root))
    if len(nodes) > 1000:
        raise ValueError('式が複雑すぎます。')
    for node in nodes:
        if isinstance(node, ast.Constant):
            if not _finite(node.value):
                raise ValueError('式の数値を確認してください。')
        elif isinstance(node, ast.Name):
            if node.id not in known:
                raise ValueError('未定義のパラメータ：' + node.id)
        elif not isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Load,
                                   ast.Add, ast.Sub, ast.Mult, ast.Div, ast.UAdd, ast.USub)):
            raise ValueError('四則演算・括弧・パラメータ名／番号だけを使用してください。')


def issues(data):
    """Find problems without mutating definitions or filling missing values."""
    try:
        validate(data)
    except ValueError as exc:
        return [str(exc)]
    result = []
    # E3D names are globally visible; also find duplicate names across classes.
    names = {}
    for collection in ('cates', 'definitions', 'scoms', 'specs'):
        for record in data[collection]:
            if not record['name'].strip():
                result.append(collection + '：名前を入力してください。')
            elif record['name'].casefold() in names:
                result.append('名前が重複：' + record['name'])
            else:
                names[record['name'].casefold()] = collection
    for definition in data['definitions']:
        local_names = set()
        if not definition['elements']:
            result.append(definition['name'] + '：要素がありません。')
        for e in definition['elements']:
            prefix = definition['name'] + ' / ' + e['name']
            if not e['name'].strip():
                result.append(definition['name'] + '：要素名を入力してください。')
            elif e['name'] in local_names:
                result.append(definition['name'] + '：要素名が重複：' + e['name'])
            local_names.add(e['name'])
            if e['type'] not in model.SCHEMAS:
                result.append(prefix + '：未対応の要素型（原文は保持）：' + e['type'])
                continue
            if (definition['kind'] == 'PTSET') != (e['type'] == 'point'):
                result.append(prefix + '：形状／ポイントと定義種別が一致しません。')
            for attr in model.SCHEMAS[e['type']][1]:
                expr = e['attrs'][attr]
                if attr == '方向':
                    if expr not in model.DIRECTIONS:
                        result.append(prefix + '：方向が不正です。')
                else:
                    try:
                        _expression_issue(expr, data['parameters'])
                    except ValueError as exc:
                        result.append(prefix + ' / ' + attr + '：' + str(exc))
    defined_ids = {p['id'] for p in data['parameters']}
    for scom in data['scoms']:
        if not get(data, 'cates', scom['cate_id']):
            result.append(scom['name'] + '：所属 CATE が未選択または見つかりません。')
        for pid in sorted(defined_ids - scom['values'].keys()):
            p = get(data, 'parameters', pid)
            result.append(scom['name'] + '：' + pid + ' ' + p['role'] + 'の実数値がありません。')
        for pid in sorted(scom['values'].keys() - defined_ids):
            result.append(scom['name'] + '：未定義のパラメータ値：' + pid)
        for ref_key, kind in (('gmset_id', 'GMSET'), ('ptset_id', 'PTSET')):
            definition = get(data, 'definitions', scom[ref_key])
            if not definition or definition['kind'] != kind:
                result.append(scom['name'] + '：' + kind + 'の参照先が未選択または不正です。')
                continue
            # Evaluate only with supplied values. Missing values remain missing.
            parameters = [{**p, 'value': scom['values'][p['id']]} for p in data['parameters']
                          if p['id'] in scom['values']]
            for e in definition['elements']:
                if e['type'] not in model.SCHEMAS:
                    continue
                for attr in model.SCHEMAS[e['type']][1]:
                    if attr == '方向':
                        continue
                    try:
                        value = model.evaluate(e['attrs'][attr], parameters)
                        if attr != '位置' and value <= 0:
                            result.append(scom['name'] + ' / ' + e['name'] + '：' + attr + 'は正の値にしてください。')
                    except ValueError as exc:
                        result.append(scom['name'] + ' / ' + e['name'] + ' / ' + attr + '：' + str(exc))
    for spec in data['specs']:
        selections = set()
        for entry in spec['entries']:
            if not get(data, 'scoms', entry['scom_id']):
                result.append(spec['name'] + '：選択行の SCOM が未選択または見つかりません。')
            if not entry['type'].strip() or not entry['bore1'].strip():
                result.append(spec['name'] + '：選択行の部品種別・口径1を入力してください。')
            key = (entry['type'].strip().casefold(), entry['bore1'].strip(), entry['bore2'].strip())
            if key in selections:
                result.append(spec['name'] + '：部品種別・口径の選択条件が重複しています。')
            selections.add(key)
    return list(dict.fromkeys(result))


def migrate(data):
    """Move v1 sample numbers into one SCOM without rewriting its expressions."""
    model.validate(data)
    integrated = copy.deepcopy(data)
    integrated.update(format=FORMAT, version=VERSION)
    original_name = data['name']
    parameters = []
    values = {}
    for parameter in data['parameters']:
        p = copy.deepcopy(parameter)
        values[p['id']] = p.pop('value')
        p.setdefault('unit', 'mm')
        parameters.append(p)
    integrated['parameters'] = parameters
    integrated.pop('elements', None)
    gm = {'id': _id(), 'name': '/' + original_name + '-GMSET', 'kind': 'GMSET',
          'revision': '01', 'elements': [copy.deepcopy(e) for e in data['elements'] if e['type'] != 'point']}
    pt = {'id': _id(), 'name': '/' + original_name + '-PTSET', 'kind': 'PTSET',
          'revision': '01', 'elements': [copy.deepcopy(e) for e in data['elements'] if e['type'] == 'point']}
    cate = {'id': _id(), 'name': '/' + original_name + '-CATE',
            'description': '旧モックアップから読み込み', 'revision': '01'}
    integrated.update(cates=[cate], definitions=[gm, pt],
                      scoms=[{'id': _id(), 'name': '/' + original_name + '-SCOM',
                              'cate_id': cate['id'], 'size': '', 'revision': '01',
                              'gmset_id': gm['id'], 'ptset_id': pt['id'], 'values': values}],
                      specs=[], books=[])
    integrated['migration'] = {'source_format': data['format'], 'source_version': data['version']}
    return validate(integrated)


def load(path):
    path = Path(path)
    if path.stat().st_size > 20_000_000:
        raise ValueError('20 MB 以下のプロジェクト JSON を選んでください。')
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('UTF-8 のプロジェクト JSON を選んでください。') from exc
    if isinstance(data, dict) and data.get('format') == 'catalog-studio-mockup' and data.get('version') == 1:
        return migrate(data)
    return validate(data)


def save(data, path):
    validate(data)
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def macro_text(data):
    """A comments-only review report; never pretend to be an executable macro."""
    lines = []
    def comment(value=''):
        # Newlines in user input must not introduce executable command lines.
        lines.extend('$* ' + line for line in str(value).splitlines() or [''])
    comment('Catalog Studio — 統合モックアップ')
    comment('E3D 登録用の実行マクロではありません。')
    comment('SPEC は概念上の選択表です。E3D 4.0 の選択構文は未検証です。')
    comment('プロジェクト：' + data['name'])
    for cate in data['cates']:
        comment('CATE ' + cate['name'] + ' / 改訂 ' + cate['revision'])
        for scom in data['scoms']:
            if scom['cate_id'] != cate['id']:
                continue
            comment('  SCOM ' + scom['name'] + ' / サイズ ' + scom['size'])
            for key, kind in (('gmset_id', 'GMRE'), ('ptset_id', 'PTRE')):
                definition = get(data, 'definitions', scom[key])
                comment('    ' + kind + ' → ' + (definition['name'] if definition else '[未設定]'))
            for p in data['parameters']:
                comment('    ' + p['id'] + ' ' + p['role'] + ' = ' + str(scom['values'].get(p['id'], '[未入力]')))
    for definition in data['definitions']:
        comment(definition['kind'] + ' ' + definition['name'])
        for element in definition['elements']:
            comment('  ' + element['name'] + ' [' + element['type'] + ']')
            for attr, expr in element['attrs'].items():
                comment('    ' + attr + ' = ' + str(expr))
    for spec in data['specs']:
        comment('SPEC ' + spec['name'] + ' / 改訂 ' + spec['revision'])
        for entry in spec['entries']:
            scom = get(data, 'scoms', entry['scom_id'])
            comment('  ' + entry['type'] + ' ' + entry['bore1'] + ' × ' + entry['bore2']
                    + ' → ' + (scom['name'] if scom else '[未設定]'))
    return '\n'.join(lines)
