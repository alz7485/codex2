"""Effect-only exhaust filaments and independent lateral afterglow."""
import math
from collections import deque
from PIL import Image, ImageDraw, ImageFilter
from thrust_trial86 import clamp,draw_exhaust as old_exhaust
from trail_trial88 import Sample
class SideTrails:
    def __init__(self,lifetime=.18,max_length=48.):
        self.lifetime=lifetime;self.max_length=max_length;self.reset()
    def reset(self):
        self.last=None;self.tracks=[deque(maxlen=32),deque(maxlen=32)];self.live=[False,False]
    def update(self,t,xy,jets,enabled=True,context=None):
        xy=tuple(map(float,xy));t=float(t)
        if len(xy)!=2 or not all(math.isfinite(v) for v in (t,*xy)):raise ValueError('invalid trail input')
        old=self.last
        if not enabled or old is None or t<old[0] or t-old[0]>.25 or math.dist(xy,old[1])>500 or context!=old[2] or (t==old[0] and xy!=old[1]):self.reset();old=None
        if not enabled:return self
        moving=old is not None and t>old[0] and math.dist(xy,old[1])/(t-old[0])>8
        by_group={port.group:(p,jet) for port,p,jet in jets}
        for i,g in enumerate(('side_minus','side_plus')):
            track=self.tracks[i]
            while track and (track[0] is None or t-track[0].t>=self.lifetime):track.popleft()
            p,jet=by_group.get(g,(0,None));active=moving and p>.08 and jet is not None
            if active:
                a,v,w=jet;pt=tuple(a[k]+v[k]*.18 for k in range(2))
                if not self.live[i] and track:track.append(None)
                track.append(Sample(t,pt,float(p),max(.6,min(3.,w))))
            items=[s for s in track if s is not None];length=0.;keep=1
            for a,b in zip(items[::-1],items[-2::-1]):
                length+=math.dist(a.xy,b.xy)
                if length>self.max_length:break
                keep+=1
            while len([s for s in track if s is not None])>keep:track.popleft()
            self.live[i]=bool(active)
        self.last=(t,xy,context);return self

def draw_side_trails(background,t,controller):
    out=background.convert('RGBA').copy()
    for width,color,alpha,blur in ((4,(40,110,255),72,1.4),(1.2,(177,231,255),180,.35)):
        layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
        for track in controller.tracks:
            for a,b in zip(track,list(track)[1:]):
                if a is None or b is None:continue
                fade=clamp(1-(t-(a.t+b.t)/2)/controller.lifetime)**1.7
                pen.line([a.xy,b.xy],fill=(*color,round(alpha*min(a.power,b.power)*fade)),width=max(1,round(width*(a.width+b.width)/2)))
        out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))
    return out

def draw_exhaust(background,t,power,nozzles):
    out=old_exhaust(background,t,power,nozzles);p=clamp(power)
    if p<=0:return out
    layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
    for idx,(a,v,w) in enumerate(nozzles):
        n=math.hypot(*v)
        if n<1e-6:continue
        dx,dy=v[0]/n,v[1]/n;nx,ny=-dy,dx
        length=n*(.12+2.45*p**.82);w=max(.65,w)
        for k in range(5):
            u=(k-2)/2.;osc=.5+.5*math.sin(t*91+k*2.13+idx)
            start=length*(.025+.08*osc);end=length*(.32+.43*osc);off=u*w*.54
            pen.line([(a[0]+dx*start+nx*off,a[1]+dy*start+ny*off),(a[0]+dx*end+nx*off*.19,a[1]+dy*end+ny*off*.19)],fill=(188,235,255,round(p*(48+85*osc))),width=max(1,round(w*.13)))
    out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(.28)));return out
