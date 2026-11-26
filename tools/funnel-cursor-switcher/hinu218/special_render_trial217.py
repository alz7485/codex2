"""Hi-Nu departure-only trail tuning; Trial215 control and other FX unchanged."""
from .special_render_trial215 import *
from . import special_render_trial215 as previous
from .fx_local217 import blur_over
from .special_trial215 import timing, FINALE_LEAVE, FINALE_START, FINALE_DURATION, PAIR_START
from .normal_fx_trial204 import core_exhaust

EXIT_LIFE=.19
EXIT_SAMPLES=14
EXIT_CAP=92.
BASE_LIFE=.16
BASE_SAMPLES=12
BASE_CAP=84.

def departing(i,t):
    ev=event(i,t)
    return ev is not None and ev[1] >= (FINALE_LEAVE if ev[0] else timing(i)[6])

def tracks(t,project,aspect=1.,scale=1.):
    """Independent per-pass and per-port trails, no connection across inactive samples."""
    if not REENTRY<=t<HI_END:return ()
    result=[]
    for exit_only,life,count,cap in ((False,BASE_LIFE,BASE_SAMPLES,BASE_CAP),(True,EXIT_LIFE,EXIT_SAMPLES,EXIT_CAP)):
        paths={}
        for k in range(count):
            h=t-life*(count-1-k)/(count-1)
            if h<REENTRY:continue
            for i,j,o,p in anchors(h,aspect):
                ev=event(i,h)
                if ev is None or departing(i,h)!=exit_only:continue
                xy=tuple(float(x) for x in project(o)[:2])
                if all(math.isfinite(x) for x in xy):
                    paths.setdefault((i,j,ev[0],exit_only),[]).append((k,xy,p*(k/(count-1))**1.5))
        for key,pts in paths.items():
            remaining=cap*scale; segments=[]
            for a,b in reversed(list(zip(pts,pts[1:]))):
                if b[0]!=a[0]+1:break
                n=math.dist(a[1],b[1]);end=a[1]
                if n>remaining:end=tuple(b[1][j]+remaining/n*(a[1][j]-b[1][j]) for j in range(2))
                segments.append((end,b[1],(a[2]+b[2])/2))
                remaining-=n
                if remaining<=0:break
            if segments:result.append((key,tuple(segments)))
    return tuple(result)

def has_departure_history(t):
    e=t-REENTRY
    if FINALE_START+FINALE_LEAVE <= e < FINALE_START+FINALE_DURATION+EXIT_LIFE:return True
    return any(PAIR_START[i//2]+timing(i)[6] <= e < PAIR_START[i//2]+timing(i)[-1]+EXIT_LIFE for i in range(6))

def draw_mobile_trails(im,t,project,aspect=1.):
    if not has_departure_history(t):
        return base_mobile_trails(im,t,project,aspect)
    out=im.convert('RGBA');scale=min(out.size)/240
    paths=tracks(t,project,aspect,scale)
    if not paths:return out
    # Retain the previous colors, widths and opacity; only the departure history changes.
    fade=min(1.,max(0.,(HI_END-t)/.05))
    for w,c,opacity,blur in ((3.,(65,125,255),85,.9),(1.,(195,231,255),170,.25)):
        layer=Image.new('RGBA',out.size);d=ImageDraw.Draw(layer)
        for _,segments in paths:
            for a,b,power in segments:
                alpha=round(opacity*power*fade)
                if alpha:d.line((a,b),fill=(*c,alpha),width=max(1,round(w*scale)))
        blur_over(out,layer,max(.25,blur*scale))
    return out

def exhaust(im,t,power,nozzles,*,kind,unit_id,port,owned=False):
    if kind!='HiNu' or not departing(unit_id,t):
        return previous.exhaust(im,t,power,nozzles,kind=kind,unit_id=unit_id,port=port,owned=owned)
    ev=event(unit_id,t);leave=FINALE_LEAVE if ev[0] else timing(unit_id)[6]
    gain=1+.10*smooth((ev[1]-leave)/.08)
    # Use the actual active nozzle (side or rear) without stale legacy phase gains.
    jets=[(a,tuple(gain*x for x in v),w) for a,v,w in nozzles]
    return core_exhaust(im,t,power,jets,owned=owned)


def base_mobile_trails(im,t,project,aspect=1.):
 out=im.convert('RGBA');scale=min(out.size)/240
 if not REENTRY<=t<HI_END:return out
 paths={};life=.16
 for k in range(12):
  h=t-life*(11-k)/11
  if h<REENTRY:continue
  for i,j,o,p in anchors(h,aspect):
   ev=event(i,h);xy=tuple(float(x) for x in project(o)[:2]);
   if ev is not None and all(math.isfinite(x) for x in xy):paths.setdefault((i,j,ev[0]),[]).append((k,xy,p*(k/11)**1.5))
 for w,c,opacity,blur in ((3.,(65,125,255),85,.9),(1.,(195,231,255),170,.25)):
  layer=Image.new('RGBA',out.size);d=ImageDraw.Draw(layer)
  for pts in paths.values():
   remaining=84*scale
   for a,b in reversed(list(zip(pts,pts[1:]))):
    if b[0]!=a[0]+1:break
    n=math.dist(a[1],b[1]);end=a[1]
    if n>remaining:end=tuple(b[1][j]+remaining/n*(a[1][j]-b[1][j]) for j in range(2))
    alpha=round(opacity*(a[2]+b[2])/2*min(1.,max(0.,(HI_END-t)/.05)))
    if alpha:d.line((end,b[1]),fill=(*c,alpha),width=max(1,round(w*scale)))
    remaining-=n
    if remaining<=0:break
  blur_over(out,layer,max(.25,blur*scale))
 return out

def hws_launch_trails(background,t,project):
    out=background.convert('RGBA');paths=hws_launch_tracks(t,project,out.width)
    if not paths:return out
    scale=out.width/240
    for width,color,opacity,blur in ((3.2,(45,129,255),90,1.0),(1.0,(193,239,255),176,.3)):
        layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
        for _,path in paths:
            for a,b in zip(path,path[1:]):
                alpha=round(opacity*(a[1]+b[1])*.5)
                if alpha:pen.line([a[0],b[0]],fill=(*color,alpha),width=max(1,round(width*scale)))
        blur_over(out,layer,max(.25,blur*scale))
    return out

def draw_launch_trails(background,t,project,kind='HiNu'):
    if kind!='HiNu':return hws_launch_trails(background,t,project)
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

def draw_raid_trails(im,t,project,aspect=1.):
    out=im.convert('RGBA');tracks=raid_tracks(t,project,out.width,aspect);scale=out.width/240
    for w,c,opacity,blur in ((3.,(65,125,255),85,.9),(1.,(195,231,255),170,.25)):
        if not tracks:break
        l=Image.new('RGBA',out.size);d=ImageDraw.Draw(l)
        for _,pts in tracks:
            for a,b in zip(pts,pts[1:]):
                alpha=round(opacity*(a[2]+b[2])/2)
                if alpha:d.line((a[1],b[1]),fill=(*c,alpha),width=max(1,round(w*scale)))
        blur_over(out,l,max(.25,blur*scale))
    return out

from .special_fx_trial193 import launch_tracks as hws_launch_tracks
from .special_render_trial207 import launch_tracks
