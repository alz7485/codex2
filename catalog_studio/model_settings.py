"""Tool-owned preview design values, separate from catalogue attributes and PARAM."""
import math
from . import expressions

FIELDS={'DDANGLE':('設計角度','ANGL'),'DDHEIGHT':('設計高さ','DIST'),
        'DDRADIUS':('設計半径','DIST'),'BORE':('確認用口径','DIST')}


def parse(values):
    result={}
    for key,(_,expected) in FIELDS.items():
        text=str(values.get(key,'')).strip()
        if not text:continue
        value=expressions.evaluate(text,expected=expected)
        if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>1e100:raise ValueError(key+' は有限の数値で指定してください。')
        result[key]=value
    return result


def validate(values):
    if not isinstance(values,dict) or any(k not in FIELDS or type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e100 for k,v in values.items()):
        raise ValueError('確認用設計値は角度（度）・距離（mm）の有限数値で保存してください。')


def edit(editor):
    definition=editor.definition()
    if not definition or not editor.commit_inline():return
    fields=[(key,label+('（度）' if dim=='ANGL' else '（mm）'),definition.get('model_settings',{}).get(key,''),None) for key,(label,dim) in FIELDS.items()]
    def apply(values):
        if editor.definition() is not definition:raise ValueError('セットが変わっています。開き直してください。')
        result=parse(values)
        definition['model_settings']=result
        editor.host.mark();editor.draw();editor.redraw_points();editor.update_validation()
    editor.host.form('確認用設計値（空欄は未設定・単位付き入力可）',fields,apply)
