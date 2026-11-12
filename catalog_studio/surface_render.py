"""Bounded alpha compositing of projected mesh faces for the Tk preview."""
import math
from PIL import Image, ImageDraw
from . import geometry_scene as geometry


def feature_edges(mesh,view_direction,crease_angle=35,visible_only=False):
    """Contours and creases, without tessellation edges on smooth surfaces."""
    if not mesh.vertices:return []
    lo=[min(p[i] for p in mesh.vertices) for i in range(3)]
    span=max(max(p[i] for p in mesh.vertices)-lo[i] for i in range(3)) or 1
    points=[tuple((p[i]-lo[i])/span for i in range(3)) for p in mesh.vertices]
    welded={};indices=[]
    for i,point in enumerate(points):indices.append(welded.setdefault(tuple(round(v,10) for v in point),i))
    edges={}
    for face in mesh.faces:
        if len(face)<3:continue
        origin=points[face[0]];normal=(0,0,0)
        for i in range(1,len(face)-1):normal=geometry.add(normal,geometry.cross(geometry.sub(points[face[i]],origin),geometry.sub(points[face[i+1]],origin)))
        if math.hypot(*normal)<1e-14:continue
        normal=geometry.unit(normal)
        for i in range(len(face)):
            a,b=indices[face[i]],indices[face[(i+1)%len(face)]]
            if a!=b:edges.setdefault(tuple(sorted((a,b))),[]).append(normal)
    result=[];limit=math.cos(math.radians(crease_angle))
    for edge,normals in edges.items():
        facing=[geometry.dot(n,view_direction) for n in normals]
        if visible_only and max(facing)<-1e-9:continue
        crease=any(geometry.dot(a,b)<limit for i,a in enumerate(normals) for b in normals[i+1:])
        silhouette=min(facing)<-1e-9 and max(facing)>1e-9
        if len(normals)==1 or crease or silhouette:result.append(edge)
    return result


def alpha_surface(size,polygons,opacity):
    """Composite back-to-front faces, retaining the colour of rear geometry.

    Only each face's clipped bounding box is allocated, rather than a full-size
    intermediate image per face. This is a display mesh, not a CAD solid kernel.
    """
    width,height=size
    alpha=round(255*max(0,min(1,opacity)))
    image=Image.new('RGBA',size,(0,0,0,0))
    if not alpha:return image
    for points,color in polygons:
        if len(points)<3:continue
        left=max(0,math.floor(min(p[0] for p in points)))
        top=max(0,math.floor(min(p[1] for p in points)))
        right=min(width,math.ceil(max(p[0] for p in points))+1)
        bottom=min(height,math.ceil(max(p[1] for p in points))+1)
        if right<=left or bottom<=top:continue
        tile=Image.new('RGBA',(right-left,bottom-top),(0,0,0,0))
        rgb=tuple(int(color[i:i+2],16) for i in (1,3,5))
        ImageDraw.Draw(tile).polygon([(x-left,y-top) for x,y in points],fill=(*rgb,alpha))
        image.alpha_composite(tile,(left,top))
    return image


def inside_polygon(x,y,points):
    """Hit testing remains available when a face has no Tk fill."""
    inside=False
    for i,(ax,ay) in enumerate(points):
        bx,by=points[i-1]
        if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:inside=not inside
    return inside


def opaque_surface(size,polygons):
    """Depth-buffered opaque triangles, including Boolean cavity surfaces."""
    import numpy as np
    width,height=size;depth=np.full((height,width),-np.inf,dtype=np.float32)
    rgba=np.zeros((height,width,4),dtype=np.uint8)
    for points,zs,color in polygons:
        for i in range(1,len(points)-1):
            ids=(0,i,i+1);p=[points[j] for j in ids];z=[zs[j] for j in ids]
            left=max(0,int(math.floor(min(x for x,y in p))));right=min(width,int(math.ceil(max(x for x,y in p)))+1)
            top=max(0,int(math.floor(min(y for x,y in p))));bottom=min(height,int(math.ceil(max(y for x,y in p)))+1)
            if right<=left or bottom<=top:continue
            (ax,ay),(bx,by),(cx,cy)=p
            determinant=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
            if abs(determinant)<1e-10:continue
            yy,xx=np.mgrid[top:bottom,left:right];xx=xx+.5;yy=yy+.5
            u=((by-cy)*(xx-cx)+(cx-bx)*(yy-cy))/determinant
            v=((cy-ay)*(xx-cx)+(ax-cx)*(yy-cy))/determinant;w=1-u-v
            zz=u*z[0]+v*z[1]+w*z[2];target=depth[top:bottom,left:right]
            mask=(u>=-1e-7)&(v>=-1e-7)&(w>=-1e-7)&(zz>=target)
            target[mask]=zz[mask]
            rgba[top:bottom,left:right][mask]=tuple(int(color[k:k+2],16) for k in (1,3,5))+(255,)
    return Image.fromarray(rgba),depth


def visible_segments(a,b,za,zb,depth):
    import numpy as np
    height,width=depth.shape;steps=max(2,int(math.hypot(b[0]-a[0],b[1]-a[1]))+1)
    t=np.linspace(0,1,steps);xs=a[0]+(b[0]-a[0])*t;ys=a[1]+(b[1]-a[1])*t;zs=za+(zb-za)*t
    good=(xs>=0)&(xs<width)&(ys>=0)&(ys<height);indices=np.where(good)[0]
    good[indices]&=zs[indices]>=depth[ys[indices].astype(int),xs[indices].astype(int)]-.003
    segments=[];start=None
    for i,visible in enumerate(good):
        if visible and start is None:start=i
        if start is not None and (not visible or i==steps-1):
            end=i if visible else i-1
            if end>start:segments.append(((float(xs[start]),float(ys[start])),(float(xs[end]),float(ys[end]))))
            start=None
    return segments
