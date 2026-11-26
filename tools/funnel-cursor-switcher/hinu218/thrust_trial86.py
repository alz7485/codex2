"""Visual-only twin exhaust. Pillow; no input hooks or OS control."""
import math
from PIL import Image, ImageDraw, ImageFilter

def clamp(x): return max(0.,min(1.,x))
def smooth(x):
    x=clamp(x); return x*x*(3-2*x)
class Thrust:
    def __init__(self): self.reset()
    def reset(self): self.last=None; self.power=0.; self.speed=0.
    def update(self,t,xy,enabled=True,context=None):
        xy=tuple(xy)
        if len(xy)!=2 or not all(math.isfinite(v) for v in (t,*xy)): raise ValueError('invalid time or coordinates')
        old=self.last
        if not enabled or old is None or t<old[0] or t-old[0]>.25 or math.dist(xy,old[1])>500 or context!=old[2] or (t==old[0] and xy!=old[1]): self.reset()
        elif t>old[0]:
            dt=t-old[0]; speed=math.dist(xy,old[1])/dt
            acc=max(-2500.,min(2500.,(speed-self.speed)/dt))
            self.speed+=(1-math.exp(-dt/.09))*(speed-self.speed)
            target=clamp(self.speed/470+max(0,acc)/4500)
            tau=.075 if target>self.power else .16
            self.power+=(1-math.exp(-dt/tau))*(target-self.power)
            if self.power<.003:self.power=0.
        self.last=(t,xy,context) if enabled else None
        return self.power

def draw_exhaust(background,t,power,nozzles):
    """Each nozzle: (anchor_xy, rear_vector_xy per model unit, halfwidth_px).
    Draw on unobstructed rear views; other views need host depth clipping."""
    if not math.isfinite(t) or not math.isfinite(power): raise ValueError('invalid time/power')
    out=background.convert('RGBA').copy(); p=clamp(power)
    if p==0: return out
    for i,(anchor,rear,w0) in enumerate(nozzles):
        x,y=anchor; vx,vy=rear; scale=math.hypot(vx,vy)
        if not all(math.isfinite(v) for v in (x,y,vx,vy,w0)) or w0<0: raise ValueError('invalid projection')
        if scale<1e-6: continue
        dx,dy=vx/scale,vy/scale; nx,ny=-dy,dx
        pulse=.95+.05*math.sin(t*math.tau*17+i*1.4)
        length=scale*(.12+2.45*p**.82)*pulse; w=max(.65,w0)*(.76+.24*p)
        def q(a,b): return (x+dx*a+nx*b,y+dy*a+ny*b)
        def shape(layer,extent,width,color,alpha):
            d=ImageDraw.Draw(layer); prof=[(0,.73),(.12,1),(.36,.83),(.65,.48),(.86,.20),(1,0)]
            pts=[q(length*extent*u,w*width*v) for u,v in prof]+[q(length*extent*u,-w*width*v) for u,v in reversed(prof)]
            d.polygon(pts,fill=(*color,round(alpha*p)))
        # Local crop limits work to the effect footprint.
        radius=max(length*1.1, w*5)+8; l=max(0,math.floor(x-radius)); r=min(out.width,math.ceil(x+radius)); top=max(0,math.floor(y-radius)); bot=min(out.height,math.ceil(y+radius))
        if r<=l or bot<=top:continue
        x-=l;y-=top; local=out.crop((l,top,r,bot))
        for extent,width,color,alpha,blur in [(1.05,1.8,(28,108,255),110,.95),(1,1.35,(39,116,255),135,.48),(.84,.90,(35,180,255),190,.26),(.60,.54,(130,231,255),235,.15),(.32,.27,(244,255,255),255,.07)]:
            layer=Image.new('RGBA',local.size);shape(layer,extent,width,color,alpha);local.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(.25,w*blur))))
        base=Image.new('RGBA',local.size);d=ImageDraw.Draw(base);d.line([q(0,-w*.65),q(0,w*.65)],fill=(216,251,255,round(245*p)),width=max(1,round(w*.28)));local.alpha_composite(base.filter(ImageFilter.GaussianBlur(max(.25,w*.15))))
        out.paste(local,(l,top))
    return out

def demo_power(t):
    if t<.45:return 0.
    if t<.85:return .32*smooth((t-.45)/.4)
    if t<1.55:return .32+.68*smooth((t-.85)/.7)
    if t<2.2:return 1.
    if t<2.9:return 1-.8*smooth((t-2.2)/.7)
    return .2*(1-smooth((t-2.9)/.6))
