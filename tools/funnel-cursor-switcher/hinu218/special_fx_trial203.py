"""HiNu breakaway only: short, capped nozzle history and modest rear jet gain."""
import math
from functools import lru_cache
from PIL import Image, ImageDraw
from .special_trial119 import sample, BASE_END, END, trail_gain
from .special_trial117 import DELAY, TURN, TRAVEL
from .composition_trial116 import camera_pose
from .special_fx_trial202 import exhaust as previous_exhaust, charge
from .thrust_trial86 import smooth
HISTORY=.165
SAMPLES=13
CAP=96.
@lru_cache(maxsize=1024)
def anchors(t):
    return tuple((u.id,j,tuple(o),p,float(u.position[2])) for u in sample(t) if u.visible for j,(port,o,v,p) in enumerate(u.thrusters()) if p>.15)
def departure_tracks(t,project,width):
    if not BASE_END<=t<END:return ()
    if width<=0:raise ValueError('invalid width')
    cp=camera_pose(t); paths={}; fade=smooth((END-t)/.05)
    for k in range(SAMPLES):
        h=t-HISTORY*(SAMPLES-1-k)/(SAMPLES-1)
        if h<BASE_END:continue
        for i,j,o,p,z in anchors(h):
            if not trail_gain(i,t,h) or cp.z-o[2]<=.35:continue
            xy=tuple(float(x) for x in project(o)[:2]);d=max(.35,min(2.2,cp.z/max(.35,cp.z-z)))
            if all(math.isfinite(x) for x in xy):paths.setdefault((i,j),[]).append((k,xy,p*(k/(SAMPLES-1))*fade,d))
    result=[]
    for key,pts in paths.items():
        kept=[pts[-1]];left=CAP*width/240
        for a in reversed(pts[:-1]):
            b=kept[-1]
            if a[0]!=b[0]-1:break
            dist=math.dist(a[1],b[1])
            if dist<1e-9:continue
            if dist>left:
                f=left/dist;kept.append((a[0],tuple(b[1][j]+f*(a[1][j]-b[1][j]) for j in range(2)),0.,a[3]));break
            kept.append(a);left-=dist
            if left<=0:break
        if len(kept)>1:result.append((key,tuple(reversed(kept))))
    return tuple(result)
def draw_departure_trails(im,t,project):
    out=im.convert('RGBA').copy();paths=departure_tracks(t,project,out.width)
    if not paths:return out
    layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
    for _,pts in paths:
        for a,b in zip(pts,pts[1:]):
            power=min(a[2],b[2]);width=max(1,round(2.4*b[3]))
            pen.line((a[1],b[1]),fill=(55,146,255,round(86*power)),width=width)
            pen.line((a[1],b[1]),fill=(180,230,255,round(190*power)),width=max(1,width//3))
    out.alpha_composite(layer);return out
def exit_gain(t,unit_id,port,kind):
    if kind!='HiNu' or unit_id not in DELAY or port.group!='rear':return 1.
    e=t-BASE_END-DELAY[unit_id]-TURN
    if not 0<e<TRAVEL:return 1.
    return 1+.12*smooth(e/.06)
def exhaust(im,t,power,nozzles,*,kind,unit_id,port):
    g=exit_gain(t,unit_id,port,kind)
    return previous_exhaust(im,t,power,[(a,tuple(g*x for x in v),w) for a,v,w in nozzles] if g!=1 else nozzles,kind=kind,unit_id=unit_id,port=port)
