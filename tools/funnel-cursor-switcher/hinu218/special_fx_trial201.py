"""HWS exit-only trail refinement. Controller and attack timings remain Trial200."""
import math
from PIL import Image, ImageDraw, ImageFilter
from .special_trial200 import REENTRY,HWS_END,WAVES,LEAVE,DURATION
from .special_fx_trial200 import anchors,raid_tracks as previous_tracks

EXIT_HISTORY=.204
EXIT_CAP=82.

def departing(i,t):
    e=t-REENTRY-WAVES[i][0]
    return LEAVE<=e<DURATION+EXIT_HISTORY

def raid_tracks(t,project,width=240,aspect=1.):
    base=previous_tracks(t,project,width,aspect)
    if not REENTRY<=t<HWS_END:return base
    ids={i for i in range(len(WAVES)) if departing(i,t)}
    if not ids:return base
    paths={}
    fade=min(1.,max(0.,(HWS_END-t)/.045))
    for k in range(13):
        h=t-EXIT_HISTORY*(12-k)/12
        if h<REENTRY:continue
        for i,j,o,p in anchors(h,aspect):
            if i not in ids or h-REENTRY-WAVES[i][0]<LEAVE:continue
            xy=tuple(float(x) for x in project(o)[:2]);gain=p*(k/12)**1.6*fade
            if all(math.isfinite(x) for x in xy):paths.setdefault((i,j),[]).append((k,xy,gain))
    extra={}
    for key,pts in paths.items():
        kept=[pts[-1]];remaining=EXIT_CAP*width/240
        for a in reversed(pts[:-1]):
            b=kept[-1]
            if a[0]!=b[0]-1:break
            d=math.dist(a[1],b[1])
            if d>remaining:
                f=remaining/d;kept.append((a[0],tuple(b[1][j]+f*(a[1][j]-b[1][j]) for j in range(2)),0.));break
            kept.append(a);remaining-=d
        if len(kept)>1:extra[key]=tuple(reversed(kept))
    # Preserve prior path order and all unrelated entry/charge trails exactly.
    out=[]
    for key,path in base:
        if key[0] not in ids:out.append((key,path))
        elif key in extra:out.append((key,extra.pop(key)))
    out.extend(extra.items())
    return tuple(out)

def draw_raid_trails(im,t,project,aspect=1.):
    out=im.convert('RGBA').copy();tracks=raid_tracks(t,project,out.width,aspect);scale=out.width/240
    for w,c,opacity,blur in ((3.,(65,125,255),85,.9),(1.,(195,231,255),170,.25)):
        if not tracks:break
        l=Image.new('RGBA',out.size);d=ImageDraw.Draw(l)
        for _,pts in tracks:
            for a,b in zip(pts,pts[1:]):
                alpha=round(opacity*(a[2]+b[2])/2)
                if alpha:d.line((a[1],b[1]),fill=(*c,alpha),width=max(1,round(w*scale)))
        out.alpha_composite(l.filter(ImageFilter.GaussianBlur(max(.25,blur*scale))))
    return out
