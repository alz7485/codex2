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
    from . import workflow, presets
    from .point_preview import PointPreview
    from .geometry_preview import GeometryPreview
    definition=editor.definition()
    if not definition or not editor.commit_inline():return
    data=editor.data
    group=workflow.linked_sets(data,definition)
    model=PointPreview(data,definition) if definition['kind']=='PTSET' else GeometryPreview(data,definition)
    state=model.snapshot()
    fields=[(key,label+('（度）' if dim=='ANGL' else '（mm）'),definition.get('model_settings',{}).get(key,''),None) for key,(label,dim) in FIELDS.items()]
    numbers=[p for p in presets.rules(data,definition) if p.get('value_type','number')=='number']
    for p in numbers:
        value=state['values'].get('PARAM',{}).get(p['id'],'')
        fields.append((p['id'],p['id']+' '+presets.meaning(p)+'（仮値）',value,None))
    def apply(values):
        if editor.data is not data or editor.definition() is not definition or [d['id'] for d in workflow.linked_sets(data,definition)]!=[d['id'] for d in group]:raise ValueError('連携先が変更されています。開き直してください。')
        result=parse(values)
        import copy
        updated=copy.deepcopy(state);target=updated['values'].setdefault('PARAM',{})
        for p in numbers:
            text=values[p['id']].strip()
            if not text:target.pop(p['id'],None);continue
            value=expressions.evaluate(text)
            if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>1e100:raise ValueError(p['id']+' は有限の数値で入力してください。')
            target[p['id']]=value
        # Old whole-expression fallbacks must not override newly supplied values.
        updated['expressions']=[]
        workflow.apply_preview(data,definition,result,updated)
        editor.host.mark('連携する '+str(len(group))+' セットの確認用設計値・仮PARAMを更新しました。')
        editor.draw();editor.redraw_points();editor.update_validation()
    return editor.host.form('連携'+str(len(group))+'セットの仮寸法・設計値（SCOM実値は変更しません）',fields,apply)
