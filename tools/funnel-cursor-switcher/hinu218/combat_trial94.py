"""Root-origin beam, frozen screen-space shot and approximate depth occlusion."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from .combat_trial93 import Combat as Previous, charge, beam as old_beam, PALETTES
MUZZLE=(0.,0.,2.925) # just forward of the bridge face at z=2.945
FORWARD_POINT=(0.,0.,1.925)
class Combat(Previous):
    def __init__(self):
        super().__init__(); self.shot_depth=None; self.shot_length=None
    def reset(self):
        super().reset(); self.shot_depth=None; self.shot_length=None
    def projected(self,t,xy,p,nozzles,muzzle,direction,enabled=True,context=None,fixed=False,*,depth_origin=None,depth_per_pixel=None,channel_pixels=None):
        if self.fire.origin is None or p.fire.stage not in ('fire','afterglow'):self.shot_depth=None; self.shot_length=None
        anchor=super().projected(t,xy,p,nozzles,muzzle,direction,enabled,context,fixed)
        if anchor is not None and self.shot_depth is None and depth_origin is not None and depth_per_pixel is not None:
            if math.isfinite(depth_origin) and math.isfinite(depth_per_pixel): self.shot_depth=(float(depth_origin),float(depth_per_pixel))
        if anchor is not None and self.shot_length is None and channel_pixels is not None and math.isfinite(channel_pixels):self.shot_length=max(0.,float(channel_pixels))
        if anchor is None:self.shot_depth=None; self.shot_length=None
        return anchor

def beam(im,p,anchor,scale=1.,kind='HiNu',*,depth=None,shot_depth=None,channel_pixels=0.):
    if anchor is None:return im
    if depth is None or shot_depth is None:return extended_beam(im,p,anchor,scale,kind,channel_pixels)
    layer=extended_beam(Image.new('RGBA',im.size),p,anchor,scale,kind,channel_pixels)
    a=np.array(layer); h,w=a.shape[:2]; d=np.asarray(depth)
    if d.shape!=(h,w):raise ValueError('depth size mismatch')
    (ox,oy),(vx,vy)=anchor; z,dz=shot_depth
    yy,xx=np.ogrid[:h,:w]; dist=(xx-ox)*vx+(yy-oy)*vy
    visible=(z+np.maximum(0,dist)*dz <= d+.0008)
    a[:,:,3]=np.where(visible,a[:,:,3],0)
    out=im.convert('RGBA');out.alpha_composite(Image.fromarray(a));return out

from .fire_trial89 import smooth, FIRE, AFTER

def draw_beam(im,p,anchor,scale=1.,kind="HiNu",channel_pixels=0.):
 outer,inner,white=PALETTES[kind]
 if anchor is None:return im
 o,v=anchor;age=p.age;length=135*scale+channel_pixels;end=length*smooth(age/.055);start=length*smooth((age-FIRE)/AFTER);fade=1-smooth((age-FIRE)/AFTER)
 if end<=start:return im
 a=Image.new('RGBA',im.size);d=ImageDraw.Draw(a)
 def pt(x,y=0):return (o[0]+v[0]*x-v[1]*y,o[1]+v[1]*x+v[0]*y)
 for w,c in [(19,(*outer,90)),(11,(*inner,175)),(6,(*inner,220)),(2,(*white,255))]:d.line([pt(start),pt(end)],fill=(*c[:3],int(c[3]*fade)),width=max(1,round(w*scale*max(.25,fade))))
 if age<.13:
  r=(4+20*age/.13)*scale;alpha=int(200*(1-age/.13));d.line([pt(3*scale+r*.28*math.cos(i*math.tau/48),r*math.sin(i*math.tau/48)) for i in range(49)],fill=(*inner,alpha),width=max(1,round(scale)))
  x,y=o;rr=7*scale*(1-age/.13);d.ellipse((x-rr,y-rr,x+rr,y+rr),fill=(*white,alpha))
 out=im.convert('RGBA');out.alpha_composite(a.filter(ImageFilter.GaussianBlur(3*scale)));out.alpha_composite(a);return out

def extended_beam(im,p,anchor,scale=1.,kind="HiNu",channel_pixels=0.):
    outer,inner,white=PALETTES[kind]
    out=draw_beam(im,p,anchor,scale,kind,channel_pixels)
    if anchor is None:return out
    o,v=anchor; age=p.age; end=(135*scale+channel_pixels)*smooth(age/.055); start=(135*scale+channel_pixels)*smooth((age-FIRE)/AFTER); fade=1-smooth((age-FIRE)/AFTER)
    if end<=start:return out
    a=Image.new('RGBA',im.size);d=ImageDraw.Draw(a)
    def pt(x,y=0):return(o[0]+v[0]*x-v[1]*y,o[1]+v[1]*x+v[0]*y)
    for k in range(9):
        u=(k*.137+age*3)%1; x=start+(end-start)*u; y=math.sin(k*2.4+age*24)*4*scale*fade
        d.line([pt(max(start,x-5*scale),y),pt(x,y)],fill=(*white,round(210*fade)),width=max(1,round(scale)))
    if age<.12:
        for k in range(8):
            angle=k*math.tau/8; x=(5+age*90)*scale; y=math.sin(angle)*x; z=math.cos(angle)*x*.6
            d.line([pt(z*.45,y*.45),pt(z,y)],fill=(*white,round(210*(1-age/.12))),width=max(1,round(scale)))
    out.alpha_composite(a.filter(ImageFilter.GaussianBlur(max(.4,scale))));out.alpha_composite(a);return out
