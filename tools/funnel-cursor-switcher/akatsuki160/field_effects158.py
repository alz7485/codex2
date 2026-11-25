"""Green shield with separated front and rear projected layers."""
import math
import numpy as np
from PIL import Image,ImageDraw,ImageFilter,ImageChops
from flight150 import screen

def draw_field(base,field,layer='all'):
    if field is None or field.opacity<=0:return base.copy()
    p=np.array([screen(x) for x in field.nodes]); z=field.nodes[:,2]; k=field.scale; a=field.opacity
    fill=Image.new('RGBA',base.size); g=Image.new('RGB',base.size); h=Image.new('RGB',base.size)
    d=ImageDraw.Draw(fill); gd=ImageDraw.Draw(g); hd=ImageDraw.Draw(h)
    def show(depth):return layer=='all' or (layer=='front' if depth>=0 else layer=='rear')
    def line(draw,pts,col,width,power):
        if power>0:draw.line([tuple(x) for x in pts],fill=tuple(round(v*min(1,power)) for v in col),width=max(1,round(width*k)))
    for j in sorted(range(len(field.faces)),key=lambda j:np.mean(z[list(field.faces[j])])):
        face=field.faces[j]; depth=np.mean(z[list(face)]); f=field.face_progress[j]
        if not show(depth) or f<=0:continue
        v=p[list(face)]; c=v.mean(axis=0); v=c+(v-c)*f
        alpha=round(a*f*(25 if depth>=0 else 14));d.polygon([tuple(x) for x in v],fill=(18,235,118,alpha))
        u=(field.t*.8+j*.13)%1; power=a*f*math.sin(math.pi*u)**2*.15
        line(gd,[v[0]+(v[1]-v[0])*u,v[0]+(v[2]-v[0])*u],(35,255,133),2,power)
    for j,(i,l) in enumerate(field.edges):
        depth=(z[i]+z[l])/2; e=field.edge_progress[j]
        if not show(depth) or e<=0:continue
        x,y=p[i],p[l]; bright=1 if depth>=0 else .55; end=x+(y-x)*e
        line(gd,[x,end],(0,255,112),7,a*bright*.8);line(hd,[x,end],(115,255,192),1.5,a*bright)
        u=(field.t*1.6-j*.1)%1
        if u<e:line(hd,[x+(y-x)*max(0,u-.06),x+(y-x)*u],(225,255,239),2,a*bright)
    for i,x in enumerate(p):
        if not show(z[i]):continue
        power=a*max((field.edge_progress[j] for j,e in enumerate(field.edges) if i in e),default=0)
        r=max(1,3*k);gd.ellipse((x[0]-2*r,x[1]-2*r,x[0]+2*r,x[1]+2*r),fill=(0,round(255*power),round(125*power)))
        hd.ellipse((x[0]-r,x[1]-r,x[0]+r,x[1]+r),fill=(round(175*power),round(255*power),round(213*power)))
    b=Image.alpha_composite(base.convert('RGBA'),fill).convert('RGB')
    return ImageChops.add(ImageChops.add(b,g.filter(ImageFilter.GaussianBlur(max(1,3*k)))),h)
