"""Compact violet-white aperture glow during HWS raid charge only."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from .combat_trial94 import MUZZLE, PALETTES
from .combat_trial95 import charge as old_charge

def aperture_glow(im, pose, project, depth=None, scale=1.):
    if pose.stage != 'charge' or pose.charge <= 0:return im
    if not math.isfinite(scale) or scale <= 0:raise ValueError('invalid scale')
    q=min(1.,max(0.,pose.charge))
    x,y,z=map(float,project(MUZZLE))
    if not all(map(math.isfinite,(x,y,z))):return im
    w,h=im.size
    r=max(1.,min(7.*scale,float(np.linalg.norm(np.asarray(project((MUZZLE[0]+.25,MUZZLE[1],MUZZLE[2])))[:2]-[x,y]))))
    pad=math.ceil(r*4+3)
    l,top,right,bot=max(0,math.floor(x)-pad),max(0,math.floor(y)-pad),min(w,math.ceil(x)+pad+1),min(h,math.ceil(y)+pad+1)
    if l>=right or top>=bot:return im
    if depth is not None:
        d=np.asarray(depth)
        if d.shape!=(h,w):raise ValueError('depth size mismatch')
        if 0<=round(x)<w and 0<=round(y)<h and z>float(d[round(y),round(x)])+.0008:return im
    x-=l;y-=top
    outer,inner,white=PALETTES['HiNu_HWS']
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
    out=old_charge(im,t,p,project,depth,scale,kind)
    if raid and kind=='HiNu_HWS':return aperture_glow(out,p,project,depth,scale)
    return out
