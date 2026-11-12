"""Cached solid subtraction for display only; never writes catalogue attributes."""
from functools import lru_cache
import math
from . import geometry_scene as geo


def solid(mesh):
    import manifold3d as manifold
    import numpy as np
    vertices=[];lookup={};indices=[]
    scale=max((max(p[i] for p in mesh.vertices)-min(p[i] for p in mesh.vertices) for i in range(3)),default=1) or 1
    for point in mesh.vertices:
        key=tuple(round(v/scale,9) for v in point)
        if key not in lookup:lookup[key]=len(vertices);vertices.append(point)
        indices.append(lookup[key])
    triangles=[]
    for face in mesh.faces:
        face=[indices[i] for i in face];clean=[]
        for i in face:
            if not clean or clean[-1]!=i:clean.append(i)
        if len(clean)>1 and clean[0]==clean[-1]:clean.pop()
        if len(set(clean))<3:continue
        points=[vertices[i] for i in clean];origin=points[0]
        normal=geo.ZERO
        for i in range(1,len(points)-1):normal=geo.add(normal,geo.cross(geo.sub(points[i],origin),geo.sub(points[i+1],origin)))
        if math.hypot(*normal)<scale*scale*1e-12:continue
        normal=geo.unit(normal);u=geo.unit(geo.sub(points[1],origin));v=geo.cross(normal,u)
        xy=np.array([(geo.dot(geo.sub(p,origin),u),geo.dot(geo.sub(p,origin),v)) for p in points],dtype=np.float64)
        for tri in manifold.triangulate([xy]):triangles.append([clean[int(i)] for i in tri])
    volume=sum(geo.dot(vertices[a],geo.cross(vertices[b],vertices[c])) for a,b,c in triangles)
    if volume<0:triangles=[list(reversed(t)) for t in triangles]
    raw=manifold.Mesh(np.array(vertices,dtype=np.float32),np.array(triangles,dtype=np.uint32));raw.merge()
    result=manifold.Manifold(raw)
    if result.status()!=manifold.Error.NoError:raise ValueError('閉じた立体として差し引けない形状です：'+mesh.name)
    return result


@lru_cache(maxsize=48)
def difference(vertices,faces,cutters):
    try:
        original=solid(geo.Mesh('solid','正形状','',list(vertices),list(faces)))
        for cv,cf in cutters:
            original=original-solid(geo.Mesh('cut','負形状','',list(cv),list(cf)))
        result=original.to_mesh()
        return tuple(tuple(float(v) for v in p[:3]) for p in result.vert_properties),tuple(tuple(int(i) for i in t) for t in result.tri_verts)
    except ImportError as exc:raise ValueError('くり抜き表示には更新版の依存パッケージ（manifold3d / numpy）が必要です。') from exc


def subtract(mesh,cutters):
    vertices,faces=difference(tuple(mesh.vertices),tuple(tuple(f) for f in mesh.faces),tuple((tuple(c.vertices),tuple(tuple(f) for f in c.faces)) for c in cutters))
    return geo.Mesh(mesh.ident,mesh.name,mesh.kind,list(vertices),list(faces),list(mesh.lines))


def apply(scene,definition):
    """Self=all positive meshes in this GMSET; Owner=direct positive parent."""
    from . import element_schema as schema
    parents={};nodes={}
    def visit(items,parent=None):
        for node in items:
            nodes[node['id']]=node;parents[node['id']]=parent
            visit(node.get('children',[]),node['id'])
    visit(definition.get('elements',[]))
    positives=[m for m in scene.meshes if not m.negative and m.faces]
    targets={m.ident:[] for m in positives}
    for cut in scene.meshes:
        if not cut.negative or not cut.faces:continue
        try:mask=int(nodes[cut.ident]['attrs'].get('NAPP','2'))
        except (ValueError,TypeError):scene.issues.append(cut.name+'：NAPPは0〜7で指定してください。');continue
        if not 0<=mask<=7:scene.issues.append(cut.name+'：NAPPは0〜7で指定してください。');continue
        # Attached is a separate Design component, absent in a standalone GMSET.
        for mesh in positives:
            if mask&4 or mask&2 and parents.get(cut.ident)==mesh.ident:
                targets[mesh.ident].append(cut)
    result=[]
    for mesh in scene.meshes:
        cutters=targets.get(mesh.ident,[])
        if not cutters:result.append(mesh);continue
        try:
            result.append(subtract(mesh,cutters))
            scene.cut_applied.update(c.ident for c in cutters)
        except (ValueError,RuntimeError,OverflowError) as exc:
            scene.issues.append(mesh.name+'：くり抜き表示できません：'+str(exc));result.append(mesh)
    scene.meshes=result
