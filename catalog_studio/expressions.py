"""Restricted catalogue expression parser. No eval, Python execution or implicit contexts."""
import math
import re
from . import units

FAMILIES = ('PARAM', 'IPARAM', 'APARAM', 'OPARAM', 'DES PARAM', 'DES APARAM', 'DES OPARAM')
ALIASES = {'PARA':'PARAM', 'IPARA':'IPARAM', 'APARA':'APARAM', 'OPARA':'OPARAM',
           'DESP':'DES PARAM', 'DESA':'DES APARAM', 'DESO':'DES OPARAM',
           'ADESP':'DES APARAM', 'ODESP':'DES OPARAM'}
TOKEN = re.compile(r'\s*(?:(\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)|([^\W\d]\w*)|([+*/()\[\],\-])|("[^"\n]*"|\x27[^\x27\n]*\x27))', re.UNICODE)


def parse(text, parameters=()):
    text = str(text).strip().replace('＊', '*').replace('×', '*').replace('÷', '/')
    if not text or len(text) > 4096: raise ValueError('式は 1〜4096 文字で入力してください。')
    tokens = []; pos = 0
    while pos < len(text):
        match = TOKEN.match(text, pos)
        if not match: raise ValueError('解釈できない式：' + text[pos:pos+30])
        tokens.append(next(x for x in match.groups() if x is not None)); pos = match.end()
    if len(tokens) > 256: raise ValueError('式が複雑すぎます。')
    roles = {p['role']: p['id'] for p in parameters}
    index = 0
    def take():
        nonlocal index
        if index >= len(tokens): raise ValueError('式が途中で終わっています。')
        result = tokens[index]; index += 1; return result
    def peek(): return tokens[index].upper() if index < len(tokens) else ''
    def atom(depth):
        if depth > 40: raise ValueError('式の入れ子が深すぎます。')
        token = take(); upper = token.upper()
        if token in ('+', '-'): return ('unary', token, atom(depth+1))
        if token == '(':
            value = expr(0, depth+1)
            if take() != ')': raise ValueError('括弧が一致しません。')
            return value
        if token[0] in ('"', "'"): return ('word', token[1:-1])
        if re.fullmatch(r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', token):
            value = float(token)
            if not math.isfinite(value): raise ValueError('有限の数値を使用してください。')
            if peek().lower() in units.UNITS:
                factor,dim=units.UNITS[take().lower()]
                value*=factor
                if not math.isfinite(value):raise ValueError('有限の数値を使用してください。')
                return ('quantity',value,dim)
            return ('number', value)
        if upper == 'ATTRIB': return atom(depth+1)
        if upper in ('SUM', 'DIFF', 'TIMES', 'DIV'):
            return ('binary', {'SUM':'+', 'DIFF':'-', 'TIMES':'*', 'DIV':'/'}[upper], atom(depth+1), atom(depth+1))
        if upper == 'TAN': return ('tan', atom(depth+1))
        if upper in ('SIN','COS','ASIN','ACOS','ATAN'):return ('func',upper,atom(depth+1))
        if upper=='TWICE':return ('binary','*',('number',2.),atom(depth+1))
        aliases={'DDA':'DDANGLE','DDANG':'DDANGLE','DDHEI':'DDHEIGHT','DDRAD':'DDRADIUS','ANGLE':'ANGL','HEIGHT':'HEIG'}
        upper=aliases.get(upper,upper)
        if upper in ('ANGL','HEIG','DDANGLE','DDHEIGHT','DDRADIUS','BORE'): return ('attr',upper)
        if upper == 'DES':
            upper = 'DES ' + ALIASES.get(take().upper(), tokens[index-1].upper())
        else: upper = ALIASES.get(upper, upper)
        if upper in FAMILIES:
            bracket = peek() == '['
            if bracket: take()
            number = take()
            if not re.fullmatch(r'[1-9]\d*', number): raise ValueError('パラメータ番号は正の整数です。')
            if bracket and take() != ']': raise ValueError('参照の括弧を閉じてください。')
            return ('ref', upper, 'P' + number)
        if token in roles: return ('ref', 'PARAM', roles[token])
        if re.fullmatch(r'P[1-9]\d*', upper): return ('ref', 'PARAM', upper)
        raise ValueError('未定義の名前：' + token)
    operators = {'+':(1,'+'), '-':(1,'-'), '*':(2,'*'), '/':(2,'/'), 'TIMES':(2,'*'), 'DIV':(2,'/')}
    def expr(minimum, depth):
        left = atom(depth)
        while peek() in operators and operators[peek()][0] >= minimum:
            precedence, op = operators[take().upper()]
            left = ('binary', op, left, expr(precedence+1, depth+1))
        return left
    root = expr(0, 0)
    if index != len(tokens): raise ValueError('式の余分な入力：' + tokens[index])
    return root


def refs(root):
    if root[0] == 'ref': return {(root[1], root[2])}
    if root[0] in ('number','quantity','word','attr'): return set()
    if root[0] in ('tan',): return refs(root[1])
    if root[0]=='func':return refs(root[2])
    if root[0] == 'unary': return refs(root[2])
    return refs(root[2]) | refs(root[3])


def attribute_refs(root):
    if root[0]=='attr':return {root[1]}
    if root[0] in ('number','quantity','word','ref'):return set()
    if root[0]=='tan':return attribute_refs(root[1])
    if root[0] in ('func','unary'):return attribute_refs(root[2])
    return attribute_refs(root[2])|attribute_refs(root[3])


def normalized(text, parameters=()):
    def render(node):
        kind = node[0]
        if kind == 'number': return f'{node[1]:g}'
        if kind == 'quantity':return f'{node[1]:.15g}'+({units.DIST:'mm',units.ANGL:'degrees',units.SCALAR:'none'}[node[2]])
        if kind == 'word': return '"' + node[1] + '"'
        if kind == 'ref': return node[1] + '[' + node[2][1:] + ']'
        if kind == 'attr': return node[1]
        if kind == 'tan': return 'TAN(' + render(node[1]) + ')'
        if kind == 'func':return node[1]+'('+render(node[2])+')'
        if kind == 'unary': return '(' + node[1] + render(node[2]) + ')'
        return '(' + render(node[2]) + ' ' + node[1] + ' ' + render(node[3]) + ')'
    return render(parse(text, parameters))


def evaluate(text, contexts=None, attributes=None, parameters=(), expected=None, typed=False):
    contexts = contexts or {}; attributes = attributes or {}
    def numeric(value):
        if type(value) not in (int, float) or not math.isfinite(value): raise ValueError('数値演算には有限の数値パラメータが必要です。')
        return value
    def run(node):
        kind = node[0]
        if kind=='word':return node[1]
        if kind=='number':return units.Quantity(node[1])
        if kind=='quantity':return units.Quantity(node[1],node[2])
        if kind == 'ref':
            if node[2] not in contexts.get(node[1], {}): raise ValueError('値が未設定：' + node[1] + '[' + node[2][1:] + ']')
            value=contexts[node[1]][node[2]]
            if isinstance(value,str):return value
            rule=next((p for p in parameters if p['id']==node[2]),{}) if node[1]=='PARAM' else {}
            factor=units.UNITS.get(str(rule.get('unit','')).lower(),(1,None))[0]
            return units.Quantity(numeric(value)*factor,units.dimension(rule.get('unit')))
        if kind == 'attr':
            if node[1] not in attributes: raise ValueError('コンポーネント属性が未設定：' + node[1])
            return units.Quantity(numeric(attributes[node[1]]),units.ANGL if node[1] in ('ANGL','DDANGLE') else units.DIST)
        if kind in ('tan','func'):
            arg=run(node[1] if kind=='tan' else node[2])
            if not isinstance(arg,units.Quantity):raise ValueError('関数には数値が必要です。')
            return units.function('TAN' if kind=='tan' else node[1],arg)
        if kind == 'unary':
            value=run(node[2])
            if not isinstance(value,units.Quantity):raise ValueError('数値演算には数値が必要です。')
            return units.Quantity(value.value if node[1]=='+' else -value.value,value.dimension)
        left,right=run(node[2]),run(node[3])
        if not isinstance(left,units.Quantity) or not isinstance(right,units.Quantity):raise ValueError('数値演算には数値パラメータが必要です。')
        result=units.binary(node[1],left,right);numeric(result.value);return result
    result = run(parse(text, parameters))
    if isinstance(result,str):
        if expected is not None:raise ValueError('寸法・角度には数値が必要です。')
        return result
    units.compatible(result.dimension,{'DIST':units.DIST,'ANGL':units.ANGL,'NONE':units.SCALAR}.get(expected))
    numeric(result.value)
    return result if typed else result.value


def contexts_for(scom):
    """Preview contexts are explicitly supplied; attached/owning never fall back."""
    supplied = dict(scom.get('expression_contexts', {}))
    supplied['PARAM'] = scom.get('values', {})
    return supplied
