"""Serialize selected definitions as declarative creation text, never execute it."""
import os
import re
import tempfile
from pathlib import Path

from . import element_schema as schema, macro_import


def _name(value):
    if not isinstance(value, str) or not re.fullmatch(r'/[^\s,\'"|!$;()\[\]\\]+', value):
        raise ValueError('作成マクロの名前は / で始まる空白・命令区切りなしの名前にしてください：' + str(value))
    return value


def _attrs(attrs, kind):
    result = {}
    fields = schema.PARENT_FIELDS.get(kind, ()) if kind in schema.TYPES_BY_SET else tuple(key for section in ('main', 'detail', 'common', 'negative') for key in schema.fields(kind, section))
    for key, value in attrs.items():
        if not isinstance(key, str) or not re.fullmatch(r':?[A-Z][A-Z0-9_]*', key):
            raise ValueError('出力できない属性名です：' + str(key))
        if key in macro_import.CONTROL | macro_import.COMMANDS:
            raise ValueError('属性名として出力できない命令です：' + key)
        if not isinstance(value, (str, int, float, bool)):
            raise ValueError(key + 'の値を文字列または数値で指定してください。')
        raw = ('TRUE' if value else 'FALSE') if isinstance(value, bool) else str(value)
        if key not in ('DESC', 'PURP'):
            raw = raw.strip()
        if not raw or raw.lower() == 'unset':
            continue
        # Control characters and multiline source must not introduce commands.
        if any(ord(char) < 32 or ord(char) == 127 for char in raw):
            raise ValueError(key + 'の改行・制御文字を除いてから出力してください。')
        canonical = key if key in fields else macro_import.ATTR_ALIASES.get(key, key)
        if canonical == 'PDIA' and 'PDIAM' in fields:
            canonical = 'PDIAM'
        if canonical in result:
            raise ValueError('同じ属性の別名が重複しています：' + key)
        result[canonical] = raw
    return result


def creation_text(definitions):
    """Export PTSET/GMSET and ordered children; exclude all preview metadata.

    A parser round trip additionally rejects ambiguous raw attribute values.
    This validates preservation, not E3D runtime compatibility.
    """
    if not definitions:
        raise ValueError('出力するセットを選んでください。')
    lines = ['$* Catalog Studio: creation text; E3D runtime verification pending.',
             '$* Select the intended catalogue owner before running. Existing names are not replaced.', '']
    expected = []
    names = set()

    def emit(record, kind, allowed, depth=0):
        if depth > 9 or kind not in allowed:
            raise ValueError('この親から出力できない要素型です：' + str(kind))
        name = record.get('name', '')
        formal_name = _name(name) if depth == 0 or name.startswith('/') else ''
        if formal_name:
            if formal_name in names:
                raise ValueError('出力する要素名が重複しています：' + formal_name)
            names.add(formal_name)
        lines.append('NEW ' + kind + (' ' + formal_name if formal_name else ''))
        attrs = _attrs(record.get('attrs', {}), kind)
        for key, value in attrs.items():
            encoded = "'" + value.replace("'", "''") + "'" if key in ('DESC', 'PURP') else value
            lines.append(key + ' ' + encoded)
        children = record.get('elements' if depth == 0 else 'children', [])
        if len(children) > 200:
            raise ValueError('1セット・親要素につき200要素以内にしてください。')
        normalized = []
        for child in children:
            normalized.append(emit(child, child.get('type'), schema.TYPES_BY_SET[kind] if depth == 0 else schema.allowed_children(kind), depth + 1))
        lines.append('END')
        return (kind, formal_name, attrs, normalized)

    for definition in definitions:
        expected.append(emit(definition, definition.get('kind'), ('PTSET', 'GMSET')))
        lines.append('')
    text = '\n'.join(lines)
    parsed = macro_import.parse(text)

    def normalized(record, root=False):
        kind = record['kind'] if root else record['type']
        name = record['name'] if root or record['name'].startswith('/') else ''
        return (kind, name, record['attrs'], [normalized(child) for child in record.get('elements' if root else 'children', [])])

    if [normalized(record, True) for record in parsed.definitions] != expected:
        raise ValueError('属性値をそのまま保持できません。命令区切り・コメント・引用符を確認してください。')
    return text


def save(path, text):
    """Write Shift-JIS (CP932) strictly and atomically, retaining existing files."""
    destination = Path(path)
    normalized = text.replace('\r\n', '\n').replace('\n', '\r\n')
    try:
        raw = normalized.encode('cp932', errors='strict')
    except UnicodeEncodeError as exc:
        unsupported = normalized[exc.start:exc.end]
        raise ValueError('Shift-JIS（CP932）で表現できない文字があります：' + repr(unsupported) + '。文字を変更してから保存してください。') from exc
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.catalog-macro-', delete=False) as stream:
            temporary = stream.name
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
