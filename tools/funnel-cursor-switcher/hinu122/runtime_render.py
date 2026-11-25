"""Reusable Trial122 mesh renderer. All coordinates are physical pixels."""

from pathlib import Path
import math
import numpy as np
import trimesh
from types import SimpleNamespace
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkPolyData, vtkCellArray
from vtkmodules.vtkCommonMath import vtkMatrix4x4
from vtkmodules.vtkFiltersCore import vtkPolyDataNormals
from vtkmodules.vtkRenderingCore import (
    vtkRenderer,
    vtkRenderWindow,
    vtkWindowToImageFilter,
    vtkActor,
    vtkLight,
    vtkPolyDataMapper,
)
import vtkmodules.vtkRenderingOpenGL2

vtk = SimpleNamespace(
    **{
        name: value
        for name, value in globals().copy().items()
        if name.startswith("vtk")
    }
)
from PIL import Image, ImageDraw
from vtkmodules.util.numpy_support import (
    vtk_to_numpy,
    numpy_to_vtk,
    numpy_to_vtkIdTypeArray,
)
from rig_trial61 import matrix
from idle_trial99 import visual_matrix, visual_power
from trimesh.transformations import scale_matrix
from integrated_trial121 import (
    FleetCombat,
    draw_escort_shots,
    draw_shots,
    charge,
    MUZZLE,
    FORWARD_POINT,
)
from effects_trial122 import draw_exhaust, draw_side_trails
from trail_trial88 import draw_trails
from escort_trail_trial98 import draw_trails as draw_escort_trails
from special_trial119 import SpecialVolley, sample, shot_matrix, SHOT, residual
from composition_trial116 import camera_pose, material_emission
from beam_trial111 import beam
from fire_trial89 import FirePose

R = Path(__file__).parent


def group(scene, name):
    while name in scene.graph.transforms.parents:
        name = scene.graph.transforms.parents[name]
        if name in ("Port hinge rig", "Starboard hinge rig"):
            return name.split()[0]
    return "Fixed"


def poly(mesh):
    result = vtkPolyData()
    points = vtkPoints()
    points.SetData(numpy_to_vtk(np.ascontiguousarray(mesh.vertices), deep=True))
    result.SetPoints(points)
    cells = vtkCellArray()
    faces = np.ascontiguousarray(mesh.faces, dtype=np.int64)
    cells.SetData(
        numpy_to_vtkIdTypeArray(
            np.arange(0, 3 * (len(faces) + 1), 3, dtype=np.int64), deep=True
        ),
        numpy_to_vtkIdTypeArray(faces.ravel(), deep=True),
    )
    result.SetPolys(cells)
    return result


def vtkmat(array):
    result = vtkMatrix4x4()
    result.DeepCopy(array.ravel())
    return result


class Renderer:
    def __init__(self, kind):
        self.kind = kind
        self.rw = rw = vtk.vtkRenderWindow()
        rw.SetOffScreenRendering(1)
        rw.SetMultiSamples(0)
        rw.SetAlphaBitPlanes(1)
        ren = vtk.vtkRenderer()
        ren.SetBackground(0, 0, 0)
        ren.SetBackgroundAlpha(0)
        ren.AutomaticLightCreationOff()
        rw.AddRenderer(ren)
        s = trimesh.load(R / f"{kind}_Trial119.glb", force="scene", process=False)
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
        for member in range(5):
            clones = []
            for side, a in actors:
                b = vtk.vtkActor()
                b.SetMapper(a.GetMapper())
                b.GetProperty().DeepCopy(a.GetProperty())
                ren.AddActor(b)
                clones.append((side, b))
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
                front = self.project((m @ [*MUZZLE, 1])[:3])[:2]
                target = np.array(position) - np.array(
                    getattr(self, "screen_origin", (0, 0))
                )
                delta = target - front
                m[:3, 3] += units * (delta[0] * right - delta[1] * up)
            fp = cp.fire if member is None else c.escort_fire_pose(member)
            m[:3, 3] += m[:3, :3] @ np.array([0, 0, fp.recoil])
            self.place(idx, m, opacity)

            def pr(v, m=m.copy()):
                return self.project((m @ [*v, 1])[:3])

            nozzles = []
            for y in (-0.105, 0.105):
                a = pr((0, y, 3.576))
                v = pr((0, y, 4.576)) - a
                nozzles.append((a[:2].tolist(), v[:2].tolist(), max(0.2, ratio * 0.3)))
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
                    **kw,
                )
                tr = c.trail
            else:
                shots = c.escort_projected(
                    t, member, nozzles, a[:2], direction, scale=0.65, **kw
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
                glow, t + idx * 0.371, fp, pr, depth, 0.3 * ratio, kind=self.kind
            )
            if getattr(self, "draw_beams", True):
                glow = (
                    draw_escort_shots(glow, t, shots, self.kind, depth=depth)
                    if idx
                    else draw_shots(glow, t, shots, 0.3, self.kind, depth=depth)
                )
        return glow

    def special(self, t, size):
        from special_trial119 import trail_gain, REENTRY

        self.rw.SetSize(*size)
        self.hide()
        cp = camera_pose(t)
        cam = self.cam
        cam.ParallelProjectionOff()
        cam.SetPosition(cp.x, cp.y, cp.z)
        cam.SetFocalPoint(cp.x, cp.y, 0)
        cam.SetViewUp(0, 1, 0)
        cam.SetViewAngle(cp.fov)
        cam.SetClippingRange(0.35, 80)
        units = sample(t)
        fx = []
        for i, u in enumerate(units):
            if not u.visible:
                continue
            for side, a in self.groups[i]:
                a.SetVisibility(True)
                a.SetUserMatrix(vtkmat(u.part_matrix(side)))
            fx.append(u)
        body, depth = self.capture()
        out = Image.new("RGBA", size)
        from nozzle_trial119 import project_ports

        if t >= REENTRY:
            pen = ImageDraw.Draw(out)
            for index in range(6):
                tracks = [[] for _ in range(4)]
                for ago in np.linspace(0.13, 0, 9):
                    past = t - ago
                    if past < REENTRY:
                        continue
                    history = sample(past)
                    if index >= len(history):
                        continue
                    unit = history[index]
                    for j, (_, origin, _, power) in enumerate(unit.thrusters()):
                        gain = power * trail_gain(index, t, past)
                        tracks[j].append(
                            (self.project(origin)[:2], gain)
                            if unit.visible and gain > 0.15
                            else None
                        )
                for track in tracks:
                    for k, (a, b) in enumerate(zip(track, track[1:])):
                        if a is not None and b is not None:
                            alpha = round(
                                180 * min(a[1], b[1]) * (k + 1) / max(1, len(track) - 1)
                            )
                            pen.line(
                                (tuple(a[0]), tuple(b[0])),
                                fill=(90, 175, 255, min(255, alpha)),
                                width=2,
                            )
        for u in fx:
            for _, power, jet in project_ports(
                u.thrusters(), u.transform(), lambda v: self.project(v)[:2]
            ):
                if power > 0:
                    out = draw_exhaust(out, t, power, [jet])
        out.alpha_composite(body)
        for u in fx:
            m = u.transform()

            def pr(v, m=m):
                return self.project((m @ [*v, 1])[:3])

            scale = float(
                0.55
                * 40
                / (cp.z - u.transform()[2, 3])
                * np.tan(np.radians(17))
                / np.tan(np.radians(cp.fov / 2))
            )
            out = charge(
                out,
                t + u.id * 0.371,
                getattr(u, "fire", FirePose()),
                pr,
                depth,
                scale,
                self.kind,
            )
            if residual(t) > 0:
                from combat_trial93 import charge as residual_charge

                out = residual_charge(
                    out,
                    t + u.id * 0.371,
                    FirePose("charge", charge=residual(t)),
                    pr,
                    depth,
                    scale,
                    self.kind,
                )
            if t >= SHOT:
                out = beam(
                    out,
                    getattr(u, "fire", FirePose()),
                    lambda v: self.project(v),
                    shot_matrix(u.id),
                    self.kind,
                    depth,
                )
        return out

    def close(self):
        self.rw.Finalize()
