"""Material-only brushup of approved Hi-Nu meshes; never regenerate the geometry."""
from pathlib import Path
from copy import deepcopy
import hashlib,json
from .rig_trial61 import read_glb,write_glb
R=Path(__file__).resolve().parent
MODELS={k:f'{k}_Trial188.glb' for k in ('HiNu','HiNu_HWS')}

def finish(name,p):
    # Keep all base colors, including HWS gradient, exactly intact.
    if 'external armour' in name or name.endswith((' main',' pale',' transition',' tip')) or 'violet_band_' in name or 'root marking' in name or 'tip inset' in name:
        return .19,.32
    if 'internal frame' in name or 'hinge cover' in name or name=='Pale mechanism':
        return .78,.30
    if name in ('Pivot steel','T81 polished edge'):
        return .90,.19
    if name in ('Deep recess','Trial59 dark','Trial60 black','T62 • ceramic throat','T81 graphite recess'):
        return min(p.get('metallicFactor',0),.30),.53
    if name in ('T81 machined titanium','T83 machined aperture bevel','T85 machined titanium liner','T62 • machined nozzle rim','Trial60 titanium','Trial60 steel'):
        return .86,.28
    if name=='T85 satin heat fins':return .76,.39
    return None

def build():
    results={}
    for kind,filename in MODELS.items():
        old,buf=read_glb(R/f'{kind}_Trial119.glb');new=deepcopy(old);changes=[]
        for m in new['materials']:
            p=m['pbrMetallicRoughness'];v=finish(m['name'],p)
            if v is None:continue
            before=[p.get('metallicFactor',1),p.get('roughnessFactor',1)]
            if list(v)==before:continue
            p['metallicFactor'],p['roughnessFactor']=v
            changes.append({'name':m['name'],'before':before,'after':list(v)})
        write_glb(R/filename,new,bytearray(buf))
        loaded,b=read_glb(R/filename)
        assert b==buf
        assert {k:v for k,v in loaded.items() if k!='materials'}=={k:v for k,v in old.items() if k!='materials'}
        for a,z in zip(old['materials'],loaded['materials']):
            def unchanged(m):
                m=deepcopy(m);m['pbrMetallicRoughness'].pop('metallicFactor',None);m['pbrMetallicRoughness'].pop('roughnessFactor',None);return m
            assert unchanged(a)==unchanged(z)
        results[kind]={'meshes':len(old['meshes']),'nodes':len(old['nodes']),'material_changes':changes,'binary_equal':True,'geometry_and_rig_equal':True,'base_colors_equal':True,'sha256':hashlib.sha256((R/filename).read_bytes()).hexdigest()}
    (R/'trial188'/'model_audit.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
    return results
if __name__=='__main__':
    for k,v in build().items():print(k,v['meshes'],len(v['material_changes']))
