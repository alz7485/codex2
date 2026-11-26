"""Short independent trails for HWS raids."""
import math
from functools import lru_cache
from PIL import Image,ImageDraw,ImageFilter
from .special_trial200 import sample,REENTRY,HWS_END
@lru_cache(maxsize=512)
def anchors(t,aspect):
    return tuple((u.id,j,tuple(o),p) for u in sample(t,'HiNu_HWS',aspect) for j,(_,o,_,p) in enumerate(u.thrusters()) if p>.15)
def raid_tracks(t,project,width=240,aspect=1.):
    if not REENTRY<=t<HWS_END:return ()
    paths={}
    for k in range(11):
        h=t-.17*(10-k)/10
        if h<REENTRY:continue
        for i,j,o,p in anchors(h,aspect):
            xy=tuple(float(x) for x in project(o)[:2]);gain=p*(k/10)**1.6
            if all(math.isfinite(x) for x in xy):paths.setdefault((i,j),[]).append((k,xy,gain))
    result=[];cap=72*width/240
    for key,pts in paths.items():
        kept=[pts[-1]];remaining=cap
        for a in reversed(pts[:-1]):
            b=kept[-1]
            if a[0]!=b[0]-1:break
            d=math.dist(a[1],b[1])
            if d>remaining:
                f=remaining/d;kept.append((a[0],tuple(b[1][j]+f*(a[1][j]-b[1][j]) for j in range(2)),0.));break
            kept.append(a);remaining-=d
        if len(kept)>1:result.append((key,tuple(reversed(kept))))
    return tuple(result)
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
