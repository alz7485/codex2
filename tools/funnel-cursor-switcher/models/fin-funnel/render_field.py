"""Photograph four hinge poses for each of the five pyramid stations."""
import bpy
import sys
import math
from pathlib import Path
from mathutils import Vector, Matrix

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from fin_field_geometry import VERTICES, rail_directions

out = Path(sys.argv[-1])
out.mkdir(exist_ok=True,parents=True)
scene=bpy.context.scene
root=bpy.data.objects['Fin funnel | roll around local Y']
scene.frame_set(1)
root.animation_data_clear()
parts=[]
for obj in root.children:
    side=obj.name.split(' / ')[0]
    if side in ('Port','Starboard') and '/ pivot' not in obj.name and '/ hinge cheek' not in obj.name:
        parts.append((obj,-1 if side=='Port' else 1,obj.matrix_local.copy()))
camera=scene.camera
camera.location=(0,0,18)
camera.rotation_euler=(0,0,0)
camera.data.type='ORTHO'
camera.data.ortho_scale=15.5
scene.render.resolution_x=scene.render.resolution_y=192
scene.render.resolution_percentage=100
scene.cycles.samples=16
# Centre of the inner grille, just forward of the hinge bridge.
emitter=Vector((0,-3.15+.169+.036,0))
for index in range(len(VERTICES)):
    left,right=map(Vector,rail_directions(index))
    along=(right+left).normalized()
    across=(right-left).normalized()
    up=across.cross(along).normalized()
    rotation=Matrix((across,along,up)).transposed().to_4x4()
    root.matrix_world=rotation @ Matrix.Translation(-emitter)
    half_angle=left.angle(right)/2
    for pose in range(4):
        for obj,sign,rest in parts:
            pivot=Vector((sign*.84,-3.16,0))
            obj.matrix_local=(Matrix.Translation(pivot)
                @ Matrix.Rotation(-sign*half_angle*pose/3,4,'Z')
                @ Matrix.Translation(-pivot) @ rest)
        scene.render.filepath=str(out/f'{index}-{pose}.png')
        bpy.ops.render.render(write_still=True)
