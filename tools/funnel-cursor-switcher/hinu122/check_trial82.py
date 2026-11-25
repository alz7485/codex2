from pathlib import Path
import numpy as np, trimesh, json
from rig_trial61 import read_glb,matrix
from audit_trial61 import poly,vtkmat
import vtk
from itertools import combinations
R=Path(__file__).resolve().parent

def group(s,n):
 while n in s.graph.transforms.parents:
  n=s.graph.transforms.parents[n]
  if n in ('Port hinge rig','Starboard hinge rig'):return n.split()[0]
 return 'Fixed'
def audit(kind):
 path=R/f'{kind}_Trial82.glb';s=trimesh.load(path,force='scene',process=False);parts={};groups={}
 for n in s.graph.nodes_geometry:
  t,g=s.graph[n];m=s.geometry[g].copy();m.apply_transform(t);gr=group(s,n);parts[n]=(m,poly(m),gr);groups.setdefault(gr,[]).append(n)
 pairs=[(a,b) for ga,gb in combinations(groups,2) for a in groups[ga] for b in groups[gb] if any(n.startswith(('T81','T82')) for n in (a,b))]
 report=[]
 for deg in range(0,91,5):
  mats={'Fixed':np.eye(4),'Port':matrix('Port',deg),'Starboard':matrix('Starboard',-deg)};vm={g:vtkmat(t) for g,t in mats.items()};bounds={}
  for n,(m,p,gr) in parts.items():
   v=trimesh.transform_points(m.vertices,mats[gr]);bounds[n]=(v.min(0),v.max(0))
  found=[];candidates=0
  for a,b in pairs:
   lo,hi=bounds[a];l,h=bounds[b]
   if np.any(hi<l) or np.any(h<lo):continue
   candidates+=1;f=vtk.vtkCollisionDetectionFilter();f.SetInputData(0,parts[a][1]);f.SetInputData(1,parts[b][1]);f.SetMatrix(0,vm[parts[a][2]]);f.SetMatrix(1,vm[parts[b][2]]);f.SetCollisionModeToFirstContact();f.SetBoxTolerance(0);f.SetCellTolerance(0);f.GenerateScalarsOff();f.Update()
   if f.GetNumberOfContacts():found.append([a,b])
  report.append({'angle':deg,'candidates':candidates,'contacts':found,'t82_contacts':[x for x in found if any(n.startswith('T82') for n in x)]})
 j,b=read_glb(path);old,_=read_glb(R/f'{kind}_Trial81.glb'); data={'method':'Cross-group AABB + VTK triangle surface contact; only pairs involving T81/T82 additions, 0–90 deg sampled in 5 deg steps; no continuous sweep/containment guarantee','mesh_nodes_old':sum('mesh' in n for n in old['nodes']),'mesh_nodes_new':sum('mesh' in n for n in j['nodes']),'poses':report,'t82_contact_pairs_total':sum(len(r['t82_contacts']) for r in report),'all_contact_pairs_total':sum(len(r['contacts']) for r in report)}
 (R/f'{kind}_interference82.json').write_text(json.dumps(data,indent=2));print(kind,{k:v for k,v in data.items() if k not in ('poses','method')},flush=True)
if __name__=='__main__':
 for kind in ('HiNu','HiNu_HWS'):audit(kind)
