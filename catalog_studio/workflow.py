"""Tool-only roles, linked preview state and catalogue parameter context."""
import copy
import re
from . import project, presets, pairing, element_schema as schema

POINT_ROLES=('', '入口', '出口', '分岐', '補助')


def linked_sets(data,definition):
    if not definition:return []
    profile=presets.selected_id(data,definition)
    group={definition['id']:definition}
    changed=True
    while changed:
        changed=False
        for gm in data['definitions']:
            if gm['kind']!='GMSET' or presets.selected_id(data,gm)!=profile:continue
            pt=pairing.resolve(data,gm)['pointset']
            if not pt or presets.selected_id(data,pt)!=profile:continue
            if gm['id'] in group or pt['id'] in group:
                for record in (pt,gm):
                    if record['id'] not in group:group[record['id']]=record;changed=True
    return list(group.values())


def share_dimensions(data,definition,state):
    from .point_geometry import validate_dimensions, DIMENSIONS_KEY
    validate_dimensions(state)
    for record in linked_sets(data,definition):record[DIMENSIONS_KEY]=copy.deepcopy(state)


def apply_preview(data,definition,settings,state):
    from .model_settings import validate
    validate(settings)
    share_dimensions(data,definition,state)
    for record in linked_sets(data,definition):record['model_settings']=copy.deepcopy(settings)


def preferred_presets(data,records,pointset=None):
    if not pointset:return list(records)
    ident=presets.selected_id(data,pointset)
    return sorted(records,key=lambda r:presets.selected_id(data,r)!=ident)


def parameter_rows(data,scom):
    """Prefer explicit TEXT provenance; fallback only to unambiguous PARAM names."""
    profile=presets.selected_id(data,scom);rows=[]
    texts=[t for t in data.get('texts',[]) if t['type']=='TEXT' and t['parent_id']==scom['cate_id']]
    for p in presets.rules(data,scom):
        pid=p['id']
        matches=[t for t in texts if t.get('parameter_text_source',{}).get('preset_id')==profile and t.get('parameter_text_source',{}).get('parameters')==pid]
        if not matches:
            matches=[t for t in texts if not t.get('parameter_text_source') and re.search(r'(?:/PARAM|/PA)'+pid[1:]+r'(?:$|[-_])',t['name'],re.I)]
        text=matches[0] if len(matches)==1 else None
        rows.append(dict(pid=pid,meaning=presets.meaning(p),text=text['attrs'].get('STEXT','') if text else p.get('english_name',''),
                         source=text['name'] if text else 'PARAM定義',unit=p.get('unit',''),value_type=p.get('value_type','number'),value=scom['values'].get(pid,'未入力')))
    return rows


def shape_group(node):
    if node['type'] in schema.NEGATIVE_BASE:return '負形状'
    if schema.positive(node['type']) in ('LINE','SLINE'):return '中心線'
    return node.get('preview_group','本体')


def filter_scene(scene,definition,enabled):
    """Filter drawing only, after Boolean evaluation, preserving subtraction."""
    nodes={n['id']:n for n in schema.walk((definition or {}).get('elements',[]))}
    scene.meshes=[m for m in scene.meshes if shape_group(nodes.get(m.ident,{'type':m.kind})) in enabled]
    return scene
