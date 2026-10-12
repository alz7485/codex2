"""Project data and arithmetic independent of the desktop UI."""
import ast
import copy
import json
import math
import re
import uuid
from pathlib import Path

SCHEMAS = {
    'cone': ('円錐台', ('大径', '小径', '長さ', '位置', '方向')),
    'cylinder': ('円筒', ('直径', '長さ', '位置', '方向')),
    'box': ('箱', ('幅', '奥行き', '高さ', '位置', '方向')),
    'point': ('接続ポイント', ('位置', '方向', '接続口径')),
}
DIRECTIONS = ('X', '-X', 'Y', '-Y', 'Z', '-Z')


def sample():
    return {'format': 'catalog-studio-mockup', 'version': 1, 'name': 'レデューサー',
            'parameters': [{'id': 'P1', 'role': '大径側外径', 'value': 100},
                           {'id': 'P2', 'role': '小径側外径', 'value': 50},
                           {'id': 'P3', 'role': '全長', 'value': 120}],
            'elements': [
                {'id': 'shape1', 'type': 'cone', 'name': '円錐台 本体',
                 'attrs': {'大径': '大径側外径', '小径': '小径側外径', '長さ': '全長', '位置': '全長 / 2', '方向': 'Z'}},
                {'id': 'point1', 'type': 'point', 'name': '接続点 1',
                 'attrs': {'位置': '0', '方向': '-Z', '接続口径': '大径側外径'}},
                {'id': 'point2', 'type': 'point', 'name': '接続点 2',
                 'attrs': {'位置': '全長', '方向': 'Z', '接続口径': '小径側外径'}}]}


def valid_role(name):
    return (isinstance(name, str) and name.isidentifier()
            and not re.fullmatch(r'P\d+', name) and name not in ('True', 'False', 'None'))


def validate(data):
    if not isinstance(data, dict) or data.get('format') != 'catalog-studio-mockup' or data.get('version') != 1:
        raise ValueError('対応するプロジェクト JSON ではありません。')
    if not isinstance(data.get('name'), str):
        raise ValueError('部品名がありません。')
    params, elements = data.get('parameters'), data.get('elements')
    if not isinstance(params, list) or not isinstance(elements, list) or len(params) > 100 or len(elements) > 200:
        raise ValueError('パラメータ・要素の構成を確認してください。')
    ids, roles = set(), set()
    for p in params:
        if not isinstance(p, dict):
            raise ValueError('パラメータの形式を確認してください。')
        pid, role, value = p.get('id'), p.get('role'), p.get('value')
        if (not isinstance(pid, str) or not re.fullmatch(r'P[1-9]\d*', pid)
                or not valid_role(role) or type(value) not in (int, float)
                or not math.isfinite(value) or pid in ids or role in roles):
            raise ValueError('パラメータの番号・役割・数値が不正または重複しています。')
        ids.add(pid); roles.add(role)
    ids = set()
    for e in elements:
        if not isinstance(e, dict) or e.get('type') not in SCHEMAS:
            raise ValueError('未対応の要素型です。')
        if (not isinstance(e.get('id'), str) or not e['id'] or e['id'] in ids
                or not isinstance(e.get('name'), str) or not isinstance(e.get('attrs'), dict)
                or any(not isinstance(e['attrs'].get(k), str) for k in SCHEMAS[e['type']][1])):
            raise ValueError('要素の名前・属性・識別子を確認してください。')
        ids.add(e['id'])
    return data


def parse(expression):
    if not isinstance(expression, str) or len(expression) > 2000:
        raise ValueError('式は 2000 文字以内で入力してください。')
    try:
        return ast.parse(expression.strip(), mode='eval').body
    except (SyntaxError, RecursionError) as exc:
        raise ValueError('式の構文・括弧を確認してください。') from exc


def evaluate(expression, parameters):
    values = {key: p['value'] for p in parameters for key in (p['id'], p['role'])}
    def visit(node, depth=0):
        if depth > 60:
            raise ValueError('式が複雑すぎます。')
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.Name):
            if node.id not in values:
                raise ValueError('未定義のパラメータ：' + node.id)
            value = values[node.id]
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand, depth + 1) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = visit(node.left, depth + 1), visit(node.right, depth + 1)
            if isinstance(node.op, ast.Add): value = a + b
            elif isinstance(node.op, ast.Sub): value = a - b
            elif isinstance(node.op, ast.Mult): value = a * b
            elif b == 0: raise ValueError('ゼロで除算できません。')
            else: value = a / b
        else:
            raise ValueError('四則演算・括弧・パラメータ名／番号だけを使用してください。')
        try:
            if not math.isfinite(value): raise ValueError('計算結果が有限の数値ではありません。')
        except OverflowError as exc:
            raise ValueError('数値が大きすぎます。') from exc
        return value
    return visit(parse(expression))


def references(expression, parameters):
    # Token matching also works while an expression is incomplete.
    names = set(re.findall(r'[^\s+*/()\-]+', expression))
    return [p['id'] for p in parameters if p['id'] in names or p['role'] in names]


def rename_parameter(data, pid, new_role):
    if not valid_role(new_role) or any(p['id'] != pid and p['role'] == new_role for p in data['parameters']):
        raise ValueError('役割名は重複や空白、演算記号を含めずに入力してください。')
    p = next(p for p in data['parameters'] if p['id'] == pid)
    old = p['role']
    for e in data['elements']:
        for k, v in e['attrs'].items():
            e['attrs'][k] = re.sub(r'[^\s+*/()\-]+', lambda m: new_role if m[0] == old else m[0], v)
    p['role'] = new_role


def add_element(data, kind):
    if len(data['elements']) >= 200: raise ValueError('要素数は最大 200 です。')
    base = data['parameters'][0]['role'] if data['parameters'] else '50'
    length = next((p['role'] for p in data['parameters'] if p['role'] == '全長'), '120')
    attrs = {'cone': {'大径': base, '小径': '25', '長さ': length, '位置': '0', '方向': 'Z'},
             'cylinder': {'直径': base, '長さ': length, '位置': '0', '方向': 'Z'},
             'box': {'幅': base, '奥行き': '40', '高さ': '30', '位置': '0', '方向': 'Z'},
             'point': {'位置': '0', '方向': 'Z', '接続口径': base}}[kind]
    label = SCHEMAS[kind][0]; n = 1
    while any(e['name'] == f'{label} {n}' for e in data['elements']): n += 1
    element = {'id': uuid.uuid4().hex, 'type': kind, 'name': f'{label} {n}', 'attrs': attrs}
    data['elements'].append(element)
    return element


def duplicate_element(data, element):
    if len(data['elements']) >= 200: raise ValueError('要素数は最大 200 です。')
    new = copy.deepcopy(element); new['id'] = uuid.uuid4().hex
    n = 1; name = element['name'] + ' コピー'
    while any(e['name'] == name for e in data['elements']):
        n += 1; name = element['name'] + f' コピー {n}'
    new['name'] = name; data['elements'].append(new)
    return new


def issues(data):
    result, names = [], set()
    for e in data['elements']:
        if not e['name'].strip(): result.append('要素名を入力してください。')
        if e['name'] in names: result.append('要素名が重複：' + e['name'])
        names.add(e['name'])
        for k in SCHEMAS[e['type']][1]:
            v = e['attrs'][k]
            if k == '方向':
                if v not in DIRECTIONS: result.append(e['name'] + '：方向が不正です。')
                continue
            try:
                if evaluate(v, data['parameters']) <= 0 and k != '位置':
                    result.append(e['name'] + '：' + k + 'は正の値にしてください。')
            except ValueError as exc: result.append(e['name'] + ' / ' + k + '：' + str(exc))
    return result


def load(path):
    path = Path(path)
    if path.stat().st_size > 2_000_000: raise ValueError('2 MB 以下のファイルを選んでください。')
    return validate(json.loads(path.read_text(encoding='utf-8-sig')))


def save(data, path):
    validate(data)
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def macro_text(data):
    lines = ['$* Catalog Studio — PYTHON MOCKUP ONLY', '$* E3D 登録用の実行マクロではありません。', '$* 部品：' + data['name'], '']
    for e in data['elements']:
        lines.append('$* ' + e['name'] + ' [' + SCHEMAS[e['type']][0] + ']')
        lines.extend('$*   ' + k + ' = ' + v for k, v in e['attrs'].items())
        lines.append('')
    return '\n'.join(lines)
