"""Trial204: pixel-preserving local FX compositing; original controllers unchanged."""
import math
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from .thrust_trial86 import smooth
from .special_fx_trial193 import HOLD,EXIT,JET_GAIN,launch_tracks
from .special_fx_trial194 import flight_tracks,FLIGHT_END
from .special_fx_trial201 import raid_tracks
from .special_fx_trial203 import departure_tracks,exit_gain
from .special_fx_trial202 import brake_gain,aperture_glow
from .special_fx_trial199 import aperture_glow as raid_aperture
from .normal_fx_trial204 import core_exhaust
from .charge_fx_trial204 import normal_charge,arc_charge
from .beam_trial111 import PALETTES,FIRE,AFTER,MUZZLE,FORWARD_POINT
from .fx_local204 import blur_over, over

def draw_launch_trails(background,t,project):
    out=background.convert('RGBA');paths=launch_tracks(t,project,out.width)
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

def draw_flight_trails(background,t,project):
    out=background.convert('RGBA');paths=flight_tracks(t,project,out.width)
    if not paths:return out
    scale=out.width/240
    for width,color,opacity,blur in ((3.5,(45,126,255),100,1.0),(1.1,(188,232,255),202,.28)):
        layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
        for _,path in paths:
            for a,b in zip(path,path[1:]):
                alpha=round(opacity*(a[2]+b[2])*.5)
                if alpha:pen.line([a[1],b[1]],fill=(*color,alpha),width=max(1,round(width*scale*(a[3]+b[3])*.5)))
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

def draw_departure_trails(im,t,project):
    out=im.convert('RGBA');paths=departure_tracks(t,project,out.width)
    if not paths:return out
    layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
    for _,pts in paths:
        for a,b in zip(pts,pts[1:]):
            power=min(a[2],b[2]);width=max(1,round(2.4*b[3]))
            pen.line((a[1],b[1]),fill=(55,146,255,round(86*power)),width=width)
            pen.line((a[1],b[1]),fill=(180,230,255,round(190*power)),width=max(1,width//3))
    over(out,layer);return out

def draw_launch_exhaust(background,t,power,nozzles,*,owned=False):
    gain=1+(JET_GAIN-1)*smooth((t-(HOLD-.065))/.13) if HOLD-.065<=t<EXIT else 1.
    return core_exhaust(background,t,power,[(a,tuple(gain*x for x in v),w) for a,v,w in nozzles],owned=owned)

def brake_exhaust(im,t,power,nozzles,*,kind,unit_id,port,owned=False):
    gain=brake_gain(t,unit_id,port,kind)
    if gain==1.:return draw_launch_exhaust(im,t,power,nozzles,owned=owned)
    return draw_launch_exhaust(im,t,power,[(a,tuple(gain*x for x in v),w) for a,v,w in nozzles],owned=owned)

def exhaust(im,t,power,nozzles,*,kind,unit_id,port,owned=False):
    g=exit_gain(t,unit_id,port,kind)
    return brake_exhaust(im,t,power,[(a,tuple(g*x for x in v),w) for a,v,w in nozzles] if g!=1 else nozzles,kind=kind,unit_id=unit_id,port=port,owned=owned)

def raid_charge(im,t,p,project,depth=None,scale=1.,kind='HiNu',*,raid=False):
    out=normal_charge(im,t,p,project,depth,scale,kind)
    if raid and kind=='HiNu_HWS':return raid_aperture(out,p,project,depth,scale)
    return out

def charge(im,t,p,project,depth=None,scale=1.,kind='HiNu',*,raid=False):
    out=raid_charge(im,t,p,project,depth,scale,kind,raid=raid)
    if kind=='HiNu':return aperture_glow(out,p,project,depth,scale,kind)
    return out

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
    if np.asarray(depth).shape!=(im.height,im.width):raise ValueError('depth size mismatch')
    box=layer.getbbox(alpha_only=False)
    out=im.convert('RGBA')
    if box is None:return out
    l,t,r,b=box;arr=np.array(layer.crop(box));yy,xx=np.ogrid[t:b,l:r]
    a,bp=coords[0],coords[-1];delta=bp[:2]-a[:2]
    q=np.clip(((xx-a[0])*delta[0]+(yy-a[1])*delta[1])/max(1e-9,np.dot(delta,delta)),0,1);z=a[2]+q*(bp[2]-a[2])
    arr[:,:,3]=np.where(z<=depth[t:b,l:r]+.000025,arr[:,:,3],0)
    layer.paste(Image.fromarray(arr),(l,t));blur_over(out,layer,1.4);over(out,layer);return out
