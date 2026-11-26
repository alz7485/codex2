"""Special flight-only trails; existing motion, anchors and launch/departure unchanged."""
import math
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter
from .special_trial119 import sample, SpecialVolley, END, phase, REENTRY, FORMATION, trail_gain
from .special_trial114 import ARRIVALS
from .composition_trial116 import camera_pose
from .special_fx_trial193 import draw_launch_trails, draw_launch_exhaust
from .thrust_trial86 import clamp
LIFETIME=.19
SAMPLES=17
MAX_LENGTH=88.
STOP_FADE=.065
FLIGHT_END=FORMATION+float(max(ARRIVALS))+STOP_FADE
@lru_cache(maxsize=512)
def anchors(t):
    return tuple((u.id,p.group,i,tuple(o),float(power),float(u.position[2])) for u in sample(t) if u.visible for i,(p,o,v,power) in enumerate(u.thrusters()) if power>.15)
def flight_tracks(t,project,width=240):
    if not REENTRY<=t<FLIGHT_END:return ()
    if width<=0:raise ValueError('invalid viewport width')
    c=camera_pose(t); tracks={}; cap=MAX_LENGTH*width/240
    for k in range(SAMPLES):
        h=t-(SAMPLES-1-k)*LIFETIME/(SAMPLES-1)
        if h<REENTRY:continue
        for i,group,j,o,p,z in anchors(h):
            stop=FORMATION+float(ARRIVALS[i]);gain=trail_gain(i,t,h)
            if h>=stop or gain<=0 or c.z-o[2]<=.35:continue
            xy=tuple(float(x) for x in project(o)[:2])
            if not all(math.isfinite(x) for x in xy):continue
            fade=clamp(1-(t-h)/LIFETIME)**1.35
            depth=max(.35,min(2.2,c.z/max(.35,c.z-z)))
            tracks.setdefault((i,group,j),[]).append((k,xy,p*gain*fade,depth))
    result=[]
    for key,pts in sorted(tracks.items()):
        runs=[]
        for point in pts:
            if not runs or point[0]!=runs[-1][-1][0]+1:runs.append([])
            runs[-1].append(point)
        left=cap
        for run in reversed(runs):
            kept=[run[-1]]
            for a in reversed(run[:-1]):
                b=kept[-1];d=math.dist(a[1],b[1])
                if d<1e-8:continue
                if d>left:
                    f=left/d;xy=tuple(b[1][j]+f*(a[1][j]-b[1][j]) for j in range(2))
                    kept.append((a[0],xy,0.,a[3]));left=0.;break
                kept.append(a);left-=d
                if left<=0:break
            if len(kept)>1:result.append((key,tuple(reversed(kept))))
            if left<=0:break
    return tuple(result)
def draw_flight_trails(background,t,project):
    out=background.convert('RGBA').copy();paths=flight_tracks(t,project,out.width)
    if not paths:return out
    scale=out.width/240
    for width,color,opacity,blur in ((3.5,(45,126,255),100,1.0),(1.1,(188,232,255),202,.28)):
        layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
        for _,path in paths:
            for a,b in zip(path,path[1:]):
                alpha=round(opacity*(a[2]+b[2])*.5)
                if alpha:pen.line([a[1],b[1]],fill=(*color,alpha),width=max(1,round(width*scale*(a[3]+b[3])*.5)))
        out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(.25,blur*scale))))
    return out
