"""Trial95 visual-only effects. Root origin, depth projection and controller from Trial94."""
import math
from dataclasses import replace
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from combat_trial94 import Combat,MUZZLE,FORWARD_POINT,PALETTES
from combat_trial93 import charge as prior_charge, arcs as prior_arcs
from fire_trial89 import smooth,FIRE,AFTER

def charge(im,t,p,project,depth=None,scale=1.,kind='HiNu'):
    # Additional independent discharge only toward full charge; no axis or ball.
    if p.stage=='charge':
        out=prior_charge(im,t,p,project,depth,scale,kind)
        surge=smooth((p.charge-.55)/.45)
        if surge>0:
            out=prior_charge(out,t*1.31+.347,replace(p,charge=.73*surge),project,depth,scale,kind)
        return out
    if p.stage=='fire' and p.age<.145:
        return prior_charge(im,t,replace(p,stage='charge',charge=.34*(1-smooth(p.age/.145))),project,depth,scale,kind)
    return im

def beam_layer(size,p,anchor,scale=1.,kind='HiNu',channel_pixels=0.):
    layer=Image.new('RGBA',size)
    if anchor is None or p.stage not in ('fire','afterglow'):return layer
    outer,inner,white=PALETTES[kind];o,v=anchor;age=max(0.,p.age);length=135*scale+max(0.,channel_pixels)
    end=length*smooth(age/.055);start=length*smooth((age-FIRE)/AFTER);fade=1-smooth((age-FIRE)/AFTER)
    if fade<=0:return layer
    def pt(x,y=0.):return(o[0]+v[0]*x-v[1]*y,o[1]+v[1]*x+v[0]*y)
    a=Image.new('RGBA',size);d=ImageDraw.Draw(a);span=end-start
    if span>0:
        nose=min(24*scale,span*.30);tail=min(12*scale,span*.25)
        def envelope(x):return max(0.,min(1.,(end-x)/max(nose,.01),(x-start)/max(tail,.01)+(.78 if start<.01 else 0.)))
        xs=np.linspace(start,end,max(12,min(100,int(span/2)+2)))
        for width,color,alpha,noise in [(11,outer,115,.19),(6.5,inner,205,.12),(3.2,white,240,.06),(1.0,white,255,0.)]:
            w=width*scale*max(.18,fade)
            def edge(x,sign):return sign*w*envelope(x)*(1+noise*math.sin(x/(4.2*scale)+age*74+sign*1.6)+noise*.6*math.sin(x/(2.5*scale)-age*91))
            d.polygon([pt(x,edge(x,1)) for x in xs]+[pt(x,edge(x,-1)) for x in xs[::-1]],fill=(*color,round(alpha*fade)))
        for k in range(13):
            x=start+span*((k*.171+age*4.7)%1);sign=(-1)**k;ext=min(end,x+scale*(7+k%4*2));off=sign*scale*max(.2,fade)
            points=[pt(u,off*(6+2*math.sin(u/(3.1*scale)-age*63+k))*envelope(u)) for u in np.linspace(x,ext,5)]
            d.line(points,fill=(*inner,round(180*fade)),width=max(1,round(scale)))
    # Transient flash at root on firing, not a persistent charge ball.
    flash=max(0.,1-age/.095)**2
    if flash>0:
        r=(6+14*smooth(age/.095))*scale
        d.polygon([pt(math.cos(k*math.pi/4)*r*(1 if k%2==0 else .32),math.sin(k*math.pi/4)*r*(.8 if k%2==0 else .25)) for k in range(8)],fill=(*inner,round(240*flash)))
        x,y=o;rr=3.5*scale*math.sqrt(flash);d.ellipse((x-rr,y-rr,x+rr,y+rr),fill=(*white,round(255*flash)))
    layer.alpha_composite(a.filter(ImageFilter.GaussianBlur(max(.5,3*scale))));layer.alpha_composite(a);return layer

def beam(im,p,anchor,scale=1.,kind='HiNu',*,depth=None,shot_depth=None,channel_pixels=0.):
    if anchor is None:return im
    if not math.isfinite(scale) or scale<=0:raise ValueError('invalid scale')
    layer=beam_layer(im.size,p,anchor,scale,kind,channel_pixels)
    if depth is not None and shot_depth is not None:
        a=np.array(layer);h,w=a.shape[:2];d=np.asarray(depth)
        if d.shape!=(h,w):raise ValueError('depth size mismatch')
        (ox,oy),(vx,vy)=anchor;z,dz=shot_depth;yy,xx=np.ogrid[:h,:w];dist=(xx-ox)*vx+(yy-oy)*vy
        a[:,:,3]=np.where(z+np.maximum(0,dist)*dz<=d+.0008,a[:,:,3],0);layer=Image.fromarray(a)
    out=im.convert('RGBA');out.alpha_composite(layer);return out
