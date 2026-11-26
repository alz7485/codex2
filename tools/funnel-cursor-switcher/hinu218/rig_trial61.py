"""Rig the original GLB without changing any mesh or material buffer. Python 3 + numpy + trimesh."""
from pathlib import Path
import struct,json,math
import numpy as np
import trimesh
R=Path(__file__).resolve().parent; D=R/'trial61'; SRC=R/'trial60/fin-funnel-trial60.glb'
PIVOTS={'Port':np.array([-.84,0,3.16]),'Starboard':np.array([.84,0,3.16])}
def group(name):
    side=name.split(' / ')[0]
    if side not in PIVOTS or any(x in name for x in (' / pivot',' / hinge cheek',' / T59 pivot',' / T60 hinge')):return 'Fixed'
    return side

def rest_adjust(name):
    if ' / T60 hinge' not in name:return np.eye(4)
    side=name.split(' / ')[0];sign=-1 if side=='Port' else 1
    # Move surface-mounted hardware from outward cheek face onto rear cheek face.
    t=trimesh.transformations.rotation_matrix(math.radians(-sign*90),[0,1,0],point=[sign*1.056,0,3.21]);t[:3,3]+=np.array([sign*(.84-1.056),0,3.465-3.21]);return t

def matrix(side,deg):
    if side=='Fixed':return np.eye(4)
    return trimesh.transformations.rotation_matrix(math.radians(deg),[0,1,0],point=PIVOTS[side])

def read_glb(path):
    b=path.read_bytes(); magic,ver,total=struct.unpack_from('<4sII',b);assert magic==b'glTF' and ver==2 and total==len(b)
    n,typ=struct.unpack_from('<I4s',b,12); assert typ==b'JSON';j=json.loads(b[20:20+n]);size,typ=struct.unpack_from('<I4s',b,20+n);assert typ==b'BIN\0';return j,bytearray(b[28+n:28+n+size])
def write_glb(path,j,b):
    jj=json.dumps(j,separators=(',',':'),ensure_ascii=False).encode();jj+=b' '*(-len(jj)%4);b+=b'\0'*(-len(b)%4)
    path.write_bytes(struct.pack('<4sII',b'glTF',2,28+len(jj)+len(b))+struct.pack('<I4s',len(jj),b'JSON')+jj+struct.pack('<I4s',len(b),b'BIN\0')+b)

def main():
    D.mkdir(exist_ok=True);j,b=read_glb(SRC);scene=trimesh.load(SRC,force='scene',process=False)
    nodes=j['nodes']; index={n['name']:i for i,n in enumerate(nodes) if 'mesh' in n};assert set(index)==set(scene.graph.nodes_geometry)
    # Flatten the old identity parents, rebuild with 3 rigid groups. Mesh-local transforms stay exact in world at rest.
    fixed=[];arms={k:[] for k in PIVOTS}; piv={}
    for name,i in index.items():
        world,_=scene.graph[name]; side=group(name);local=rest_adjust(name)@world
        if side!='Fixed':local[:3,3]-=PIVOTS[side];arms[side].append(i)
        else:fixed.append(i)
        n=nodes[i];n.pop('translation',None);n.pop('rotation',None);n.pop('scale',None);n['matrix']=local.T.flatten().tolist()
    for n in nodes:
        if 'mesh' not in n:n.pop('children',None)
    for side,children in arms.items():
        piv[side]=len(nodes);nodes.append({'name':side+' hinge rig','translation':PIVOTS[side].tolist(),'rotation':[0,0,0,1],'children':children})
    root=len(nodes);nodes.append({'name':'Fin Funnel Trial61 rigid assembly','children':fixed+list(piv.values())});j['scenes']=[{'nodes':[root]}];j['scene']=0
    def accessor(values,typ):
        a=np.asarray(values,dtype='<f4');b.extend(b'\0'*(-len(b)%4));off=len(b);data=a.tobytes();b.extend(data);v=len(j['bufferViews']);j['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':len(data)});n=len(j['accessors']);acc={'bufferView':v,'componentType':5126,'count':len(a),'type':typ};
        if typ=='SCALAR':acc.update(min=[float(a.min())],max=[float(a.max())])
        j['accessors'].append(acc);return n
    def clip(name,keys):
        # Bake smoothstep at 30 Hz. Avoid quaternion wrap (all angles within +/-90 deg).
        ts=[];a=[]
        for (t0,v0),(t1,v1) in zip(keys,keys[1:]):
            count=max(1,round((t1-t0)*30))
            for k in range(count):
                u=k/count;s=u*u*(3-2*u);ts.append(t0+(t1-t0)*u);a.append(v0+(v1-v0)*s)
        ts.append(keys[-1][0]);a.append(keys[-1][1]);time=accessor(ts,'SCALAR');sam=[];ch=[]
        for side,sign in [('Port',1),('Starboard',-1)]:
            half=np.radians(np.array(a)*sign)*.5; q=np.column_stack((np.zeros(len(a)),np.sin(half),np.zeros(len(a)),np.cos(half)));sam.append({'input':time,'output':accessor(q,'VEC4'),'interpolation':'LINEAR'});ch.append({'sampler':len(sam)-1,'target':{'node':piv[side],'path':'rotation'}})
        return {'name':name,'samplers':sam,'channels':ch}
    j['animations']=[clip('Combat flare 0-30-0',[(0,0),(.35,0),(1.15,30),(1.55,30),(2.35,0),(2.7,0)]),clip('Straight rack to combat and back',[(0,90),(.35,90),(1.8,0),(2.25,0),(3.7,90),(4.05,90)])]
    j['buffers'][0]['byteLength']=len(b);out=D/'fin-funnel-trial61-rigged.glb';write_glb(out,j,b)
    check=trimesh.load(out,force='scene',process=False);assert set(check.graph.nodes_geometry)==set(index)
    for name in index:
        ta,ga=scene.graph[name];tb,gb=check.graph[name];assert np.allclose(rest_adjust(name)@ta,tb,atol=1e-7),name;assert np.array_equal(scene.geometry[ga].vertices,check.geometry[gb].vertices),name
    print('expected rest transforms and vertices verified',len(index),'fixed',len(fixed),'arms',{k:len(v) for k,v in arms.items()})
    (D/'rig.json').write_text(json.dumps({'axis':'glTF +Y (Blender +Z)','pivot':{k:v.tolist() for k,v in PIVOTS.items()},'fixed':[nodes[i]['name'] for i in fixed],'arms':{k:[nodes[i]['name'] for i in v] for k,v in arms.items()},'clips':[x['name'] for x in j['animations']],'legacy_folded_pose':{'port':-82,'starboard':-90,'status':'not animated; legacy storage pose requires separate interference check'}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
