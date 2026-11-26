"""HiNu-only special brake and charge refinement; HWS delegates unchanged."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from .combat_trial94 import MUZZLE, PALETTES
from .special_fx_trial199 import charge as previous_charge
from .special_trial114 import FORMATION, ARRIVALS
from .special_trial115 import pulse
from .special_fx_trial193 import draw_launch_exhaust
from .thrust_trial86 import smooth

def aperture_glow(im, pose, project, depth=None, scale=1., kind="HiNu_HWS"):
    if pose.stage != 'charge' or pose.charge <= 0:return im
    if not math.isfinite(scale) or scale <= 0:raise ValueError('invalid scale')
    q=min(1.,max(0.,pose.charge))
    if kind=="HiNu":
        q=smooth((q-.60)/.40)
        if q<=0:return im
    x,y,z=map(float,project(MUZZLE))
    if not all(map(math.isfinite,(x,y,z))):return im
    w,h=im.size
    r=max(1.,min((4.5 if kind=="HiNu" else 7.)*scale,float(np.linalg.norm(np.asarray(project((MUZZLE[0]+.25,MUZZLE[1],MUZZLE[2])))[:2]-[x,y]))))
    pad=math.ceil(r*4+3)
    l,top,right,bot=max(0,math.floor(x)-pad),max(0,math.floor(y)-pad),min(w,math.ceil(x)+pad+1),min(h,math.ceil(y)+pad+1)
    if l>=right or top>=bot:return im
    if depth is not None:
        d=np.asarray(depth)
        if d.shape!=(h,w):raise ValueError('depth size mismatch')
        if 0<=round(x)<w and 0<=round(y)<h and z>float(d[round(y),round(x)])+.0008:return im
    x-=l;y-=top
    outer,inner,white=PALETTES[kind]
    layer=Image.new('RGBA',(right-l,bot-top));draw=ImageDraw.Draw(layer)
    def dot(radius,color,alpha):
        draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=(*color,round(alpha*q)))
    dot(r*(1.55-.48*q),outer,125)
    halo=layer.filter(ImageFilter.GaussianBlur(max(.65,r*.72)))
    layer=Image.new('RGBA',halo.size);draw=ImageDraw.Draw(layer)
    dot(r*(.65+.18*q),inner,195)
    dot(r*.38,white,245)
    halo.alpha_composite(layer)
    if depth is not None:
        a=np.array(halo);a[:,:,3]=np.where(z<=d[top:bot,l:right]+.0008,a[:,:,3],0);halo=Image.fromarray(a)
    out=im.convert('RGBA');out.alpha_composite(halo,(l,top));return out

def charge(im,t,p,project,depth=None,scale=1.,kind='HiNu',*,raid=False):
    out=previous_charge(im,t,p,project,depth,scale,kind,raid=raid)
    if kind=='HiNu':return aperture_glow(out,p,project,depth,scale,kind)
    return out

def brake_gain(t,unit_id,port,kind):
    if kind!='HiNu' or not 0<=unit_id<len(ARRIVALS) or port.group not in ('side_minus','side_plus'):return 1.
    return 1.+.22*pulse(t-FORMATION,ARRIVALS[unit_id])

def exhaust(im,t,power,nozzles,*,kind,unit_id,port):
    gain=brake_gain(t,unit_id,port,kind)
    if gain==1.:return draw_launch_exhaust(im,t,power,nozzles)
    return draw_launch_exhaust(im,t,power,[(a,tuple(gain*x for x in v),w) for a,v,w in nozzles])
