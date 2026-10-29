"""Dimensions tied to actual GMSET attributes and their PARAM expressions."""
from . import geometry_scene as geo,element_schema as schema,expressions,presets,project,pairing


def measurements(view):
    if not view.scene.actual:return []
    e=view.editor;definition=e.definition()
    if not definition:return []
    scom=project.get(e.data,'scoms',e.preview_scom_id)
    pt=pairing.resolve(e.data,definition)['pointset']
    resolver=geo.Resolver(e.data,definition,pt,scom,True,geo.Scene(actual=True))
    visible={m.ident for m in view.scene.meshes if not m.negative}
    result=[]
    def add(node,key,start,end,diameter=False,expression=None):
        expr=str(expression if expression is not None else node['attrs'].get(key,'')).strip()
        if not expr:return
        try:
            tree=expressions.parse(expr,resolver.parameters)
            refs=expressions.refs(tree)
            ids=sorted({pid for family,pid in refs if family=='PARAM'},key=lambda p:int(p[1:]))
            if not ids:return
            value=resolver.number(expr,'DIST')
        except ValueError:return
        if abs(value)<1e-10:return
        names={p['id']:presets.meaning(p) for p in resolver.parameters}
        label=' / '.join(names.get(pid,pid) for pid in ids)
        result.append(dict(key='gm:'+node['id']+':'+key,label=label,expression=expr,
            value=abs(value),start=start,end=end,diameter=diameter,attribute=key))
    for node in schema.walk(definition['elements']):
        if node['id'] not in visible:continue
        kind=schema.positive(node['type']);attrs=node['attrs']
        try:
            if kind=='SBOX':
                center=tuple(resolver.value(node,k) for k in ('PX','PY','PZ'))
                for i,key in enumerate(('PXLE','PYLE','PZLE')):
                    half=geo.mul(geo.AXES[i],resolver.value(node,key)/2)
                    add(node,key,geo.sub(center,half),geo.add(center,half))
            elif kind in ('SCYL','LCYL','SCON','SDIS','SSPH','SSLC'):
                origin,axis=resolver.axis(attrs.get('PAXI',''),geo.AXES[0])
                if kind=='LCYL':low=resolver.value(node,'PBDI');high=resolver.value(node,'PTDI')
                elif kind=='SCON':low=0;high=resolver.value(node,'PDIS')
                else:
                    low=resolver.value(node,'PDIS');high=low+resolver.value(node,'PHEI') if kind in ('SCYL','SSLC') else low
                bottom=geo.add(origin,geo.mul(axis,low));top=geo.add(origin,geo.mul(axis,high))
                u,_=geo.frame(axis);radius=resolver.value(node,'PDIA')/2
                center=top if kind=='SCON' else bottom
                # SSLC diameter lies in the normal cross-section through the axis.
                add(node,'PDIA',geo.sub(center,geo.mul(u,radius)),geo.add(center,geo.mul(u,radius)),True)
                if kind in ('SCYL','SSLC'):add(node,'PHEI',bottom,top)
                elif kind=='SCON':add(node,'PDIS',bottom,top)
                elif kind=='LCYL':add(node,'LENGTH',bottom,top,expression='('+str(attrs.get('PTDI',''))+') - ('+str(attrs.get('PBDI',''))+')')
                if kind not in ('SCON','LCYL') and abs(low)>1e-10:add(node,'PDIS',origin,bottom)
        except (ValueError,TypeError):continue
    return result


def display_expression(view,text):
    e=view.editor;scom=project.get(e.data,'scoms',e.preview_scom_id) or {}
    parameters=presets.rules(e.data,e.definition() or scom)
    names={p['id']:presets.meaning(p) for p in parameters}
    if view.dimension_stext.get():
        names={}
        for p in parameters:
            records=[r for r in e.data.get('texts',[]) if r.get('type')=='TEXT' and r.get('parent_id')==scom.get('cate_id') and
                r.get('parameter_text_source',{}).get('preset_id')==presets.selected_id(e.data,scom) and
                r.get('parameter_text_source',{}).get('parameters')==p['id']]
            values={r.get('attrs',{}).get('STEXT','').strip() for r in records}-{''}
            if len(values)==1:names[p['id']]=next(iter(values))
    def replace(match):
        if match.group('quoted') is not None:return match[0]
        family=' '.join((match.group('family') or 'PARAM').upper().split())
        family=expressions.ALIASES.get(family,family)
        if family!='PARAM':return match[0]
        pid='P'+(match.group('bracket') or match.group('number') or match.group('short'))
        name=names.get(pid)
        display_id='PA'+pid[1:]
        return display_id+'（'+name.replace('\n',' ').replace('\r',' ')+'）' if name else display_id
    return presets._DISPLAY_REFERENCE.sub(replace,str(text))
