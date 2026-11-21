"""Synthetic ready-to-edit piping catalogues using the separate builtin presets."""
import copy
import uuid
from . import project, presets, element_library, catalogue, parameter_catalog
from .piping_presets import add_presets, PARAMETERS


def add_samples(data):
    """Add missing component samples atomically, preserving existing user records."""
    candidate=copy.deepcopy(data)
    add_presets(candidate)
    added=0
    used={r['name'] for key in ('definitions','cates','scoms','texts') for r in candidate.get(key,[])}
    def name(base):
        value=base;n=2
        while value in used:value=base+'-'+str(n);n+=1
        used.add(value);return value
    for component in PARAMETERS:
        marker='piping-'+component.lower()
        if any(c.get('sample')==marker for c in candidate['cates']):continue
        profile=presets.get(candidate,'builtin-piping-param-'+component.lower())
        def definition(kind):
            record=dict(id=uuid.uuid4().hex,name=name(('/PT-' if kind=='PTSET' else '/GM-')+'SAMPLE-'+component),
                        kind=kind,revision='01',elements=[],sample=marker)
            element_library.recall(candidate,record,'builtin-piping-'+component.lower()+'-'+kind.lower(),replace=True)
            candidate['definitions'].append(record)
            return record
        pt=definition('PTSET');gm=definition('GMSET') if component=='BEND' else None
        if gm:gm['paired_ptset_id']=pt['id']
        cate=project.add_cate(candidate,name('/SAMPLE-'+component+'-CATE'))
        cate.update(sample=marker,description=component+' 編集用サンプル（寸法は自作参考値）',attrs={'PURP':'COMP'})
        sdte=catalogue.add_record(candidate,'texts','SDTE',name(cate['name']+'/SDTE'),cate['id'])
        sdte['attrs'].update(SKEY={'PIPE':'','WELD':'WS','BEND':'PB+D'}[component],
                             RTEX=pt['name'].lstrip('/')+' '+(gm['name'].lstrip('/') if gm else 'GNULREF'))
        # The preset's English labels retain the PARAM descriptions from CATE TEXT.
        texts=parameter_catalog.write_texts(candidate,profile,cate['id'])
        for record in texts:record['sample']=marker
        scom=project.add_scom(candidate,cate['id'],name('/SAMPLE-'+component+'-40'))
        values={'PIPE':{'P1':40.,'P2':48.6,'P3':'TUB'},
                'WELD':{'P1':40.,'P2':'TUB','P3':'TUB'},
                'BEND':{'P1':40.,'P2':48.6,'P3':'TUB','P4':150.}}[component]
        scom.update(sample=marker,size='',parameter_preset_id=profile['id'],ptset_id=pt['id'],
                    gmset_id=gm['id'] if gm else '',values=values,attrs={'GTYP':'TUBE' if component=='PIPE' else component})
        if gm:
            scom['component_attrs']={'ANGL':90.}
            # Preview-only dimensions; these do not export as catalogue attributes.
            state={'scale':.01,'values':{'PARAM':{k:v for k,v in values.items() if isinstance(v,float)},'IPARAM':{'P1':0.}},'expressions':[]}
            for definition in (pt,gm):definition['schematic_dimensions']=copy.deepcopy(state)

        added+=1
    project.validate(candidate)
    data.clear();data.update(candidate)
    return added
