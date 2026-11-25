from pathlib import Path
import sys, numpy as np, trimesh, vtk
from PIL import Image,ImageDraw,ImageFont
from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtk
from rig_trial61 import matrix
from audit_trial61 import poly,vtkmat
from check_trial82 import group
import imageio.v2 as iio
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'review_tools'));import create_models as cm
W,H=800,320;rw=vtk.vtkRenderWindow();rw.SetOffScreenRendering(1);rw.SetMultiSamples(0);rw.SetSize(W,H)
scenes=[];env=cm.studio_texture(False)
for i,kind in enumerate(('HiNu','HiNu_HWS')):
 s=trimesh.load(R/f'{kind}_Trial119.glb',force='scene',process=False);ren=vtk.vtkRenderer();ren.SetViewport(i*.5,0,(i+1)*.5,1);ren.SetBackground(.055,.075,.105);ren.AutomaticLightCreationOff();ren.SetEnvironmentTexture(env,False);ren.UseImageBasedLightingOn();ren.GetEnvMapPrefiltered().SetPrefilterLevels(4);rw.AddRenderer(ren)
 parts={};mats={}
 for n in s.graph.nodes_geometry:
  t,g=s.graph[n];m=s.geometry[g].copy();m.apply_transform(t);mat=m.visual.material;k=(group(s,n),mat.name,n if n=='Bridge / perforated face' and True else '');parts.setdefault(k,[]).append(m);mats[k]=mat
 actors=[]
 for k,ms in parts.items():
  normal=vtk.vtkPolyDataNormals();normal.SetInputData(poly(trimesh.util.concatenate(ms)));normal.SetFeatureAngle(30);normal.SplittingOn();normal.ConsistencyOn();mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normal.GetOutputPort());
  if k[2]:
   pd=poly(ms[0]); ns=numpy_to_vtk(np.ascontiguousarray(ms[0].vertex_normals),deep=True); ns.SetName("Normals"); pd.GetPointData().SetNormals(ns); mapper.SetInputData(pd)
  a=vtk.vtkActor();a.SetMapper(mapper);pr=a.GetProperty();pr.SetInterpolationToPBR();mat=mats[k];pr.SetColor(*(mat.baseColorFactor[:3]/255));pr.SetMetallic(float(mat.metallicFactor or 0));pr.SetRoughness(float(mat.roughnessFactor or .36));
  if k[1]=='T82 recessed energy core':pr.SetEmissiveFactor(.025,.065,.12)
  ren.AddActor(a);actors.append((k[0],a))
 for pos,intensity in [((-5,8,-7),1.3),((7,2,-1),.65),((1,-4,7),.8),((-4,1,5),.35)]:
  l=vtk.vtkLight();l.SetPosition(*pos);l.SetFocalPoint(0,0,0);l.SetIntensity(intensity);ren.AddLight(l)
 cam=ren.GetActiveCamera();cam.ParallelProjectionOn();groups=[actors]
 for member in range(3):
  clones=[]
  for side,a in actors:
   b=vtk.vtkActor();b.SetMapper(a.GetMapper());b.GetProperty().DeepCopy(a.GetProperty());ren.AddActor(b);clones.append((side,b))
  groups.append(clones)
 scenes.append((ren,cam,groups))
from integrated_trial121 import FleetCombat, draw_escort_shots, draw_shots, charge, MUZZLE, FORWARD_POINT
from idle_trial99 import visual_matrix,visual_power
from effects_trial122 import draw_exhaust,draw_side_trails
from trail_trial88 import draw_trails,Trail
from escort_trial98 import EscortFleet
from escort_trail_trial98 import draw_trails as draw_escort_trails
from trimesh.transformations import scale_matrix
import json
pivot=np.array([0,0,-.28]);toward=np.array([1.8,10.,2.5]);toward/=np.linalg.norm(toward);right=np.cross([0,1,0],toward);right/=np.linalg.norm(right);up=np.cross(toward,right)
for ren,cam,groups in scenes:
 cam.SetFocalPoint(*pivot);cam.SetPosition(*(pivot+12*toward));cam.SetViewUp(*up);cam.SetParallelScale(12.5);cam.SetClippingRange(1.,30.)
keys=[(0,(200,160)),(.4,(200,160)),(1.6,(170,190)),(2.2,(230,150)),(3.2,(235,125)),(4.5,(200,160))]
def path(t):
 for (a,x),(b,y) in zip(keys,keys[1:]):
  if t<=b:
   q=max(0,min(1,(t-a)/(b-a)));q=q*q*(3-2*q);return tuple(np.array(x)+(np.array(y)-x)*q)
 return keys[-1][1]
def capture(depth=False):
 f=vtk.vtkWindowToImageFilter();f.SetInput(rw);f.ReadFrontBufferOff();f.ShouldRerenderOff();f.SetInputBufferTypeToZBuffer() if depth else f.SetInputBufferTypeToRGB();f.Update();return vtk_to_numpy(f.GetOutput().GetPointData().GetScalars()).reshape((H,W) if depth else (H,W,3))[::-1].copy()
controllers=[FleetCombat(3,100) for _ in scenes];frames=[];records=[];fps=12
for i in range(54):
 t=i/fps;xy=path(t);coords=[];percent=100
 for j,(ren,cam,groups) in enumerate(scenes):
  c=controllers[j]
  if i in (7,24,32):c.down(t)
  if i in (13,26,34):c.up(t)
  cp=c.update(t,xy);p=cp.flight;trail=c.trail;fleet=c.fleet;members=c.update_fleet(t,xy,.65,(0,26,W//2,H));offset=np.array([j*W//2,0]);allfx=[]
  for idx,(position,pose,ratio,opacity) in enumerate([(xy,p,1.,1.)]+[(f.xy,c.escort_render_pose(f),f.ratio,f.opacity) for f in members]):
   visual=c.primary_visual if idx==0 else c.escort_visual(members[idx-1]);m=visual_matrix(pose,visual,right,up,toward,pivot,np.array(position)-[W/4,H/2],25/H)@scale_matrix(ratio,pivot)
   fp=cp.fire if idx==0 else c.escort_fire_pose(members[idx-1]);m[:3,3]+=m[:3,:3]@np.array([0,0,fp.recoil])
   for side,a in groups[idx]:
    a.SetUserMatrix(vtkmat(m@matrix(side,0)));a.SetVisibility(opacity>0);a.GetProperty().SetOpacity(opacity)
   def pr(v):
    ren.SetWorldPoint(*(m@[*v,1])[:3],1);ren.WorldToDisplay();x,y,z=ren.GetDisplayPoint();return np.array([x,H-1-y])-offset
   nozzles=[]
   for y in (-.105,.105):
    a=pr((0,y,3.576));v=pr((0,y,4.576))-a;normal=np.array([-v[1],v[0]])/max(1e-9,np.linalg.norm(v));w=abs(np.dot(pr((.129,y,3.576))-a,normal))+abs(np.dot(pr((0,y+.013,3.576))-a,normal));nozzles.append((a.tolist(),v.tolist(),float(w)))
   def pr3(v,ren=ren,m=m.copy(),offset=offset.copy()):
    ren.SetWorldPoint(*(m@[*v,1])[:3],1);ren.WorldToDisplay();x,y,z=ren.GetDisplayPoint();return (x-offset[0],H-1-y,z)
   a=pr3(MUZZLE);b=pr3(FORWARD_POINT);direction=np.array(b[:2])-a[:2];n=np.linalg.norm(direction)
   kw=dict(depth_origin=a[2],depth_per_pixel=(b[2]-a[2])/max(n,1e-9),channel_pixels=n*7.0674)
   if idx==0:shots=c.projected(t,xy,cp,nozzles,a[:2],direction,**kw);tr=trail
   else:shots=c.escort_projected(t,members[idx-1],nozzles,a[:2],direction,scale=.65,**kw);tr=fleet.trails[idx-1]
   def world_project(v):
    ren.SetWorldPoint(*v,1);ren.WorldToDisplay();x,y,z=ren.GetDisplayPoint();return (x-offset[0],H-1-y)
   jets=c.visual_jets(idx,t,position,m,visual_power(pose,visual)*opacity,right,up,world_project,enabled=opacity>0)
   allfx.append((tr,nozzles,visual_power(pose,visual)*opacity,fp,pr3,ratio,shots,jets))
  coords.append(allfx)
 rw.Render();base=Image.fromarray(capture()).convert('RGBA');depth=capture(True);body=Image.fromarray(np.where(depth<.999999,255,0).astype('uint8'));glow=base.copy()
 for j,fx in enumerate(coords):
  x=j*W//2;crop=glow.crop((x,0,x+W//2,H))
  for idx in reversed(range(len(fx))):
   tr,nozzles,power,*rest=fx[idx]
   crop=draw_side_trails(crop,t,controllers[j].side_trails[idx])
   crop=(draw_escort_trails if hasattr(tr,"size_multiplier") else draw_trails)(crop,t,tr)
   for port,power,jet in rest[-1]:crop=draw_exhaust(crop,t,power,[jet])
  glow.paste(crop,(x,0))
 im=Image.composite(base,glow,body)
 for j,fx in enumerate(coords):
  x=j*W//2;crop=im.crop((x,0,x+W//2,H));dep=depth[:,x:x+W//2];kind=('HiNu','HiNu_HWS')[j]
  for idx,(_,_,_,fp,pr3,ratio,shots,jets) in enumerate(fx):
   crop=charge(crop,t+idx*.371,fp,pr3,dep,.85*ratio,kind=kind)
   crop=draw_shots(crop,t,shots,.65,kind,depth=dep) if idx==0 else draw_escort_shots(crop,t,shots,kind,depth=dep)
  im.paste(crop,(x,0))
 im=im.convert('RGB');d=ImageDraw.Draw(im);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
 for j,k in enumerate(('Hi-Nu','Hi-Nu HWS')):
  x=j*W//2;d.rectangle((x,0,x+W//2-1,25),fill='#142131');d.text((x+8,4),f'{k} | '+'PARALLEL VOLLEY' ,font=font,fill='#eef4ff')
 d.line((W//2,26,W//2,H),fill='#314155');frames.append(im);records.append({'t':t,'xy':xy,'size_percent':percent,'roll_deg':float(np.degrees(c.primary_visual.roll)),'idle_mix':c.primary_visual.mix,'shots':[[[f[3].stage,len(f[6])] for f in fx] for fx in coords],'members':[{'id':m.id,'ratio':m.ratio,'xy':m.xy,'heading':m.pose.heading,'render_heading':c.escort_render_pose(m).heading,'aim_locked':c.aim_locked,'bank':m.pose.bank,'power':m.pose.power} for m in members]})
 if i%12==0:print('rendered',i,flush=True)
rw.Finalize()
frames[17].save(R/'normal122.jpg')
with iio.get_writer(R/'normal122.mp4',fps=fps,codec='libx264',macro_block_size=2,quality=8) as writer:
 for im in frames:writer.append_data(np.asarray(im))
small=[im.resize((480,192),Image.Resampling.LANCZOS) for im in frames[::2]];strip=Image.new('RGB',(480,192*len(small)))
for i,im in enumerate(small):strip.paste(im,(0,i*192))
pal=strip.quantize(colors=32,method=Image.Quantize.MEDIANCUT);small=[im.quantize(palette=pal,dither=Image.Dither.NONE) for im in small];small[0].save(R/'normal122.gif',save_all=True,append_images=small[1:],duration=167,loop=0,optimize=True,disposal=1)
(R/'normal122_trace.json').write_text(json.dumps(records,indent=2,default=float))
