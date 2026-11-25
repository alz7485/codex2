"""Trial160 mesh and transparent compositor for the Windows host."""
from pathlib import Path
from dataclasses import replace
import numpy as np
import trimesh
from PIL import Image
import runtime_render as shared
from runtime_render import vtk, poly, vtkmat
from studio148 import setup, material
from motion149 import transform as deploy_transform
from effects160 import draw_effects
from combat_effects160 import draw_combat
from field_effects158 import draw_field

class Renderer(shared.Renderer):
    def __init__(self):
        self.rw = rw = (shared._render_window_type or vtk.vtkRenderWindow)()
        shared._render_window_type = type(rw)
        rw.SetOffScreenRendering(1)
        rw.SetMultiSamples(0)
        rw.SetAlphaBitPlanes(1)
        self.ren = vtk.vtkRenderer()
        self.ren.SetBackground(0,0,0)
        self.ren.SetBackgroundAlpha(0)
        self.ren.AutomaticLightCreationOff()
        rw.AddRenderer(self.ren)
        self.environment = setup(self.ren)
        self.ren.GetEnvMapPrefiltered().SetPrefilterLevels(4)
        scene = trimesh.load(Path(__file__).parent/'Akatsuki_Shiranui_Trial149_stowed.glb',force='scene',process=False)
        first=[]
        for node in scene.graph.nodes_geometry:
            transform,name=scene.graph[node]
            mesh=scene.geometry[name].copy()
            mesh.apply_transform(transform)
            normals=vtk.vtkPolyDataNormals()
            normals.SetInputData(poly(mesh))
            normals.ComputePointNormalsOn()
            normals.SplittingOn()
            normals.SetFeatureAngle(10)
            mapper=vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(normals.GetOutputPort())
            actor=vtk.vtkActor()
            actor.SetMapper(mapper)
            material(actor.GetProperty(),mesh.visual.material)
            self.ren.AddActor(actor)
            first.append((node,actor))
        self.groups=[first]
        for _ in range(6):
            group=[]
            for side,original in first:
                actor=vtk.vtkActor()
                actor.SetMapper(original.GetMapper())
                actor.SetProperty(original.GetProperty())
                self.ren.AddActor(actor)
                group.append((side,actor))
            self.groups.append(group)
        for position,intensity,color in [((400,-20,500),1.4,(.87,.94,1)),((-250,-300,300),.8,(.78,.86,1)),((650,-250,200),.7,(1,.87,.67))]:
            light=vtk.vtkLight()
            light.SetPosition(*position)
            light.SetFocalPoint(320,-192,0)
            light.SetColor(*color)
            light.SetIntensity(intensity)
            self.ren.AddLight(light)
        self.cam=self.ren.GetActiveCamera()
        self.cam.ParallelProjectionOn()
        self.cam.SetViewUp(0,1,0)
        self.cam.SetClippingRange(500,1500)

    def deployment(self,age):
        # Per-renderer cache: closing a display also releases its geometry and pose data.
        if not hasattr(self,'_poses'):self._poses={}
        if age not in self._poses:
            if len(self._poses)>=256:self._poses.clear()
            self._poses[age]={name:deploy_transform(name,age) for name,_ in self.groups[0]}
        return self._poses[age]

    @staticmethod
    def luminous(rgb):
        rgb=np.asarray(rgb).astype(float)
        alpha=rgb.max(axis=2)
        colors=np.divide(rgb*255,alpha[...,None],out=np.zeros_like(rgb),where=alpha[...,None]>0)
        return Image.fromarray(np.dstack((colors,alpha)).clip(0,255).astype('uint8'),'RGBA')

    def draw(self,indexed,size,origin=(0,0),field=None):
        width,height=size
        self.rw.SetSize(width,height)
        self.cam.SetParallelScale(height/2)
        self.cam.SetPosition(width/2,-height/2,1000)
        self.cam.SetFocalPoint(width/2,-height/2,0)
        self.hide()
        states=[]
        screen_shift=np.asarray(origin,dtype=float)
        world_shift=np.array([-origin[0],origin[1],0.])
        if field is not None:field=replace(field,nodes=field.nodes+world_shift)
        for identity,state in indexed:
            f=state.flight
            if not f.visible:continue
            flight=replace(f,translation=f.translation+world_shift,
                           jets=tuple(replace(j,origin=j.origin+world_shift) for j in f.jets),
                           trails={key:tuple((t,p-screen_shift,power) for t,p,power in history)
                                   for key,history in f.trails.items()})
            shot=replace(state.shot,origin=tuple(np.asarray(state.shot.origin)+world_shift)) if state.shot else None
            state=replace(state,flight=flight,shot=shot)
            matrix=np.eye(4)
            matrix[:3,:3]=flight.matrix*flight.scale
            matrix[:3,3]=flight.translation
            pose=self.deployment(flight.deploy_time)
            for name,actor in self.groups[identity]:
                actor.SetVisibility(True)
                actor.SetUserMatrix(vtkmat(matrix@pose[name]))
            states.append(state)
        body,_=self.capture()
        rgb=draw_field(Image.new('RGB',size),field,'rear')
        for state in states:
            rgb=draw_effects(rgb,state.flight)
            rgb=draw_combat(rgb,state)
        effect=self.luminous(rgb)
        effect.alpha_composite(body)
        if field is not None:
            effect.alpha_composite(self.luminous(draw_field(Image.new('RGB',size),field,'front')))
        return effect
