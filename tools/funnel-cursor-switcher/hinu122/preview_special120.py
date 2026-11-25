from pathlib import Path
import os, sys, numpy as np, trimesh, vtk
from PIL import Image,ImageDraw,ImageFont
from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtk
from rig_trial61 import matrix
from audit_trial61 import poly,vtkmat
from check_trial82 import group
import imageio.v2 as iio
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'review_tools'));import create_models as cm
W,H=480,240;rw=vtk.vtkRenderWindow();rw.SetOffScreenRendering(1);rw.SetMultiSamples(0);rw.SetSize(W,H)
scenes=[];actor_materials={};env=cm.studio_texture(False)
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
  ren.AddActor(a);actors.append((k[0],a));actor_materials[a]=(k[1],tuple(pr.GetEmissiveFactor()))
 for pos,intensity in [((-5,8,-7),1.3),((7,2,-1),.65),((1,-4,7),.8),((-4,1,5),.35)]:
  l=vtk.vtkLight();l.SetPosition(*pos);l.SetFocalPoint(0,0,0);l.SetIntensity(intensity);ren.AddLight(l)
 cam=ren.GetActiveCamera();cam.ParallelProjectionOn();groups=[actors]
 for member in range(5):
  clones=[]
  for side,a in actors:
   b=vtk.vtkActor();b.SetMapper(a.GetMapper());b.GetProperty().DeepCopy(a.GetProperty());ren.AddActor(b);clones.append((side,b));actor_materials[b]=actor_materials[a]
  groups.append(clones)
 scenes.append((ren,cam,groups))
from special_trial119 import sample,END,phase,REENTRY,FORMATION,SHOT,shot_matrix,BASE_END,residual
from special_trial117 import CAMERA_Z,MOVE,HOLD
from nozzle_trial119 import project_ports
from composition_trial116 import camera_pose,material_emission
from special_trial115 import flight_unit
from functools import lru_cache
sample=lru_cache(maxsize=1024)(sample)
from combat_trial95 import charge
from combat_trial93 import charge as residual_charge
from fire_trial89 import FirePose,FIRE
from beam_trial111 import beam
from combat_trial94 import MUZZLE,FORWARD_POINT
from special_trial106 import HOLD,EXIT
from effects_trial120 import draw_exhaust
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
for ren,cam,groups in scenes:
 cam.SetFocalPoint(0,0,0);cam.SetPosition(0,0,CAMERA_Z);cam.SetViewUp(0,1,0);cam.ParallelProjectionOff();cam.SetViewAngle(34);cam.SetClippingRange(.35,80)
def capture(depth=False):
 f=vtk.vtkWindowToImageFilter();f.SetInput(rw);f.ReadFrontBufferOff();f.ShouldRerenderOff();f.SetInputBufferTypeToZBuffer() if depth else f.SetInputBufferTypeToRGB();f.Update();return vtk_to_numpy(f.GetOutput().GetPointData().GetScalars()).reshape((H,W) if depth else (H,W,3))[::-1].copy()
fps=12;frames=[]
from special_trial119 import trail_gain
for i in range(round(END*fps)):
 t=i/fps;units=sample(t);fx=[];trails=[];combat=[]; cp=camera_pose(t)
 for j,(ren,cam,groups) in enumerate(scenes):
  current=[]; paths=[]; attacks=[]
  cam.SetPosition(cp.x,cp.y,cp.z);cam.SetFocalPoint(cp.x,cp.y,0);cam.SetViewAngle(cp.fov)
  kind=("HiNu","HiNu_HWS")[j]
  def pr(p):
   ren.SetWorldPoint(*p,1);ren.WorldToDisplay();x,y,z=ren.GetDisplayPoint();return np.array([x-j*W//2,H-1-y])
  for idx,actors in enumerate(groups):
   u=units[idx] if idx<len(units) else None
   for side,a in actors:
    a.SetVisibility(bool(u and u.visible))
    if u:
     a.SetUserMatrix(vtkmat(u.part_matrix(side)))
     name,baseline=actor_materials[a];a.GetProperty().SetEmissiveFactor(*material_emission(name,baseline,kind,getattr(u,"fire",FirePose())))
   if u and u.visible:
    for port,p,jet in project_ports(u.thrusters(),u.transform(),pr):
     if p>0:current.append((p,[jet]))
   if u and u.visible and (getattr(u,'fire',FirePose()).stage!='idle' or residual(t)>0):
    attacks.append((u,u.transform(),shot_matrix(u.id) if t>=SHOT else None))
  if REENTRY<=t<END:
   for k in range(6):
    points=[[] for _ in range(4)]
    for dt in np.linspace(.13,0,9):
     a=t-REENTRY-dt
     if a<0:continue
     history=sample(REENTRY+a)
     if k>=len(history):continue
     u=history[k]
     for n,(port,o,v,p) in enumerate(u.thrusters()):
      p *= trail_gain(k,t,REENTRY+a)
      points[n].append((tuple(pr(o)),p,float(cp.z/(cp.z-u.position[2])) ) if u.visible and p>.15 else None)
    paths.extend(points)
  trails.append(paths);fx.append(current);combat.append(attacks)
 rw.Render();base=Image.fromarray(capture()).convert('RGBA');depth=capture(True);mask=Image.fromarray(np.where(depth<.999999,255,0).astype('uint8'));glow=base.copy()
 for j,items in enumerate(fx):
  x=j*W//2;crop=glow.crop((x,0,x+W//2,H))
  layer=Image.new('RGBA',crop.size);pen=ImageDraw.Draw(layer)
  for path in trails[j]:
   for k,(a,b) in enumerate(zip(path,path[1:])):
    if a is None or b is None:continue
    f=(k+1)/(len(path)-1); power=min(a[1],b[1]); width=max(1,round(2.4*b[2]));pen.line((a[0],b[0]),fill=(55,146,255,round(86*f*power)),width=width);pen.line((a[0],b[0]),fill=(180,230,255,round(190*f*power)),width=max(1,width//3))
  crop.alpha_composite(layer)
  for p,nozzles in items:crop=draw_exhaust(crop,t,p,nozzles)
  glow.paste(crop,(x,0))
 im=Image.composite(base,glow,mask)
 for j,(ren,cam,groups) in enumerate(scenes):
  x=j*W//2;crop=im.crop((x,0,x+W//2,H));dep=depth[:,x:x+W//2];kind=('HiNu','HiNu_HWS')[j]
  def project(v,m):
   ren.SetWorldPoint(*(m@[*v,1])[:3],1);ren.WorldToDisplay();a,b,c=ren.GetDisplayPoint();return np.array([a-x,H-1-b,c])
  for u,m,sm in combat[j]:
   scale=float(.55*CAMERA_Z/(cp.z-u.position[2])*np.tan(np.radians(17))/np.tan(np.radians(cp.fov/2)));crop=charge(crop,t+u.id*.371,u.fire,lambda v:project(v,m),dep,scale,kind)
   if residual(t)>0:
    crop=residual_charge(crop,t+u.id*.371,FirePose('charge',charge=residual(t)),lambda v:project(v,m),dep,scale,kind)
   if sm is not None:
    crop=beam(crop,u.fire,lambda p:project(p,np.eye(4)),sm,kind,dep)
  im.paste(crop,(x,0))
 im=im.convert('RGB');d=ImageDraw.Draw(im)
 for j,k in enumerate(('Hi-Nu','Hi-Nu HWS')):
  x=j*W//2;d.rectangle((x,0,x+W//2-1,25),fill='#142131');d.text((x+8,4),f'{k} | {phase(t).upper()}',font=font,fill='#eef4ff')
 d.line((W//2,26,W//2,H),fill='#314155');frames.append(im)
 if i%8==0:print('rendered',i,flush=True)
rw.Finalize()
with iio.get_writer(R/'volley120.mp4',fps=fps,codec='libx264',macro_block_size=2,quality=8) as writer:
 for im in frames:writer.append_data(np.asarray(im))
small=[im.resize((400,200),Image.Resampling.LANCZOS) for im in frames[::1]];strip=Image.new('RGB',(400,200*len(small)))
for i,im in enumerate(small):strip.paste(im,(0,i*200))
pal=strip.quantize(colors=32,method=Image.Quantize.MEDIANCUT);small=[im.quantize(palette=pal,dither=Image.Dither.NONE) for im in small];small[0].save(R/'volley120.gif',save_all=True,append_images=small[1:],duration=83,loop=0,optimize=True,disposal=1)

frames[round((BASE_END+.32)*fps)].save(R/'departure120.jpg',quality=92)
