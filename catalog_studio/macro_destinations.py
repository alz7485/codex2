"""Project-wide creation destinations, independent for PTSET and GMSET."""
import re

KEY = 'macro_destinations'
LIST_KEY = 'macro_destination_lists'
KINDS = ('PTSET', 'GMSET', 'CATE')


def normalize(value, *, strict=True):
    if not isinstance(value, str):
        raise ValueError('登録先は名前を文字列で指定してください。')
    value = value.strip()
    if value and not value.startswith('/'):
        value = '/' + value
    if strict and value and (len(value) > 1000 or not re.fullmatch(r'/[^\s,\'"|!$;()\[\]\\]+', value)):
        raise ValueError('登録先は空白・改行・命令区切りなしの /名前 で指定してください。')
    return value


def validate_storage(data):
    values = data.get(KEY, {})
    if not isinstance(values, dict) or any(key in values and (not isinstance(values[key], str) or len(values[key]) > 1000) for key in KINDS):
        raise ValueError('PTSET・GMSETの登録先は1000文字以内の文字列で保存してください。')
    lists=data.get(LIST_KEY,{})
    if not isinstance(lists,dict):raise ValueError('登録先リストの形式が不正です。')
    for kind in KINDS:
        if kind in lists:
            rows=lists[kind]
            if not isinstance(rows,list) or any(not isinstance(v,str) or not v or normalize(v)!=v for v in rows) or len(set(rows))!=len(rows):
                raise ValueError('登録先リストは重複のない /名前 の一覧で保存してください。')


def get(data, kind):
    validate_storage(data)
    return data.get(KEY, {}).get(kind, '')


def options(data,kind):
    validate_storage(data)
    if kind in data.get(LIST_KEY,{}):return list(data[LIST_KEY][kind])
    old=normalize(get(data,kind))
    return [old] if old else []


def save_options(data,kind,values):
    rows=list(dict.fromkeys(normalize(v) for v in values if v.strip()))
    data.setdefault(LIST_KEY,{})[kind]=rows
    data.setdefault(KEY,{})[kind]=rows[0] if rows else ''
    return rows
