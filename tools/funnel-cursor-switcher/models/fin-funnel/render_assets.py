"""Bake the app poses from the edited Blender scene: blender -b model.blend -P render_assets.py -- DEST."""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

out = Path(sys.argv[-1]).resolve()
out.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
root = bpy.data.objects['Fin funnel | roll around local Y']
camera = scene.camera
scene.frame_set(1)
root.animation_data_clear()
scene.cycles.samples = 12
scene.render.resolution_x = scene.render.resolution_y = 384
scene.render.resolution_percentage = 100
scene.render.film_transparent = True

def shoot(label):
    scene.render.filepath = str(out / (label + '.png'))
    bpy.ops.render.render(write_still=True)

def view(position, forward, angle, span, target=(0,0,0)):
    camera.location = Vector(position) + Vector(target)
    track = (-Vector(position)).to_track_quat('-Z', 'Y')
    axis = track.inverted() @ Vector(forward)
    bank = math.atan2(axis.y,axis.x) - math.radians(angle)
    camera.rotation_euler = (track @ Quaternion((0,0,1),bank)).to_euler()
    camera.data.ortho_scale = span

# Capture a full roll at constant framing. The resting arrow uses roll-00.
for index in range(48):
    root.rotation_euler.y = math.tau * index / 48
    shoot(f'roll-{index:02d}')
root.rotation_euler.y = 0
view((3,1,12),(0,1,0),0,9.1)
for index, bank in enumerate((0,15,28,-15)):
    root.rotation_euler.y = math.radians(bank)
    shoot(f'flight-{index}')
root.rotation_euler.y = 0
# Rig around the two physical hinge pins. Keep the short bridge stationary.
arms = []
for obj in root.children:
    side = obj.name.split(' / ')[0]
    if side not in ('Port','Starboard') or '/ pivot' in obj.name or '/ hinge cheek' in obj.name:
        continue
    sign = -1 if side == 'Port' else 1
    arms.append((obj, sign, obj.matrix_local.copy()))

def open_arms(port, starboard):
    for obj, sign, rest in arms:
        pivot = Vector((sign*.84,-3.16,0))
        angle = port if sign < 0 else starboard
        obj.matrix_local = (Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(angle),4,'Z')
                            @ Matrix.Translation(-pivot) @ rest)

for index in range(4):
    open_arms(10*index,-10*index)
    shoot(f'open-{index}')

# Face the OUTSIDE of the two straightened panels. +X is the upper tip.
view((0,-15,0),(1,0,0),90,16)
fill = bpy.data.lights.new('Rack frontal softbox', 'AREA')
fill.energy, fill.size = 920, 9
lamp = bpy.data.objects.new(fill.name, fill)
scene.collection.objects.link(lamp)
lamp.location = (0,-8,2)
lamp.rotation_euler = (-lamp.location).to_track_quat('-Z','Y').to_euler()
for folded in (False,True):
    open_arms(-82 if folded else 90,-90)
    shoot('rack-fold' if folded else 'rack')
