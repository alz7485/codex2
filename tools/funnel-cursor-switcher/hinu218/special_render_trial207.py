"""Staggered launch trails and per-pair exhaust phase. Other FX unchanged."""
from .special_render_trial205 import *
from . import special_render_trial205 as previous
from .special_trial207 import sample, launch_age, LAUNCH_END, HOLD, REENTRY, old_age
from .special_fx_trial193 import LIFETIME,MAX_LENGTH,SAMPLES
from .thrust_trial86 import clamp,smooth
from functools import lru_cache

@lru_cache(maxsize=512)
def opening_anchors(t):
    return tuple((u.id,tuple(o),p) for u in sample(t) for port,o,v,p in u.thrusters() if port.group=='folded_root_preview')

def launch_tracks(t,project,viewport_width=240):
    if not HOLD<t<LAUNCH_END:return ()
    recent={}
    for k in range(SAMPLES):
        h=t-(SAMPLES-1-k)*LIFETIME/(SAMPLES-1)
        if h<HOLD:continue
        for i,o,p in opening_anchors(h):
            local=launch_age(i,h)
            if local<HOLD:continue
            xy=tuple(float(x) for x in project(o)[:2])
            if not all(math.isfinite(x) for x in xy):continue
            strength=smooth((local-HOLD)/.13)*p*clamp(1-(t-h)/LIFETIME)**1.4
            recent.setdefault(i,[]).append((xy,strength))
    result=[];cap=MAX_LENGTH*viewport_width/240
    for i,track in sorted(recent.items()):
        if len(track)<2:continue
        kept=[track[-1]];total=0.
        for a in reversed(track[:-1]):
            b=kept[-1];d=math.dist(a[0],b[0]);left=cap-total
            if d<1e-8:continue
            if d>left:
                f=left/d;kept.append((tuple(b[0][j]+f*(a[0][j]-b[0][j]) for j in range(2)),0.));break
            kept.append(a);total+=d
            if total>=cap:break
        if len(kept)>1:result.append((i,tuple(reversed(kept))))
    return tuple(result)

def draw_launch_trails(background,t,project,kind='HiNu'):
    if kind!='HiNu':return previous.draw_launch_trails(background,t,project)
    out=background.convert('RGBA');scale=out.width/240;paths=launch_tracks(t,project,out.width)
    if not paths:return out
    for width,color,opacity,blur in ((3.2,(45,129,255),90,1.0),(1.,(193,239,255),176,.3)):
        layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
        for _,path in paths:
            for a,b in zip(path,path[1:]):
                alpha=round(opacity*(a[1]+b[1])*.5)
                if alpha:pen.line((a[0],b[0]),fill=(*color,alpha),width=max(1,round(width*scale)))
        blur_over(out,layer,max(.25,blur*scale))
    return out

def exhaust(im,t,power,nozzles,*,kind,unit_id,port,owned=False):
    if kind=='HiNu' and t<REENTRY:
        return previous.exhaust(im,launch_age(unit_id,t),power,nozzles,kind=kind,unit_id=unit_id,port=port,owned=owned)
    return previous.exhaust(im,old_age(t) if kind=='HiNu' else t,power,nozzles,kind=kind,unit_id=unit_id,port=port,owned=owned)


def draw_mobile_trails(im,t,project,aspect=1.):
    if t<REENTRY:return im.convert('RGBA')
    return previous.draw_mobile_trails(im,old_age(t),project,aspect)
