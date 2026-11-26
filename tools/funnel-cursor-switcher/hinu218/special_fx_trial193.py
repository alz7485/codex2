"""Opening-only FX. Retain Trial119 motion and port anchors. Draw tracks before jets,
then apply existing depth mask. Project history using the current camera."""
import math
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter
from .special_trial119 import sample, SpecialVolley, END, phase, camera_pose
from .special_trial106 import HOLD, EXIT
from .effects_trial120 import draw_exhaust as previous_exhaust
from .thrust_trial86 import clamp, smooth
LIFETIME=.16
MAX_LENGTH=60.
JET_GAIN=1.22
SAMPLES=13
@lru_cache(maxsize=256)
def _anchors(t):
    return tuple((u.id,tuple(o),float(power)) for u in sample(t) if u.visible
                 for port,o,v,power in u.thrusters() if port.group=='folded_root_preview')
def launch_tracks(t,project,viewport_width=240):
    if not HOLD<t<EXIT:return ()
    cap=MAX_LENGTH*viewport_width/240
    recent={}
    for k in range(SAMPLES):
        h=t-(SAMPLES-1-k)*LIFETIME/(SAMPLES-1)
        if h<HOLD:continue
        for i,o,p in _anchors(h):
            xy=tuple(float(x) for x in project(o)[:2])
            if not all(math.isfinite(x) for x in xy):continue
            fade=clamp(1-(t-h)/LIFETIME)**1.4
            strength=smooth((h-HOLD)/.13)*p*fade
            recent.setdefault(i,[]).append((xy,strength))
    result=[]
    for i,track in sorted(recent.items()):
        if len(track)<2:continue
        kept=[track[-1]]; total=0.
        for a in reversed(track[:-1]):
            b=kept[-1];d=math.dist(a[0],b[0]);left=cap-total
            if d<1e-8:continue
            if d>left:
                f=left/d;xy=tuple(b[0][j]+f*(a[0][j]-b[0][j]) for j in range(2));kept.append((xy,0.));break
            kept.append(a);total+=d
            if total>=cap:break
        if len(kept)>1:result.append((i,tuple(reversed(kept))))
    return tuple(result)
def draw_launch_trails(background,t,project):
    out=background.convert('RGBA').copy();paths=launch_tracks(t,project,out.width)
    if not paths:return out
    scale=out.width/240
    for width,color,opacity,blur in ((3.2,(45,129,255),90,1.0),(1.0,(193,239,255),176,.3)):
        layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
        for _,path in paths:
            for a,b in zip(path,path[1:]):
                alpha=round(opacity*(a[1]+b[1])*.5)
                if alpha:pen.line([a[0],b[0]],fill=(*color,alpha),width=max(1,round(width*scale)))
        out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(.25,blur*scale))))
    return out
def draw_launch_exhaust(background,t,power,nozzles):
    gain=1+(JET_GAIN-1)*smooth((t-(HOLD-.065))/.13) if HOLD-.065<=t<EXIT else 1.
    return previous_exhaust(background,t,power,[(a,tuple(gain*x for x in v),w) for a,v,w in nozzles])
