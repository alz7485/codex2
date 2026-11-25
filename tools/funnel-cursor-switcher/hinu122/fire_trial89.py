"""Visual-only fire controller, seconds and physical pixels. No OS hooks."""
import math
from dataclasses import dataclass
from PIL import Image,ImageDraw,ImageFilter
OPEN=.34; FIRE=.16; AFTER=.24; CLOSE=.42
def smooth(x):
 x=max(0.,min(1.,x));return x*x*(3-2*x)
@dataclass(frozen=True)
class FirePose:
 stage:str='idle'; angle:float=0.; charge:float=0.; recoil:float=0.; age:float=0.
class Fire:
 def __init__(self):self.reset()
 def reset(self):self.start=self.release=self.last=self.origin=self.context=None
 cancel=reset
 def down(self,t):
  if not math.isfinite(t) or self.start is not None or (self.last is not None and t<self.last):return False
  self.start=t;self.last=t;return True
 def up(self,t):
  if not math.isfinite(t) or self.start is None or self.release is not None or t<self.last:return False
  self.release=max(t,self.start+OPEN+.18);self.last=t;return True
 def update(self,t,enabled=True,context=None):
  if not math.isfinite(t) or not enabled or (self.last is not None and (t<self.last or t-self.last>.25 or (self.context is not None and context!=self.context))):self.reset();return FirePose()
  self.last=t;self.context=context
  if self.start is None:return FirePose()
  e=t-self.start
  if e<OPEN:return FirePose('opening',30*smooth(e/OPEN),.18*smooth(e/OPEN))
  if self.release is None or t<self.release:return FirePose('charge',30,.18+.82*smooth((e-OPEN)/.18))
  a=t-self.release
  if a<FIRE:return FirePose('fire',30,0,.13*math.sin(math.pi*min(1,a/.12)),a)
  if a<FIRE+AFTER:return FirePose('afterglow',30,0,0,a)
  if a<FIRE+AFTER+CLOSE:return FirePose('closing',30*(1-smooth((a-FIRE-AFTER)/CLOSE)),0,0,a)
  self.reset();return FirePose()
 def anchor(self,p,muzzle,direction):
  if p.stage not in ('fire','afterglow'):return None
  if self.origin is None:
   n=math.hypot(*direction)
   if n<1e-6:return None
   self.origin=(tuple(muzzle),tuple(x/n for x in direction))
  return self.origin

def draw_charge(im,t,p,grid,muzzle,holes,scale=1.):
 if p.charge<=0:return im
 a=Image.new('RGBA',im.size);d=ImageDraw.Draw(a);q=p.charge*(.93+.07*math.sin(t*36));gx,gy=grid;mx,my=muzzle
 def dot(pt,r,col):
  x,y=pt;d.ellipse((x-r,y-r,x+r,y+r),fill=col)
 d.line([tuple(grid),tuple(muzzle)],fill=(81,148,255,int(85*q)),width=max(1,round(10*scale*q)))
 for pt in holes:dot(pt,1.8*scale,(132,220,255,int(210*q)))
 for i in range(12):
  u=(t*2.6+i/12)%1;off=math.sin(i*2.4+t*12)*5*scale*math.sin(math.pi*u);dx,dy=mx-gx,my-gy;n=max(1,math.hypot(dx,dy));dot((gx+dx*u-dy/n*off,gy+dy*u+dx/n*off),1.2*scale,(192,239,255,int(230*q)))
 dot(muzzle,(2+5*q)*scale,(112,190,255,int(190*q)));dot(muzzle,(1+2*q)*scale,(240,252,255,int(245*q)))
 out=im.convert('RGBA');out.alpha_composite(a.filter(ImageFilter.GaussianBlur(3*scale)));out.alpha_composite(a);return out

def draw_beam(im,p,anchor,scale=1.):
 if anchor is None:return im
 o,v=anchor;age=p.age;length=135*scale;end=length*smooth(age/.055);start=length*smooth((age-FIRE)/AFTER);fade=1-smooth((age-FIRE)/AFTER)
 if end<=start:return im
 a=Image.new('RGBA',im.size);d=ImageDraw.Draw(a)
 def pt(x,y=0):return (o[0]+v[0]*x-v[1]*y,o[1]+v[1]*x+v[0]*y)
 for w,c in [(19,(54,111,255,90)),(11,(66,176,255,175)),(6,(132,224,255,220)),(2,(244,254,255,255))]:d.line([pt(start),pt(end)],fill=(*c[:3],int(c[3]*fade)),width=max(1,round(w*scale*max(.25,fade))))
 if age<.13:
  r=(4+20*age/.13)*scale;alpha=int(200*(1-age/.13));d.line([pt(3*scale+r*.28*math.cos(i*math.tau/48),r*math.sin(i*math.tau/48)) for i in range(49)],fill=(174,224,255,alpha),width=max(1,round(scale)))
  x,y=o;rr=7*scale*(1-age/.13);d.ellipse((x-rr,y-rr,x+rr,y+rr),fill=(230,251,255,alpha))
 out=im.convert('RGBA');out.alpha_composite(a.filter(ImageFilter.GaussianBlur(3*scale)));out.alpha_composite(a);return out
