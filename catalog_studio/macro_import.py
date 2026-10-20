"""Read declarative NEW/END catalogue text without executing macro commands."""
import copy
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import element_schema as schema, presets, project, alp, macro_destinations

MAX_BYTES = 8 * 1024 * 1024
SET_TYPES = tuple(schema.TYPES_BY_SET)
TYPE_ALIASES = {kind: kind for kind in (*SET_TYPES, *schema.PT_TYPES, *schema.GM_TYPES,
                                      *schema.NEGATIVE_BASE, *schema.STRUCTURAL_TYPES, *schema.CHILD_TYPES)}
TYPE_ALIASES.update(dict(PTSE='PTSET', GMSE='GMSET', NGMS='NGMSET', PTSS='PTSSET', GMSS='GMSSET',
                         PTAX='PTAXI', PTCA='PTCAR', PTMI='PTMIX', PLIN='PLINE',
                         SLOOP='SLOO', SVERTEX='SVER', SPVERTEX='SPVE',
                         SRECTANGLE='SREC', SANNULUS='SANN', SPROFILE='SPRO'))
TYPE_ALIASES.update({long: short for short, long in alp.TYPE_NAMES.items()})
WRAPPERS = {'CATA': (), 'SECT': ('CATA',), 'CATE': ('SECT',)}
ATTR_ALIASES = {key: key for kind in TYPE_ALIASES.values()
                for section in ('main', 'detail', 'common', 'negative') for key in schema.fields(kind, section)}
ATTR_ALIASES.update({key: key for fields in schema.PARENT_FIELDS.values() for key in fields})
for short, long, minimum in [('NUMB', 'NUMBER', 3), ('PBOR', 'PBORE', 4),
                            ('PCON', 'PCONNECTION', 4), ('PDIS', 'PDISTANCE', 4),
                            ('PDIA', 'PDIAMETER', 4), ('PHEI', 'PHEIGHT', 4),
                            ('PAXI', 'PAXIS', 4), ('PTCDIR', 'PTCDIRECTION', 6),
                            ('TVISI', 'TVISIBLE', 5), ('BVISI', 'BVISIBLE', 5),
                            ('GTYP', 'GTYPE', 4)]:
    ATTR_ALIASES.update({long[:length]: short for length in range(minimum, len(long) + 1)})
ATTR_ALIASES.update(CLFL='CLFLA', TUFL='TUFLA', PTCD='PTCDIR', SETP='PTS')
CONTROL = {'DELETE', 'COPY', 'RENAME', 'REORDER', 'INCLUDE', 'RETURN', 'FINISH', 'EXIT',
           'SAVEWORK', 'VAR', 'DO', 'IF', 'ELSE', 'ENDIF', 'ENDDO', 'ALPHA', 'INPUT',
           'OUTPUT', 'TRACE', 'Q', 'QUERY', 'CE', 'MODEL', 'REPRESENTATION', 'UNITS',
           'MM', 'INCH', 'FINCH', 'GOTO', 'OWNER', 'OWN', 'NEXT', 'PREV', 'SAME', 'OLD', 'LOCK'}
COMMANDS = {'NEW', 'END', 'NAME', 'UNSET'}


class MacroImportError(ValueError):
    def __init__(self, line, message):
        self.line = line
        super().__init__(f'{line}行目：{message}')


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    line: int


@dataclass
class ParsedMacro:
    definitions: list
    warnings: list


def read_text(path):
    """Strict decoding: never replace unreadable bytes with lost characters."""
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('読込ファイルは8 MB以内にしてください。')
    encodings = ('utf-16',) if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else ('utf-8-sig', 'cp932')
    for encoding in encodings:
        try:
            text = raw.decode(encoding)
        except UnicodeError:
            continue
        if '\x00' not in text:
            return text, encoding
    raise ValueError('文字コードを読めません。UTF-8、UTF-16（BOM付き）、またはShift-JISで保存してください。')


def _statements(text):
    """Keep quoted strings/parenthesized expressions together, including newlines."""
    text = text.removeprefix('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
    if len(text.encode('utf-8')) > MAX_BYTES or '\x00' in text:
        raise ValueError('テキストのサイズまたは形式を確認してください（8 MB以内）。')
    clean = list(text)
    tokens, statements = [], []
    index, line, block, count = 0, 1, 0, 0
    while index < len(text):
        if text.startswith('$(', index):
            block += 1
            if block > 16: raise MacroImportError(line, 'コメントの入れ子が深すぎます。')
            clean[index:index + 2] = '  '; index += 2; continue
        if block:
            if text.startswith('$)', index):
                block -= 1; clean[index:index + 2] = '  '; index += 2; continue
            if text[index] == '\n': line += 1
            else: clean[index] = ' '
            index += 1; continue
        if text.startswith('$*', index):
            while index < len(text) and text[index] != '\n':
                clean[index] = ' '; index += 1
            continue
        char = text[index]
        if char == '$' and re.match(r'\$[ \t]*\n', text[index:]):
            while text[index] != '\n': clean[index] = ' '; index += 1
            clean[index] = ' '; index += 1; line += 1; continue
        if char.isspace() or char == ',':
            if char in '\n,' and tokens:
                statements.append(tokens); tokens = []
            if char == '\n': line += 1
            index += 1; continue
        start, start_line = index, line
        quote, brackets = None, []
        while index < len(text):
            char = text[index]
            if quote:
                if char == quote:
                    if index + 1 < len(text) and text[index + 1] == quote:
                        index += 2; continue
                    quote = None
                if char == '\n': line += 1
                index += 1; continue
            if char in "'\"|": quote = char
            elif text.startswith('$*', index) or text.startswith('$(', index):
                if brackets: raise MacroImportError(line, '式内のコメントは式の外へ移してください。')
                break
            elif char in '([':
                brackets.append(char)
                if len(brackets) > 40: raise MacroImportError(line, '式の入れ子が深すぎます。')
            elif char in ')]':
                if not brackets or brackets.pop() != {')':'(', ']':'['}[char]:
                    raise MacroImportError(line, '括弧が一致しません。')
            elif not brackets and (char.isspace() or char == ','): break
            if char == '\n': line += 1
            index += 1
        if quote or brackets: raise MacroImportError(start_line, '引用符または括弧を閉じてください。')
        raw = text[start:index]
        attached = re.fullmatch(r'(PAXI|PLAXI|PTCDIR|PTCD)(-[XYZ])', raw, re.IGNORECASE)
        if attached:
            boundary = start + len(attached[1])
            tokens.extend((Token(attached[1], start, boundary, start_line), Token(attached[2], boundary, index, start_line)))
        else: tokens.append(Token(raw, start, index, start_line))
        count += 1
        if count > 100000:
            raise MacroImportError(line, 'テキストが複雑すぎます。ファイルを分割してください。')
    if block: raise MacroImportError(line, 'ブロックコメントを閉じてください。')
    if tokens: statements.append(tokens)
    return ''.join(clean), statements


def _literal(text):
    if len(text) >= 2 and text[0] in "'\"|" and text[-1] == text[0]:
        return text[1:-1].replace(text[0] * 2, text[0])
    return text


def parse(text):
    """Extract NEW sets; errors prevent all import, never run or expand PML."""
    source, statements = _statements(text)
    definitions, warnings, stack = [], [], []
    active, root, footer, old_target, finished, blocks = False, None, False, None, False, 0
    destination = ''
    seen = set()
    def warn(line, message):
        item = f'{line}行目：{message}'
        if item not in seen: seen.add(item); warnings.append(item)
    for tokens in statements:
        words = [item.text for item in tokens]
        upper = [word.upper() for word in words]
        first = upper[0]
        if finished:
            raise MacroImportError(tokens[0].line, 'INPUT FINISHの後に命令があります。')
        if first.startswith('/'):
            if len(words) != 1 or active or stack:
                raise MacroImportError(tokens[0].line, '登録先の選択はセット作成前に /名前 だけの行で指定してください。')
            try: destination = macro_destinations.normalize(words[0])
            except ValueError as exc: raise MacroImportError(tokens[0].line, str(exc)) from exc
            continue
        if first == 'INPUT':
            line = tokens[0].line
            if upper == ['INPUT', 'BEGIN']:
                if active or stack: raise MacroImportError(line, 'INPUT BEGINの前のセットを閉じてください。')
                active, root, footer, old_target = True, None, False, None
            elif len(words) == 4 and upper[1] == 'END':
                kind = TYPE_ALIASES.get(upper[2], upper[2])
                if not active or root is None or stack or old_target is not None or kind != root['kind'] or words[3] != root['name']:
                    raise MacroImportError(line, 'INPUT ENDの型・名前・NEW/ENDの対応を確認してください。')
                active, root, footer = False, None, False
                blocks += 1
            elif upper == ['INPUT', 'FINISH']:
                if active or stack or not blocks: raise MacroImportError(line, 'INPUT ENDでセットを閉じてからINPUT FINISHを指定してください。')
                finished = True
            else: raise MacroImportError(line, '未対応のINPUT形式です。')
            continue
        if first in ('OLD', 'LOCK'):
            line = tokens[0].line
            if first == 'LOCK' and len(words) == 1 and stack and not footer and not stack[-1].get('wrapper'):
                stack[-1]['macro_locked'] = True
                continue
            if not active or root is None or stack:
                raise MacroImportError(line, 'OLD・LOCKはINPUT内の作成完了後だけ読み込めます。')
            footer = True
            if first == 'OLD':
                if old_target is not None: raise MacroImportError(line, 'OLDの後にLOCKが必要です。')
                try: old_target = alp.resolve_old(words[1:], root, TYPE_ALIASES)
                except ValueError as exc: raise MacroImportError(line, str(exc)) from exc
            else:
                if len(words) != 1 or old_target is None: raise MacroImportError(line, 'LOCKには直前のOLDによる対象指定が必要です。')
                old_target['macro_locked'] = True
                old_target = None
            continue
        if footer:
            raise MacroImportError(tokens[0].line, 'ロック指定後はINPUT ENDで閉じてください。')
        pos = 0
        while pos < len(tokens):
            token = tokens[pos]; command = token.text.upper(); pos += 1
            if command == 'NEW':
                if pos >= len(tokens): raise MacroImportError(token.line, 'NEWの後に要素型が必要です。')
                kind_token = tokens[pos]; pos += 1
                kind = TYPE_ALIASES.get(kind_token.text.upper(), kind_token.text.upper())
                name = ''
                if pos < len(tokens) and tokens[pos].text.startswith('/'):
                    name = tokens[pos].text; pos += 1
                if kind in WRAPPERS:
                    if stack and stack[-1].get('kind') not in WRAPPERS:
                        stack = [frame for frame in stack if frame.get('kind') in WRAPPERS]
                    while stack and stack[-1]['kind'] not in WRAPPERS[kind]: stack.pop()
                    stack.append({'kind':kind, 'attrs':{}, 'wrapper':True})
                    warn(token.line, kind + 'の所有階層・属性は取り込みません。')
                    continue
                if kind in SET_TYPES:
                    if active and root is not None: raise MacroImportError(token.line, 'INPUT BEGINごとに1セットを指定してください。')
                    stack = [frame for frame in stack if frame.get('wrapper')]
                    if len(definitions) >= 1000: raise MacroImportError(token.line, '定義数の上限です。')
                    if not name:
                        name = f'/IMPORTED-{kind}-{len(definitions) + 1}'
                        warn(token.line, '無名のセットに表示名を付けました：' + name)
                    record = {'id':uuid.uuid4().hex, 'kind':kind, 'name':name,
                              'revision':'01', 'attrs':{}, 'elements':[]}
                    if destination: record['macro_destination'] = destination
                    if active:
                        record['macro_locked'] = False
                        root = record
                    definitions.append(record); stack.append(record)
                    continue
                if not schema.known(kind):
                    raise MacroImportError(kind_token.line, '未対応の要素型です：' + kind_token.text)
                parent = None
                for index in range(len(stack) - 1, -1, -1):
                    frame = stack[index]
                    allowed = schema.TYPES_BY_SET.get(frame.get('kind'), ()) if 'elements' in frame else schema.allowed_children(frame.get('type'))
                    if kind in allowed:
                        parent = frame; stack = stack[:index + 1]; break
                if parent is None: raise MacroImportError(token.line, kind + 'を置ける親セット・要素がありません。')
                children = parent['elements'] if 'elements' in parent else parent.setdefault('children', [])
                if len(children) >= 200 or len(stack) > 9: raise MacroImportError(token.line, '要素数または階層の上限です。')
                record = {'id':uuid.uuid4().hex, 'type':kind, 'name':name or f'{kind} {len(children) + 1}', 'attrs':{}}
                if active: record['macro_locked'] = False
                children.append(record); stack.append(record)
            elif command == 'END':
                if not stack: raise MacroImportError(token.line, '対応するNEWがないENDです。')
                if pos < len(tokens) and tokens[pos].text.upper() in (*TYPE_ALIASES, *WRAPPERS):
                    raw = tokens[pos].text.upper(); pos += 1
                    kind = TYPE_ALIASES.get(raw, raw)
                    found = next((i for i in range(len(stack)-1, -1, -1) if stack[i].get('kind', stack[i].get('type')) == kind), None)
                    if found is None: raise MacroImportError(token.line, '対応するNEWがありません：END ' + raw)
                    stack = stack[:found]
                else: stack.pop()
            elif command == 'NAME':
                if not stack or stack[-1].get('wrapper') or pos >= len(tokens) or not tokens[pos].text.startswith('/'):
                    raise MacroImportError(token.line, 'NAMEには現在の要素と /名前 が必要です。')
                stack[-1]['name'] = tokens[pos].text; pos += 1
            else:
                if not stack: raise MacroImportError(token.line, 'NEWより前の命令は取り込めません：' + token.text)
                unset = command == 'UNSET'
                if unset:
                    if pos >= len(tokens): raise MacroImportError(token.line, 'UNSETの後に属性名が必要です。')
                    token = tokens[pos]; command = token.text.upper(); pos += 1
                if command in CONTROL or not re.fullmatch(r':?[A-Z][A-Z0-9_]*', command):
                    raise MacroImportError(token.line, '属性代入以外の命令は未対応です：' + token.text)
                key = ATTR_ALIASES.get(command, command)
                begin = pos
                if not unset:
                    if begin >= len(tokens): raise MacroImportError(token.line, command + 'の値がありません。')
                    if tokens[begin].text.upper() in COMMANDS | ATTR_ALIASES.keys():
                        raise MacroImportError(token.line, command + 'の値がありません。命令名を文字値にする場合は引用符で囲んでください。')
                    pos += 1
                    while pos < len(tokens) and tokens[pos].text.upper() not in COMMANDS | ATTR_ALIASES.keys(): pos += 1
                    raw = source[tokens[begin].start:tokens[pos - 1].end].strip()
                    for part in tokens[begin:pos]:
                        if part.text.upper() in CONTROL - {'MM','INCH','FINCH'} or (part.text[0] not in "'\"|" and re.search(r'[!$;]', part.text)):
                            raise MacroImportError(part.line, '変数・制御命令・外部マクロの展開は未対応です。')
                else: raw = ''
                target = stack[-1]
                if target.get('wrapper'): continue
                fields = schema.PARENT_FIELDS[target['kind']] if 'kind' in target else tuple(k for section in ('main','detail','common','negative') for k in schema.fields(target['type'], section))
                if command in fields: key = command
                elif key == 'PDIA' and 'PDIAM' in fields: key = 'PDIAM'
                if key not in fields:
                    warn(token.line, command + 'は原文属性として保持します（未対応の属性は読み取り専用）。')
                if key in target['attrs']: warn(token.line, command + 'の再代入は最後の値を採用します。')
                # Text delimiters are syntax, while expression parentheses are stored verbatim.
                target['attrs'][key] = _literal(raw) if key in ('DESC','PURP') else raw
    if active: raise MacroImportError(statements[-1][0].line, 'INPUT ENDがありません。')
    if blocks and not finished: raise MacroImportError(statements[-1][0].line, 'INPUT FINISHがありません。')
    if not definitions: raise ValueError('NEW PTSET /名前 または NEW GMSET /名前 で始まる定義がありません。')
    for definition in definitions: project.validate_elements(definition['elements'])
    return ParsedMacro(definitions, warnings)


def prepare_import(data, parsed, selected):
    """Make a validated candidate; no existing records or source objects are changed."""
    selected = set(selected)
    originals = [record for record in parsed.definitions if record['id'] in selected]
    if not originals: raise ValueError('取り込む定義を選択してください。')
    if selected - {record['id'] for record in parsed.definitions}: raise ValueError('読込対象が変更されています。再解析してください。')
    if len(data['definitions']) + len(originals) > project.LIMITS['definitions']: raise ValueError('定義数の上限です。')
    candidate = copy.deepcopy(data)
    preset_names = {p['name'].casefold() for p in candidate.get('parameter_presets', [])}
    base = 'マクロ読込・PARAM規則未設定'; name = base; number = 2
    while name.casefold() in preset_names: name = f'{base} {number}'; number += 1
    rule = presets.add(candidate, name, empty=True)
    used = {record['name'].casefold() for collection in ('cates','definitions','scoms','specs','texts','tables','catalog_details','catalog_props') for record in candidate.get(collection, [])}
    added, renamed = [], []
    for original in originals:
        record = copy.deepcopy(original)
        record['id'] = uuid.uuid4().hex
        for element in schema.walk(record['elements']): element['id'] = uuid.uuid4().hex
        base = record['name']; name = base; number = 2
        while name.casefold() in used: name = f'{base}-IMPORT-{number}'; number += 1
        if name != base: renamed.append((base, name))
        used.add(name.casefold()); record['name'] = name
        record['parameter_preset_id'] = rule['id']
        candidate['definitions'].append(record); added.append(record)
    project.validate(candidate)
    return candidate, added, renamed
