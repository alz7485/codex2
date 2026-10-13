"""Restricted catalogue expression parser. No eval, Python execution or implicit contexts."""
import math
import re

FAMILIES = ('PARAM', 'IPARAM', 'APARAM', 'OPARAM', 'DES PARAM', 'DES APARAM', 'DES OPARAM')
ALIASES = {'PARA':'PARAM', 'IPARA':'IPARAM', 'APARA':'APARAM', 'OPARA':'OPARAM',
           'DESP':'DES PARAM', 'DESA':'DES APARAM', 'DESO':'DES OPARAM'}
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
            return ('number', value)
        if upper == 'ATTRIB': return atom(depth+1)
        if upper in ('SUM', 'DIFF', 'TIMES', 'DIV'):
            return ('binary', {'SUM':'+', 'DIFF':'-', 'TIMES':'*', 'DIV':'/'}[upper], atom(depth+1), atom(depth+1))
        if upper == 'TAN': return ('tan', atom(depth+1))
        if upper == 'ANGL': return ('attr', 'ANGL')
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
    if root[0] in ('number','word','attr'): return set()
    if root[0] in ('tan',): return refs(root[1])
    if root[0] == 'unary': return refs(root[2])
    return refs(root[2]) | refs(root[3])


def normalized(text, parameters=()):
    def render(node):
        kind = node[0]
        if kind == 'number': return f'{node[1]:g}'
        if kind == 'word': return '"' + node[1] + '"'
        if kind == 'ref': return node[1] + '[' + node[2][1:] + ']'
        if kind == 'attr': return node[1]
        if kind == 'tan': return 'TAN(' + render(node[1]) + ')'
        if kind == 'unary': return '(' + node[1] + render(node[2]) + ')'
        return '(' + render(node[2]) + ' ' + node[1] + ' ' + render(node[3]) + ')'
    return render(parse(text, parameters))


def evaluate(text, contexts=None, attributes=None, parameters=()):
    contexts = contexts or {}; attributes = attributes or {}
    def numeric(value):
        if type(value) not in (int, float) or not math.isfinite(value): raise ValueError('数値演算には有限の数値パラメータが必要です。')
        return value
    def run(node):
        kind = node[0]
        if kind in ('number', 'word'): return node[1]
        if kind == 'ref':
            if node[2] not in contexts.get(node[1], {}): raise ValueError('値が未設定：' + node[1] + '[' + node[2][1:] + ']')
            return contexts[node[1]][node[2]]
        if kind == 'attr':
            if node[1] not in attributes: raise ValueError('コンポーネント属性が未設定：' + node[1])
            return numeric(attributes[node[1]])
        if kind == 'tan':
            angle = numeric(run(node[1])); radians = math.radians(angle)
            if abs(math.cos(radians)) < 1e-12: raise ValueError('TAN が定義できない角度です。')
            return numeric(math.tan(radians))
        if kind == 'unary':
            value = numeric(run(node[2])); return value if node[1] == '+' else -value
        left, right = numeric(run(node[2])), numeric(run(node[3]))
        if node[1] == '/' and right == 0: raise ValueError('ゼロで除算できません。')
        result = {'+':lambda:left+right, '-':lambda:left-right, '*':lambda:left*right, '/':lambda:left/right}[node[1]]()
        return numeric(result)
    result = run(parse(text, parameters))
    if not isinstance(result, str): numeric(result)
    return result


def contexts_for(scom):
    """Preview contexts are explicitly supplied; attached/owning never fall back."""
    supplied = dict(scom.get('expression_contexts', {}))
    supplied['PARAM'] = scom.get('values', {})
    return supplied
