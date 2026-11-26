"""Normal flight only: bounded independent trails and modest exhaust enhancement."""
import math
from PIL import Image,ImageDraw,ImageFilter
from .effects_trial120 import SideTrails as PreviousSide,draw_exhaust as previous_exhaust
from .effects_trial122 import draw_side_trails
from .trail_trial88 import Sample,Trail as RearTrail
from .escort_trail_trial98 import Trail as EscortRearTrail
from .thrust_trial86 import clamp
LIFETIME=.18
LENGTH=48.
SAMPLES=32
EXHAUST_LENGTH=1.12

def rear_trail(multiplier=None):
    kw=dict(lifetime=LIFETIME,max_length=LENGTH*(1 if multiplier is None else multiplier),max_samples=SAMPLES)
    return RearTrail(**kw) if multiplier is None else EscortRearTrail(**kw,size_multiplier=multiplier)

class SideTrails(PreviousSide):
    def __init__(self,multiplier=1.):
        self.multiplier=multiplier
        super().__init__(LIFETIME,LENGTH*multiplier)
    def update(self,t,xy,jets,enabled=True,context=None):
        super().update(t,xy,jets,enabled,context)
        if enabled:
            by_group={p.group:j for p,power,j in jets}
            for i,g in enumerate(('side_minus','side_plus')):
                tr=self.tracks[i]
                if tr and tr[-1] is not None and tr[-1].t==t and self.live[i] and g in by_group:
                    s=tr[-1];w=by_group[g][2];tr[-1]=Sample(s.t,s.xy,s.power,max(.6*self.multiplier,min(3.*self.multiplier,w)))
        return self

def draw_exhaust(background,t,power,nozzles):
    nozzles=[(a,tuple(EXHAUST_LENGTH*x for x in v),w) for a,v,w in nozzles]
    out=previous_exhaust(background,t,power,nozzles);p=clamp(power)
    if p<=0:return out
    for a,v,w in nozzles:
        n=math.hypot(*v)
        if n<1e-6:continue
        dx,dy=v[0]/n,v[1]/n;length=n*(.12+2.45*p**.82)*.33
        pad=max(3,math.ceil(w*2+3));b=(a[0]+dx*length,a[1]+dy*length)
        l=max(0,math.floor(min(a[0],b[0])-pad));r=min(out.width,math.ceil(max(a[0],b[0])+pad));top=max(0,math.floor(min(a[1],b[1])-pad));bot=min(out.height,math.ceil(max(a[1],b[1])+pad))
        if l>=r or top>=bot:continue
        layer=Image.new('RGBA',(r-l,bot-top));d=ImageDraw.Draw(layer)
        d.line([(a[0]-l,a[1]-top),(b[0]-l,b[1]-top)],fill=(226,250,255,round(118*p)),width=max(1,round(w*.30)))
        out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(.35)),(l,top))
    return out
