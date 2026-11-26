"""Trial218 meshes and current FX; reuse only the established VTK backend."""
from pathlib import Path
import math
import numpy as np
import trimesh
from PIL import Image
import runtime_render as shared
from runtime_render import vtk,poly,vtkmat,group,studio_texture,vtk_to_numpy,numpy_to_vtk
from .rig_trial61 import matrix
from .model_trial188 import MODELS
from .idle_trial99 import visual_matrix,visual_power
from trimesh.transformations import scale_matrix
from .idle_trial192 import FleetCombat
from .pulse_trial190 import draw_shots,draw_escort_shots,MUZZLE,FORWARD_POINT
from .charge_fx_trial204 import normal_charge as charge
from .normal_fx_trial204 import draw_exhaust,draw_side_trails,draw_trails,draw_escort_trails
from .special_trial215 import SpecialVolley,sample,camera_pose,shot_matrix,reentry_for
from .composition_trial116 import material_emission
from .fire_trial89 import FirePose
from .nozzle_trial119 import project_ports
from . import special_render_trial217 as fx218
R=Path(__file__).parent

class Renderer:
    def __init__(self, kind):
        self.kind = kind
        self.rw = rw = (shared._render_window_type or vtk.vtkRenderWindow)()
        shared._render_window_type = type(rw)
        rw.SetOffScreenRendering(1)
        rw.SetMultiSamples(0)
        rw.SetAlphaBitPlanes(1)
        ren = vtk.vtkRenderer()
        ren.SetBackground(0, 0, 0)
        ren.SetBackgroundAlpha(0)
        ren.AutomaticLightCreationOff()
        self.environment = studio_texture(False)
        ren.SetEnvironmentTexture(self.environment, False)
        ren.UseImageBasedLightingOn()
        ren.GetEnvMapPrefiltered().SetPrefilterLevels(4)
        self.materials = {}
        rw.AddRenderer(ren)
        s = trimesh.load(R / MODELS[kind], force="scene", process=False)
        self.cursor_tip=np.array([0.,0.,s.bounds[0,2]])
        parts = {}
        mats = {}
        for n in s.graph.nodes_geometry:
            t, g = s.graph[n]
            m = s.geometry[g].copy()
            m.apply_transform(t)
            mat = m.visual.material
            k = (
                group(s, n),
                mat.name,
                n if n == "Bridge / perforated face" and True else "",
            )
            parts.setdefault(k, []).append(m)
            mats[k] = mat
        actors = []
        for k, ms in parts.items():
            normal = vtk.vtkPolyDataNormals()
            normal.SetInputData(poly(trimesh.util.concatenate(ms)))
            normal.SetFeatureAngle(30)
            normal.SplittingOn()
            normal.ConsistencyOn()
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(normal.GetOutputPort())
            if k[2]:
                pd = poly(ms[0])
                ns = numpy_to_vtk(np.ascontiguousarray(ms[0].vertex_normals), deep=True)
                ns.SetName("Normals")
                pd.GetPointData().SetNormals(ns)
                mapper.SetInputData(pd)
            a = vtk.vtkActor()
            a.SetMapper(mapper)
            pr = a.GetProperty()
            pr.SetInterpolationToPBR()
            mat = mats[k]
            pr.SetColor(*(mat.baseColorFactor[:3] / 255))
            pr.SetMetallic(float(mat.metallicFactor or 0))
            pr.SetRoughness(float(mat.roughnessFactor or 0.36))
            if k[1] == "T82 recessed energy core":
                pr.SetEmissiveFactor(0.025, 0.065, 0.12)
            ren.AddActor(a)
            actors.append((k[0], a))
            self.materials[a] = (k[1], tuple(pr.GetEmissiveFactor()))
        for pos, intensity in [
            ((-5, 8, -7), 1.3),
            ((7, 2, -1), 0.65),
            ((1, -4, 7), 0.8),
            ((-4, 1, 5), 0.35),
        ]:
            l = vtk.vtkLight()
            l.SetPosition(*pos)
            l.SetFocalPoint(0, 0, 0)
            l.SetIntensity(intensity)
            ren.AddLight(l)
        cam = ren.GetActiveCamera()
        cam.ParallelProjectionOn()
        groups = [actors]
        for member in range(7):
            clones = []
            for side, a in actors:
                b = vtk.vtkActor()
                b.SetMapper(a.GetMapper())
                b.GetProperty().DeepCopy(a.GetProperty())
                ren.AddActor(b)
                clones.append((side, b))
                self.materials[b] = self.materials[a]
            groups.append(clones)
        self.ren, self.cam, self.groups = ren, cam, groups

    def capture(self):
        self.rw.Render()

        def read(depth=False):
            f = vtk.vtkWindowToImageFilter()
            f.SetInput(self.rw)
            f.ReadFrontBufferOff()
            f.ShouldRerenderOff()
            f.SetInputBufferTypeToZBuffer() if depth else f.SetInputBufferTypeToRGBA()
            f.Update()
            w, h = self.rw.GetSize()
            return (
                vtk_to_numpy(f.GetOutput().GetPointData().GetScalars())
                .reshape((h, w) if depth else (h, w, 4))[::-1]
                .copy()
            )

        return Image.fromarray(read()), read(True)

    def project(self, p):
        self.ren.SetWorldPoint(*p, 1)
        self.ren.WorldToDisplay()
        x, y, z = self.ren.GetDisplayPoint()
        return np.array([x, self.rw.GetSize()[1] - 1 - y, z])

    def place(self, index, m, opacity=1, fold=0):
        for side, a in self.groups[index]:
            a.SetVisibility(opacity > 0)
            a.GetProperty().SetOpacity(opacity)
            a.GetProperty().SetEmissiveFactor(*self.materials[a][1])
            a.SetUserMatrix(vtkmat(m @ matrix(side, fold if side == "Port" else -fold)))

    def hide(self):
        for actors in self.groups:
            for _, a in actors:
                a.SetVisibility(False)

    def normal(self, c, t, xy, size, bounds, fixed, context):
        self.rw.SetSize(*size)
        self.hide()
        w, h = size
        pivot = np.array([0, 0, -0.28])
        toward = np.array([1.8, 10.0, 2.5])
        toward /= np.linalg.norm(toward)
        right = np.cross([0, 1, 0], toward)
        right /= np.linalg.norm(right)
        up = np.cross(toward, right)
        cam = self.cam
        cam.ParallelProjectionOn()
        cam.SetFocalPoint(*pivot)
        cam.SetPosition(*(pivot + 12 * toward))
        cam.SetViewUp(*up)
        # Match the original 32px cursor body size, independent of render-target size.
        units = 7.0 / (32 * getattr(self, "scale", 1))
        cam.SetParallelScale(h * units / 2)
        cam.SetClippingRange(1, 30)
        cp = c.update(t, xy, context=context, fixed=fixed)
        members = c.update_fleet(
            t, xy, 0.65 * getattr(self, "scale", 1), bounds, context=context
        )
        fx = []
        self.shot_layers=[]
        entries = [(xy, cp.flight, 1.0, 1.0, None)] + [
            (f.xy, c.escort_render_pose(f), f.ratio, f.opacity, f) for f in members
        ]
        for idx, (position, pose, ratio, opacity, member) in enumerate(entries):
            visual = c.primary_visual if member is None else c.escort_visual(member)
            m = visual_matrix(
                pose,
                visual,
                right,
                up,
                toward,
                pivot,
                np.array(position)
                - np.array(getattr(self, "screen_origin", (0, 0)))
                - [w / 2, h / 2],
                units,
            ) @ scale_matrix(ratio, pivot)
            if member is None:
                front = self.project((m @ [*self.cursor_tip, 1])[:3])[:2]
                target = np.array(position) - np.array(
                    getattr(self, "screen_origin", (0, 0))
                )
                delta = target - front
                m[:3, 3] += units * (delta[0] * right - delta[1] * up)
            fp = cp.fire if member is None else c.escort_fire_pose(member)
            m[:3, 3] += m[:3, :3] @ np.array([0, 0, fp.recoil])
            if member is None:self.primary_anchor=self.project((m@[*self.cursor_tip,1])[:3])
            self.place(idx, m, opacity)

            def pr(v, m=m.copy()):
                return self.project((m @ [*v, 1])[:3])

            nozzles = []
            for y in (-0.105, 0.105):
                a = pr((0, y, 3.576))
                v = pr((0, y, 4.576)) - a
                normal=np.array([-v[1],v[0]])/max(1e-9,np.linalg.norm(v[:2]))
                width=abs(np.dot(pr((.129,y,3.576))[:2]-a[:2],normal))+abs(np.dot(pr((0,y+.013,3.576))[:2]-a[:2],normal))
                nozzles.append((a[:2].tolist(), v[:2].tolist(),float(width)))
            a, b = pr(MUZZLE), pr(FORWARD_POINT)
            direction = b[:2] - a[:2]
            n = np.linalg.norm(direction)
            kw = dict(
                depth_origin=a[2],
                depth_per_pixel=(b[2] - a[2]) / max(n, 1e-9),
                channel_pixels=n * 7.0674,
            )
            if member is None:
                shots = c.projected(
                    t,
                    xy,
                    cp,
                    nozzles,
                    a[:2],
                    direction,
                    context=context,
                    fixed=fixed,
                    scale=.3*getattr(self,"scale",1),
                    **kw,
                )
                tr = c.trail
            else:
                shots = c.escort_projected(
                    t, member, nozzles, a[:2], direction, scale=.3*getattr(self,"scale",1), **kw
                )
                tr = c.fleet.trails[member.id]
            jets = c.visual_jets(
                idx,
                t,
                position,
                m,
                visual_power(pose, visual) * opacity,
                right,
                up,
                lambda v: self.project(v)[:2],
                enabled=opacity > 0,
            )
            self.shot_layers.append((idx,shots,a))
            fx.append((idx, fp, pr, ratio, shots, tr, jets))
        body, depth = self.capture()
        glow = Image.new("RGBA", size)
        for idx, fp, pr, ratio, shots, tr, jets in reversed(fx):
            glow = draw_side_trails(glow, t, c.side_trails[idx])
            glow = (draw_escort_trails if idx else draw_trails)(glow, t, tr)
            for _, power, jet in jets:
                glow = draw_exhaust(glow, t, power, [jet])
        glow.alpha_composite(body)
        for idx, fp, pr, ratio, shots, tr, jets in fx:
            glow = charge(
                glow, t + idx * 0.371, fp, pr, depth, 0.3 * ratio * getattr(self,"scale",1), kind=self.kind
            )
            if getattr(self, "draw_beams", True):
                glow = (
                    draw_escort_shots(glow, t, shots, self.kind, depth=depth,root=pr(MUZZLE))
                    if idx
                    else draw_shots(glow, t, shots, 0.3*getattr(self,"scale",1), self.kind, depth=depth,root=pr(MUZZLE))
                )
        return glow

    def special(self,t,size):
        self.rw.SetSize(*size);self.hide()
        aspect=size[0]/size[1];cp=camera_pose(t,self.kind)
        cam=self.cam;cam.ParallelProjectionOff()
        cam.SetPosition(cp.x,cp.y,cp.z);cam.SetFocalPoint(cp.x,cp.y,0)
        cam.SetViewUp(0,1,0);cam.SetViewAngle(cp.fov);cam.SetClippingRange(.35,80)
        current=[];attacks=[]
        for u in sample(t,self.kind,aspect):
            if not u.visible:continue
            for side,actor in self.groups[u.id]:
                actor.SetVisibility(True);actor.GetProperty().SetOpacity(1.)
                actor.SetUserMatrix(vtkmat(u.part_matrix(side)))
                name,baseline=self.materials[actor]
                actor.GetProperty().SetEmissiveFactor(*material_emission(name,baseline,self.kind,getattr(u,'fire',FirePose())))
            m=u.transform()
            for port,power,jet in project_ports(u.thrusters(),m,self.project):
                if power>0:current.append((u.id,port,power,[jet]))
            fire=getattr(u,'fire',FirePose())
            if fire.stage!='idle':
                shot=shot_matrix(u.id,self.kind,aspect,t=t) if t>=reentry_for(self.kind) and fire.stage in ('fire','afterglow') else None
                attacks.append((u,m,shot))
        body,depth=self.capture()
        blank=Image.new('RGBA',size)
        if t<reentry_for(self.kind):glow=fx218.draw_launch_trails(blank,t,self.project,self.kind)
        elif self.kind=='HiNu':glow=fx218.draw_mobile_trails(blank,t,self.project,aspect)
        else:glow=fx218.draw_raid_trails(blank,t,self.project,aspect)
        for uid,port,power,jets in current:
            glow=fx218.exhaust(glow,t,power,jets,kind=self.kind,unit_id=uid,port=port,owned=True)
        mask=Image.fromarray(np.where(depth<.999999,255,0).astype('uint8'))
        image=Image.composite(body,glow,mask)
        for u,m,shot in attacks:
            scale=float(.55*40/(cp.z-u.position[2]))
            image=fx218.charge(image,t+u.id*.371,u.fire,lambda v,m=m:self.project((m@[*v,1])[:3]),depth,scale,self.kind,
                               raid=self.kind=='HiNu_HWS' and t>=reentry_for(self.kind))
            if shot is not None:
                image=(fx218.mobile_beam(image,u.fire,self.project,shot,depth) if self.kind=='HiNu'
                       else fx218.beam(image,u.fire,self.project,shot,self.kind,depth))
        return image

    def close(self):self.rw.Finalize()
