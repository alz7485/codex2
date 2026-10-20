"""Project-wide creation destinations, independent for PTSET and GMSET."""
import re

KEY = 'macro_destinations'
KINDS = ('PTSET', 'GMSET')


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


def get(data, kind):
    validate_storage(data)
    return data.get(KEY, {}).get(kind, '')
