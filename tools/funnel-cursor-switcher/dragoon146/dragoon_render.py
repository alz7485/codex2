"""Trial146 mesh and transparent compositor for the Windows host."""
from pathlib import Path
from dataclasses import replace
import numpy as np
import trimesh
from PIL import Image
import runtime_render as shared
from runtime_render import vtk, poly, vtkmat
from studio133 import setup, material
from render_fx146 import compose

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
        scene = trimesh.load(Path(__file__).parent/'StrikeFreedom_Dragoon_Trial133.glb',force='scene',process=False)
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
            first.append(('Fixed',actor))
        self.groups=[first]
        for _ in range(7):
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

    def draw(self,indexed,size,origin=(0,0),special=False):
        width,height=size
        self.rw.SetSize(width,height)
        self.cam.SetParallelScale(height/2)
        self.cam.SetPosition(width/2,-height/2,1000)
        self.cam.SetFocalPoint(width/2,-height/2,0)
        self.hide()
        states=[]
        screen_shift=np.asarray(origin,dtype=float)
        world_shift=np.array([-origin[0],origin[1],0.])
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
            for _,actor in self.groups[identity]:
                actor.SetVisibility(True)
                actor.SetUserMatrix(vtkmat(matrix))
            states.append(state)
        body,_=self.capture()
        rgb=np.asarray(compose(Image.new('RGB',size),states,special=special)).astype(float)
        alpha=rgb.max(axis=2)
        colors=np.divide(rgb*255,alpha[...,None],out=np.zeros_like(rgb),where=alpha[...,None]>0)
        effect=Image.fromarray(np.dstack((colors,alpha)).clip(0,255).astype('uint8'),'RGBA')
        effect.alpha_composite(body)
        return effect
