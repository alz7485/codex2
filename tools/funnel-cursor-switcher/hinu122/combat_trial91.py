"""Fixed U-shape, inward travelling electric arcs, visual-only."""
import math
from PIL import Image, ImageDraw, ImageFilter
from fire_trial89 import Fire, FirePose, smooth, FIRE, AFTER
from combat_trial90 import Combat as Previous, beam
CHARGE=.52
RECOVER=.18
class FixedFire(Fire):
    def up(self,t):
        if not math.isfinite(t) or self.start is None or self.release is not None or t<self.last:return False
        self.release=max(t,self.start+CHARGE);self.last=t;return True
    def update(self,t,enabled=True,context=None):
        if not math.isfinite(t) or not enabled or (self.last is not None and (t<self.last or t-self.last>.25 or (self.context is not None and context!=self.context))):self.reset();return FirePose()
        self.last=t;self.context=context
        if self.start is None:return FirePose()
        if self.release is None or t<self.release:return FirePose('charge',0.,smooth((t-self.start)/CHARGE))
        a=t-self.release
        if a<FIRE:return FirePose('fire',0.,0.,.13*math.sin(math.pi*min(1,a/.12)),a)
        if a<FIRE+AFTER:return FirePose('afterglow',0.,0.,0.,a)
        if a<FIRE+AFTER+RECOVER:return FirePose('recover',0.,0.,0.,a)
        self.reset();return FirePose()
class Combat(Previous):
    def __init__(self):
        super().__init__();self.fire=FixedFire()
# Inner faces of actual rails on both models, offset into channel.
RAILS=tuple((sign*x,.264*y,z) for sign in (-1,1) for y in (-1,1) for x,z in ((.745,-.715),(.763,-1.611),(.786,-2.753)))
MUZZLE=(0.,0.,-4.20)
def arcs(t,q):
    if q<=0:return []
    out=[]
    for k,(x,y,z) in enumerate(RAILS):
        phase=(t*(2.5+.13*(k%3))+k*.137)%1
        lo=max(0.,phase-.48);hi=phase;pts=[]
        for j in range(13):
            u=lo+(hi-lo)*j/12;taper=math.sin(math.pi*u)
            pts.append((x*(1-u),y*(1-u)+.12*taper*math.sin(j*2.8+k*1.7+int(t*24)*.9),z+(-3.80-z)*u+.20*taper*math.sin(j*2.1+k*2.4+int(t*24)*1.2)))
        out.append((pts,q*min(1.,phase*8,(1-phase)*10)))
    return out

def charge(im,t,p,project,depth=None,scale=1.):
    if p.charge<=0:return im
    a=Image.new('RGBA',im.size);d=ImageDraw.Draw(a);q=p.charge;w,h=im.size
    def visible(pt):
        x,y,z=pt;ix,iy=round(x),round(y)
        return 0<=ix<w and 0<=iy<h and (depth is None or z<=float(depth[iy,ix])+.002)
    for pts,strength in arcs(t,q):
        pp=[project(v) for v in pts]
        for u,v in zip(pp,pp[1:]):
            n=max(1,math.ceil(math.dist(u[:2],v[:2])/1.5))
            for j in range(n):
                a0=tuple(x+(y-x)*j/n for x,y in zip(u,v));a1=tuple(x+(y-x)*(j+1)/n for x,y in zip(u,v));mid=tuple((x+y)*.5 for x,y in zip(a0,a1))
                if visible(mid):
                    d.line([a0[:2],a1[:2]],fill=(57,155,255,round(200*strength)),width=max(1,round(3*scale)))
                    d.line([a0[:2],a1[:2]],fill=(224,249,255,round(250*strength)),width=max(1,round(scale)))
    for point,r,clr in [(MUZZLE,(2+5*q)*scale,(79,167,255,round(210*q))),(MUZZLE,(1+2*q)*scale,(240,253,255,round(250*q)))]:
        x,y,z=project(point)
        if visible((x,y,z)):d.ellipse((x-r,y-r,x+r,y+r),fill=clr)
    out=im.convert('RGBA');out.alpha_composite(a.filter(ImageFilter.GaussianBlur(max(.7,2.2*scale))));out.alpha_composite(a);return out
