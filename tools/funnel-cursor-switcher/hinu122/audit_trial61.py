"""Discrete cross-rigid-group surface contact audit (not solid containment or continuous sweep)."""
from rig_trial61 import *
import vtk
from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray
from itertools import combinations

def poly(m):
    p=vtk.vtkPolyData();pts=vtk.vtkPoints();pts.SetData(numpy_to_vtk(np.ascontiguousarray(m.vertices),deep=True));p.SetPoints(pts);c=vtk.vtkCellArray();f=np.ascontiguousarray(m.faces,dtype=np.int64);c.SetData(numpy_to_vtkIdTypeArray(np.arange(0,3*(len(f)+1),3,dtype=np.int64),deep=True),numpy_to_vtkIdTypeArray(f.ravel(),deep=True));p.SetPolys(c);return p

def vtkmat(a):
    m=vtk.vtkMatrix4x4();m.DeepCopy(a.ravel());return m

def main():
    s=trimesh.load(SRC,force='scene',process=False);parts={};groups={}
    for n in s.graph.nodes_geometry:
        t,g=s.graph[n];m=s.geometry[g].copy();m.apply_transform(rest_adjust(n)@t);parts[n]=(m,poly(m));groups.setdefault(group(n),[]).append(n)
    poses=[(a,-a) for a in range(0,91,5)]+[(-82,-90)];report=[]
    pairs=[(a,b) for ga,gb in combinations(groups,2) for a in groups[ga] for b in groups[gb]]
    for port,star in poses:
        transforms={'Fixed':np.eye(4),'Port':matrix('Port',port),'Starboard':matrix('Starboard',star)}; vm={g:vtkmat(t) for g,t in transforms.items()};bounds={}
        for name,(m,p) in parts.items():
            v=trimesh.transform_points(m.vertices,transforms[group(name)]);bounds[name]=(v.min(0),v.max(0))
        found=[];candidates=0
        for a,b in pairs:
            lo,hi=bounds[a];lo2,hi2=bounds[b]
            if np.any(hi<lo2) or np.any(hi2<lo):continue
            candidates+=1;f=vtk.vtkCollisionDetectionFilter();f.SetInputData(0,parts[a][1]);f.SetInputData(1,parts[b][1]);f.SetMatrix(0,vm[group(a)]);f.SetMatrix(1,vm[group(b)]);f.SetCollisionModeToFirstContact();f.SetBoxTolerance(0);f.SetCellTolerance(0);f.GenerateScalarsOff();f.Update()
            if f.GetNumberOfContacts()>0:found.append((a,b))
        new=[p for p in found if any(' / T59 ' in n or ' / T60 ' in n for n in p)]
        report.append({'port':port,'starboard':star,'aabb_candidates':candidates,'surface_contact_pairs':found,'detail_contact_pairs':new});print(port,star,'candidates',candidates,'contacts',len(found),'detail',len(new),flush=True)
    (D/'interference_audit.json').write_text(json.dumps({'method':'cross-group AABB then VTK triangle surface contact at discrete angles; includes intentional hinge interfaces; no containment/swept guarantee','poses':report},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
