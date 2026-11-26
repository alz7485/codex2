from .special_render_trial207 import *
from .special_trial215 import sample,event,REENTRY,HI_END
@lru_cache(maxsize=512)
def anchors(t,aspect):
 return tuple((u.id,j,tuple(o),p) for u in sample(t,'HiNu',aspect) for j,(_,o,v,p) in enumerate(u.thrusters()) if p>.12)
def draw_mobile_trails(im,t,project,aspect=1.):
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

