"""Trial205 HiNu mobile trails; HWS and opening use the pixel-preserving Trial204 renderer."""
from .special_render_trial204 import *
from .special_trial205 import sample, event, REENTRY, HI_END
from functools import lru_cache
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

def mobile_beam(im,p,project,m,depth):
    """A finite blue-white pulse launched in world coordinates; never attached to a moving unit."""
    if p.stage not in ('fire','afterglow') or not 0<p.age<FIRE+AFTER:return im
    age=p.age; head=155*age; tail=max(0.,head-18.); fade=1-smooth((age-.22)/.18)
    origin=(m@[*MUZZLE,1])[:3];f=(m@[*FORWARD_POINT,1])[:3]-origin;f/=np.linalg.norm(f)
    side=np.cross(f,[0.,0.,1.]);side/=np.linalg.norm(side)
    outer,inner,white=PALETTES['HiNu'];layer=Image.new('RGBA',im.size);d=ImageDraw.Draw(layer)
    a,b=[np.asarray(project(origin+f*v),float) for v in (tail,head)]
    if not np.isfinite(np.r_[a,b]).all():return im
    for width,color,alpha in ((.48,outer,125),(.25,inner,210),(.10,white,255)):
        poly=[]
        for q,w in ((0,0),(.12,-.7),(.5,-1),(.88,-.6),(1,0),(.88,.6),(.5,1),(.12,.7)):
            pt=origin+f*(tail+(head-tail)*q)+side*(width*w*fade);poly.append(tuple(project(pt)[:2]))
        d.polygon(poly,fill=(*color,round(alpha*fade)))
    box=layer.getbbox(alpha_only=False);out=im.convert('RGBA')
    if box is None:return out
    l,t,r,bottom=box;arr=np.array(layer.crop(box));yy,xx=np.ogrid[t:bottom,l:r];delta=b[:2]-a[:2]
    q=np.clip(((xx-a[0])*delta[0]+(yy-a[1])*delta[1])/max(1e-9,np.dot(delta,delta)),0,1)
    arr[:,:,3]=np.where(a[2]+q*(b[2]-a[2])<=depth[t:bottom,l:r]+.000025,arr[:,:,3],0)
    layer.paste(Image.fromarray(arr),(l,t));blur_over(out,layer,1.3);over(out,layer);return out
