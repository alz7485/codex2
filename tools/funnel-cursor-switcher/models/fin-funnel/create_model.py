"""Blender 4.x: blender -b -P create_model.py -- <output folder>."""
import bpy
import math
import sys
from pathlib import Path
from mathutils import Vector, Quaternion

out = Path(sys.argv[sys.argv.index('--') + 1])
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def material(name, color, metal=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metal
    shader.inputs['Roughness'].default_value = .36
    return mat

white = material('Ivory • external armour', (.88,.895,.90), .14)
navy = material('Blue-black • internal frame', (.018,.029,.049), .35)
rib = material('Inset bevel • gunmetal', (.048,.067,.089), .48)
dark = material('Deep recess', (.006,.010,.016))
gold = material('Amber • hinge cover', (.96,.48,.016), .25)
steel = material('Pivot steel', (.21,.24,.27), .65)
red = material('Crimson tip inset', (.62,.043,.028), .18)
green = material('Emerald root marking', (.022,.36,.095), .18)
alloy = material('Pale mechanism', (.55,.58,.60), .50)
root = bpy.data.objects.new('Fin funnel | roll around local Y', None)
scene.collection.objects.link(root)
root.empty_display_size = .2

def finish(obj, name, mat, radius):
    obj.name = name
    obj.parent = root
    obj.data.materials.append(mat)
    if radius:
        bevel = obj.modifiers.new('Machined edges', 'BEVEL')
        bevel.width, bevel.segments = radius, 3
        obj.modifiers.new('Face normals', 'WEIGHTED_NORMAL')
    return obj

def block(name, pos, size, mat, bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj,name,mat,bevel)

def shell(name, sign, stations, mat, bevel, crown=False):
    # Successive chamfered cross-sections in the width/thickness plane.
    verts, faces = [], []
    for y, inner, outer, half_width in stations:
        c = min((outer-inner)*.32,.045)
        section = [(inner,-half_width+c),(inner+c,-half_width),
                   (outer-c,-half_width),(outer,-half_width+c),
                   (outer,half_width-c),(outer-c,half_width),
                   (inner+c,half_width),(inner,half_width-c)]
        if crown:
            # A broad central facet and two sloping shoulders. The section
            # rises along the blade, so the wedge is visible in silhouette.
            shoulder = (outer-inner)*.48
            section[2:6] = [(outer-shoulder, -half_width),
                            (outer, -.58*half_width),
                            (outer, .58*half_width),
                            (outer-shoulder, half_width)]
        verts.extend((sign*x,y,z) for x,z in section)
    for i in range(len(stations)-1):
        for j in range(8):
            k = (j+1)%8
            faces.append((8*i+j,8*(i+1)+j,8*(i+1)+k,8*i+k))
    faces.extend([tuple(range(8)),tuple(reversed(range(len(verts)-8,len(verts))))])
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(obj)
    return finish(obj,name,mat,bevel)

def recess(obj, name, pos, size):
    # Cut through the white armour; the navy substrate forms the floor.
    cutter = block(name+' tool',pos,size,dark,0)
    subtract(obj, cutter, name)

def subtract(obj, cutter, name):
    modifier = obj.modifiers.new(name,'BOOLEAN')
    modifier.object = cutter
    modifier.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_move_to_index(modifier=modifier.name,index=0)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter,do_unlink=True)

base, tip = -3.15, 3.36
# Half widths, thickness and crown height vary together towards the blunt tip.
armour = [(base+.08,.97,1.10,.50),(-1.78,.98,1.40,.55),
          (.65,.965,1.22,.462),(2.92,.95,1.055,.364),(tip,.947,1.026,.345)]
spar = [(base,.71,.98,.50),(-2.48,.73,1.01,.54),(.4,.79,1.0,.465),
        (2.86,.85,.98,.355),(tip-.04,.90,.975,.332)]

def section_at(stations,y):
    for left,right in zip(stations,stations[1:]):
        if y <= right[0]:
            t=(y-left[0])/(right[0]-left[0])
            return (y, *(a+(b-a)*t for a,b in zip(left[1:],right[1:])))
    return stations[-1]

def face_block(name, sign, stations, face_index, y, z, size, offset, mat):
    x=section_at(stations,y)[face_index]
    slope=(section_at(stations,y+.001)[face_index]-x)/.001
    obj=block(name,(sign*(x+offset),y,z),size,mat,.007)
    obj.rotation_euler.z=-math.atan(sign*slope)
    return obj

for sign, side in [(-1,'Port'),(1,'Starboard')]:
    shell(side+' / inner spar',sign,spar,navy,.019)
    # Individual crosswise panels sit on a continuous spar. A short taper
    # at each panel end catches the light along the narrow joint.
    ends=[armour[0][0],-2.12,-.57,.78,2.74,tip]
    panels=[]
    for index,(start,end) in enumerate(zip(ends,ends[1:])):
        start+=.009 if index else 0
        end-=.009 if index<len(ends)-2 else 0
        ys=sorted({start,start+.043,end-.043,end,*[s[0] for s in armour if start<s[0]<end]})
        stations=[]
        for y in ys:
            _,inner,outer,width=section_at(armour,y)
            lip=.022 if (y==start and index or y==end and index<len(ends)-2) else 0
            stations.append((y,inner,outer-lip,width-lip))
        panels.append(shell(f'{side} / armour {index+1}',sign,stations,white,.010,crown=True))
    recess(panels[2],'Single slit',(sign*1.17,-.34,0),(.66,.35,.076))
    for panel,y,length,width,mat,label in [
            (panels[-1],3.04,.34,.175,red,'tip'),
            (panels[0],-2.57,.19,.31,green,'root')]:
        x=section_at(armour,y)[2]
        recess(panel,'Recess for '+label,(sign*x,y,0),(.55,length,width))
        face_block(side+' / '+label+' inlay',sign,armour,2,y,0,
                   (.028,length-.018,width-.018),-.033,mat)
    # Raised paired pale tracks on the thick shoulder.
    for z in (-.118,.118):
        face_block(side+' / track bed',sign,armour,2,-1.39,z,(.028,.94,.095),.013,rib)
        face_block(side+' / pale guide',sign,armour,2,-1.39,z,(.063,.78,.070),.046,alloy)
        for y in (-1.66,-1.14):
            face_block(side+' / guide collar',sign,armour,2,y,z,(.082,.09,.10),.048,white)
    # Ribbed inner bays, interrupted by a framed rectangular socket.
    for center,length,count in [(-1.67,.81,10),(-.59,.76,9),(3.08,.30,5)]:
        face_block(side+' / channel floor',sign,spar,1,center,0,
                   (.020,length,.49),-.010,dark)
        for j in range(count):
            y=center+length*((j+.5)/count-.5)
            face_block(side+' / fine transverse rib',sign,spar,1,y,0,
                       (.027,.026,.46),-.025,rib)
    for y in (-1.09,1.61):
        face_block(side+' / socket rim',sign,spar,1,y,0,(.043,.28,.20),-.020,rib)
        face_block(side+' / socket inset',sign,spar,1,y,0,(.010,.19,.12),-.043,dark)
    for z in (-.285,.285):
        block(side+' / hinge cheek',(sign*.84,base-.055,z),(.43,.52,.37),gold,.052)
    bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.195,depth=1.01,
                                        location=(sign*.84,base-.01,0))
    finish(bpy.context.object,side+' / pivot',rib,.015)
    for z in (-.511,.511):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=.088,depth=.022,
                                            location=(sign*.84,base-.01,z))
        finish(bpy.context.object,side+' / pivot pin',steel,.009)

block('Bridge / central navy enclosure',(0,base-.115,0),(1.64,.48,1.015),navy,.065)
block('Bridge / internal well',(0,base+.128,0),(.76,.055,.60),dark,.032)
grille=block('Bridge / perforated face',(0,base+.169,0),(.79,.072,.66),steel,.024)
for row in range(3):
    for column in range(5 if row!=1 else 4):
        x=(column-(2 if row!=1 else 1.5))*.145
        bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=.048,depth=.22,
            location=(x,base+.17,(row-1)*.156),rotation=(math.pi/2,0,0))
        subtract(grille,bpy.context.object,'Perforation')
block('Bridge / rear yellow surround',(0,base-.361,0),(.59,.048,.53),gold,.022)
block('Bridge / rear recess',(0,base-.39,0),(.44,.032,.38),dark,.017)

block('Bridge / gold centre bar',(0,base-.413,0),(.42,.038,.046),gold,.007)

for obj in list(root.children):
    obj.select_set(True)
root.select_set(True)
bpy.context.view_layer.objects.active=root
bpy.ops.export_scene.gltf(filepath=str(out/'fin-funnel.glb'),use_selection=True,
                          export_apply=True,export_format='GLB',export_animations=False)

# Fixed camera; compose the projection of the local forward axis at upper-left.
cam_data=bpy.data.cameras.new('Orthographic camera')
cam=bpy.data.objects.new('Camera',cam_data)
scene.collection.objects.link(cam)
cam.location=(7,4.2,10)
track=(-cam.location).to_track_quat('-Z','Y')
forward=track.inverted() @ Vector((0,1,0))
roll=math.atan2(forward.y,forward.x)-math.radians(128)
cam.rotation_euler=(track @ Quaternion((0,0,1),roll)).to_euler()
cam_data.type='ORTHO'
cam_data.ortho_scale=8.35
scene.camera=cam

def area(name,position,energy,size):
    light=bpy.data.lights.new(name,'AREA')
    light.energy,light.shape,light.size=energy,'DISK',size
    obj=bpy.data.objects.new(name,light)
    scene.collection.objects.link(obj)
    obj.location=position
    obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()

area('Softbox', (2,3,8),850,7)
area('Edge light',(-4,-2,4),640,5)
area('Fill',(5,-4,-2),460,5)
scene.world=bpy.data.worlds.new('Studio')
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.12,.15,.20,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.55
scene.render.engine='CYCLES'
scene.cycles.samples=12
scene.cycles.use_denoising=False
bpy.context.preferences.filepaths.save_version=0
scene.render.film_transparent=True
scene.render.resolution_x=scene.render.resolution_y=580
scene.render.resolution_percentage=100
scene.render.image_settings.color_mode='RGBA'
scene.render.fps=12
scene.frame_start,scene.frame_end=1,36
for frame,angle in [(1,0),(37,math.tau)]:
    root.rotation_euler.y=angle
    root.keyframe_insert(data_path='rotation_euler',index=1,frame=frame)
for curve in root.animation_data.action.fcurves:
    for k in curve.keyframe_points:
        k.interpolation='LINEAR'
scene.frame_set(1)
for screen in bpy.data.screens:
    for area_ui in screen.areas:
        if area_ui.type=='VIEW_3D':
            area_ui.spaces.active.region_3d.view_perspective='CAMERA'
            area_ui.spaces.active.overlay.show_overlays=False
            area_ui.spaces.active.shading.color_type='MATERIAL'
scene.render.filepath='//frames/roll-'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'fin-funnel.blend'))
(out/'frames').mkdir(exist_ok=True)
for frame in range(1,37):
    scene.frame_set(frame)
    scene.render.filepath=str(out/'frames'/f'roll-{frame:02d}.png')
    bpy.ops.render.render(write_still=True)
