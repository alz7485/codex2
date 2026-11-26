"""World-space beam projected with perspective and depth masking."""
import math
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from .combat_trial95 import PALETTES
from .fire_trial89 import FIRE,AFTER,smooth
from .combat_trial94 import MUZZLE,FORWARD_POINT

def beam(im,p,project,m,kind,depth):
    if p.stage not in ('fire','afterglow'):return im
    age=p.age; start=30*smooth((age-FIRE)/AFTER);end=30*smooth(age/.055);fade=1-smooth((age-FIRE)/AFTER)
    if end<=start or fade<=0:return im
    outer,inner,white=PALETTES[kind]; origin=(m@[*MUZZLE,1])[:3];f=(m@[*FORWARD_POINT,1])[:3]-origin;f/=np.linalg.norm(f)
    side=np.cross(f,[0,0,1]);side/=np.linalg.norm(side)
    layer=Image.new('RGBA',im.size);d=ImageDraw.Draw(layer);ts=np.linspace(start,end,42);coords=np.array([project(origin+f*t) for t in ts]);widths=np.array([np.linalg.norm(project(origin+f*t+side*.15)[:2]-c[:2]) for t,c in zip(ts,coords)])
    for k,(a,b) in enumerate(zip(coords,coords[1:])):
        taper=max(.08,min(1,(end-ts[k])/3)); w=widths[k]*taper*fade*(1+.11*math.sin(ts[k]*4-age*70)+.05*math.sin(ts[k]*7+age*95))
        for mult,color,alpha in [(2.6,outer,72),(1.45,inner,165),(.72,white,240),(.24,white,255)]:
            d.line([tuple(a[:2]),tuple(b[:2])],fill=(*color,round(alpha*fade)),width=max(1,round(w*mult*2)))
    # Traveling peripheral streaks remain in world space and shrink with distance.
    for k in range(13):
        t=start+(end-start)*((k*.173+age*4.4)%1); t2=min(end,t+.7+(k%4)*.18)
        off=(.18+.045*math.sin(t*6-age*70+k))*((-1)**k)*fade
        a=project(origin+f*t+side*off); b=project(origin+f*t2+side*off*.65)
        d.line([tuple(a[:2]),tuple(b[:2])],fill=(*inner,round(180*fade)),width=max(1,round(float(np.linalg.norm(project(origin+f*t+side*.045)[:2]-project(origin+f*t)[:2])))))
    flash=max(0.,1-age/.095)**2
    if flash>0:
        o=project(origin); r=max(2.,float(np.linalg.norm(project(origin+side*.32)[:2]-o[:2]))); x,y=o[:2]
        d.polygon([(x+math.cos(k*math.pi/4)*r*(1 if k%2==0 else .32),y+math.sin(k*math.pi/4)*r*(1 if k%2==0 else .32)) for k in range(8)],fill=(*inner,round(240*flash)))
        rr=r*.32;d.ellipse((x-rr,y-rr,x+rr,y+rr),fill=(*white,round(255*flash)))
    arr=np.array(layer);yy,xx=np.ogrid[:arr.shape[0],:arr.shape[1]];a,b=coords[0],coords[-1];delta=b[:2]-a[:2];q=np.clip(((xx-a[0])*delta[0]+(yy-a[1])*delta[1])/max(1e-9,np.dot(delta,delta)),0,1);z=a[2]+q*(b[2]-a[2]);arr[:,:,3]=np.where(z<=depth+.000025,arr[:,:,3],0);layer=Image.fromarray(arr);out=im.convert('RGBA');out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1.4)));out.alpha_composite(layer);return out
