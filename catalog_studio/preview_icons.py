"""Native cube and grid-plane glyphs in the preview's default 3D view."""
import tkinter as tk
from .point_geometry import Camera, PLANES


def create(master, plane='立体'):
    size=24
    image=tk.PhotoImage(master=master,width=size,height=size)
    camera=Camera();camera.zoom=7.5
    def project(point):return tuple(round(v) for v in camera.project(point,size,size))
    def line(a,b,color):
        x,y=a;u,v=b;n=max(abs(u-x),abs(v-y),1)
        for i in range(n+1):image.put(color,(round(x+(u-x)*i/n),round(y+(v-y)*i/n)))
    def polygon(points,color,outline):
        for y in range(size):
            for x in range(size):
                inside=False
                for a,b in zip(points,points[1:]+points[:1]):
                    if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
                if inside:image.put(color,(x,y))
        for a,b in zip(points,points[1:]+points[:1]):line(a,b,outline)
    # The plane passes through the centre of a small solid box. All planes
    # share Camera's 3D projection, including XZ (never a face-on square).
    if plane!='立体':
        first,second=PLANES[plane]
        def on_plane(a,b):
            point=[0,0,0];point[first]=a;point[second]=b
            return project(point)
        polygon([on_plane(a,b) for a,b in ((-1,-1),(1,-1),(1,1),(-1,1))],'#e6f1ff','#4385d0')
        for offset in (-.5,0,.5):
            line(on_plane(offset,-1),on_plane(offset,1),'#a8c9ed')
            line(on_plane(-1,offset),on_plane(1,offset),'#a8c9ed')
    extent=.8 if plane=='立体' else .45
    # +Z, -Y and -X are the visible faces for the default yaw/pitch.
    for vertices,color in (
        (((-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)),'#d2e6ff'),
        (((-1,-1,-1),(1,-1,-1),(1,-1,1),(-1,-1,1)),'#4288e8'),
        (((-1,-1,-1),(-1,1,-1),(-1,1,1),(-1,-1,1)),'#58c4df'),
    ):
        polygon([project(tuple(extent*v for v in vertex)) for vertex in vertices],color,'#42638c')
    return image
