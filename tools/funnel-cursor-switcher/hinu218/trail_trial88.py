"""Bounded twin screen-space afterglow; one controller per viewport."""
from collections import deque
from dataclasses import dataclass
import math
from PIL import Image, ImageDraw, ImageFilter
@dataclass(frozen=True)
class Sample:
    t: float
    xy: tuple
    power: float
    width: float
class Trail:
    def __init__(self,lifetime=.46,max_length=76.,max_samples=96):
        if not (math.isfinite(lifetime) and lifetime>0 and math.isfinite(max_length) and max_length>0 and isinstance(max_samples,int) and max_samples>=2):raise ValueError('invalid limits')
        self.lifetime=lifetime;self.max_length=max_length;self.max_samples=max_samples;self.reset()
    def reset(self):
        self.last=None;self.tracks=[deque(maxlen=self.max_samples) for _ in range(2)]
    def update(self,t,xy,pose,nozzles,enabled=True,context=None,fixed=False):
        xy=tuple(xy);nozzles=list(nozzles)
        if len(xy)!=2 or len(nozzles)!=2 or not all(math.isfinite(v) for v in (t,*xy,pose.power,pose.speed)):raise ValueError('invalid trail input')
        values=[]
        for a,v,w in nozzles:
            if len(a)!=2 or len(v)!=2 or not all(math.isfinite(k) for k in (*a,*v,w)) or w<0:raise ValueError('invalid nozzle')
            values.append((tuple(a),tuple(v),w))
        old=self.last;key=(context,bool(fixed))
        if not enabled or old is None or t<old[0] or t-old[0]>.25 or math.dist(xy,old[1])>500 or key!=old[2] or (t==old[0] and xy!=old[1]):self.reset();old=None
        if not enabled:return self.tracks
        moving=old is not None and t>old[0] and math.dist(xy,old[1])/(t-old[0])>8 and pose.power>.025
        for track,(a,v,w) in zip(self.tracks,values):
            while track and t-track[0].t>=self.lifetime:track.popleft()
            if moving and math.hypot(*v)>1e-6:
                p=tuple(a[j]+v[j]*.20 for j in range(2))
                if not track or math.dist(track[-1].xy,p)>=.6 or t-track[-1].t>=.04:track.append(Sample(t,p,max(0.,min(1.,pose.power)),max(.7,min(4.,w))))
            length=0.;keep=1;rev=list(reversed(track))
            for a,b in zip(rev,rev[1:]):
                length+=math.dist(a.xy,b.xy)
                if length>self.max_length:break
                keep+=1
            while len(track)>keep:track.popleft()
        self.last=(t,xy,key)
        return self.tracks

def draw_trails(background,t,controller):
    out=background.convert('RGBA').copy()
    for track in controller.tracks:
        if len(track)<2:continue
        points=list(track);pad=14
        l=max(0,math.floor(min(s.xy[0] for s in points)-pad));r=min(out.width,math.ceil(max(s.xy[0] for s in points)+pad))
        top=max(0,math.floor(min(s.xy[1] for s in points)-pad));bot=min(out.height,math.ceil(max(s.xy[1] for s in points)+pad))
        if l>=r or top>=bot:continue
        local=out.crop((l,top,r,bot));size=local.size
        for scale,color,alpha,blur in ((3.8,(25,90,255),115,2.8),(2.0,(35,156,255),155,1.1),(.8,(158,235,255),210,.35)):
            layer=Image.new('RGBA',size);d=ImageDraw.Draw(layer)
            for a,b in zip(points,points[1:]):
                fade=max(0.,min(1.,1-(t-(a.t+b.t)/2)/controller.lifetime))**1.7
                strength=fade*(a.power+b.power)/2
                width=max(1,round(scale*(a.width+b.width)/2*(.3+.7*fade)))
                d.line([(s.xy[0]-l,s.xy[1]-top) for s in (a,b)],fill=(*color,round(alpha*strength)),width=width)
            local.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))
        out.paste(local,(l,top))
    return out
