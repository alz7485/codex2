"""Combined visual controller: no OS hooks; seconds, physical pixels."""
import math
from dataclasses import dataclass
from flight_trial87 import Flight
from fire_trial89 import Fire, draw_charge, draw_beam, smooth, FIRE, AFTER
from trail_trial88 import Trail
from PIL import Image, ImageDraw, ImageFilter
@dataclass(frozen=True)
class CombatPose:
    flight: object
    fire: object
class Combat:
    def __init__(self):
        self.flight=Flight(); self.fire=Fire(); self.trail=Trail(); self.last=None
    def reset(self):
        self.flight.reset(); self.fire.cancel(); self.trail.reset(); self.last=None
    def down(self,t): return self.fire.down(t)
    def up(self,t): return self.fire.up(t)
    def update(self,t,xy,enabled=True,context=None,fixed=False):
        xy=tuple(xy)
        if len(xy)!=2 or not all(math.isfinite(v) for v in (t,*xy)): self.reset(); raise ValueError('invalid input')
        key=(context,bool(fixed)); old=self.last
        if not enabled or (old is not None and (t<old[0] or t-old[0]>.25 or math.dist(xy,old[1])>500 or key!=old[2] or (t==old[0] and xy!=old[1]))): self.reset()
        f=self.flight.update(t,xy,enabled,context,fixed); s=self.fire.update(t,enabled,key)
        self.last=(t,xy,key) if enabled else None
        return CombatPose(f,s)
    def projected(self,t,xy,p,nozzles,muzzle,direction,enabled=True,context=None,fixed=False):
        self.trail.update(t,xy,p.flight,nozzles,enabled,context,fixed)
        return self.fire.anchor(p.fire,muzzle,direction) if enabled else None

def charge(im,t,p,grid,muzzle,holes,scale=1.):
    out=draw_charge(im,t,p,grid,muzzle,holes,scale)
    if p.charge<=0:return out
    q=p.charge; a=Image.new('RGBA',im.size); d=ImageDraw.Draw(a)
    gx,gy=grid; mx,my=muzzle; dx,dy=mx-gx,my-gy; n=max(1,math.hypot(dx,dy)); nx,ny=-dy/n,dx/n
    for k in range(3):
        pts=[]
        for j in range(9):
            u=j/8; off=math.sin(math.pi*u)*math.sin(j*2.6+k*2.1+int(t*24)*1.7)*(4+4*q)*scale
            pts.append((gx+dx*u+nx*off,gy+dy*u+ny*off))
        d.line(pts,fill=(124,201,255,round(150*q*q)),width=max(1,round(scale)))
    for k in range(12):
        u=(t*2.8+k/12)%1; rad=(8+5*math.sin(k*2.4))*scale*(1-u); angle=k*2.4+t*5
        x=mx+math.cos(angle)*rad; y=my+math.sin(angle)*rad; r=max(.5,scale*(.6+q*.5))
        d.ellipse((x-r,y-r,x+r,y+r),fill=(208,241,255,round(210*q*(.4+.6*u))))
    out.alpha_composite(a.filter(ImageFilter.GaussianBlur(max(.4,2*scale))));out.alpha_composite(a);return out

def beam(im,p,anchor,scale=1.):
    out=draw_beam(im,p,anchor,scale)
    if anchor is None:return out
    o,v=anchor; age=p.age; end=135*scale*smooth(age/.055); start=135*scale*smooth((age-FIRE)/AFTER); fade=1-smooth((age-FIRE)/AFTER)
    if end<=start:return out
    a=Image.new('RGBA',im.size);d=ImageDraw.Draw(a)
    def pt(x,y=0):return(o[0]+v[0]*x-v[1]*y,o[1]+v[1]*x+v[0]*y)
    for k in range(9):
        u=(k*.137+age*3)%1; x=start+(end-start)*u; y=math.sin(k*2.4+age*24)*4*scale*fade
        d.line([pt(max(start,x-5*scale),y),pt(x,y)],fill=(186,237,255,round(210*fade)),width=max(1,round(scale)))
    if age<.12:
        for k in range(8):
            angle=k*math.tau/8; x=(5+age*90)*scale; y=math.sin(angle)*x; z=math.cos(angle)*x*.6
            d.line([pt(z*.45,y*.45),pt(z,y)],fill=(205,242,255,round(210*(1-age/.12))),width=max(1,round(scale)))
    out.alpha_composite(a.filter(ImageFilter.GaussianBlur(max(.4,scale))));out.alpha_composite(a);return out
