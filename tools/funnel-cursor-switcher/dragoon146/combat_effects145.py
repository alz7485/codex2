"""Trial145 special-only volley FX; depth-scaled screen-space compositing."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from flight_trial135 import screen, clip
from combat_trial137 import BEAM_ORIGIN, BEAM_AXIS, SHOT_TIME

def draw_volley(base,state):
    f=state.flight
    if not f.visible or (not state.charging and state.shot is None):
        return base.copy()
    halo=Image.new('RGB',base.size); inner=Image.new('RGB',base.size); core=Image.new('RGB',base.size)
    g=ImageDraw.Draw(halo); m=ImageDraw.Draw(inner); c=ImageDraw.Draw(core)
    factor=f.scale*6.6/82
    depth_gain=min(1.,.68+.32*factor)
    def color(rgb,v):return tuple(round(x*clip(v*depth_gain)) for x in rgb)
    def dot(draw,p,r,col):
        if r<=0:return
        x,y=p;draw.ellipse((x-r,y-r,x+r,y+r),fill=col)
    def line(draw,p,q,width,col):
        draw.line([tuple(p),tuple(q)],fill=col,width=max(1,round(width)))
    def basis(direction):
        d=screen(direction); n=np.linalg.norm(d)
        return d, np.array([-d[1],d[0]])/max(n,1e-9)
    def lance(draw,p,d,n,tail,head,width,col):
        if head<=tail:return
        L=head-tail; a=p+d*tail; b=p+d*head
        # Taper both ends, no rectangular beam cap.
        points=[a,a+d*(.18*L)+n*width*.70,a+d*(.68*L)+n*width,b,a+d*(.68*L)-n*width,a+d*(.18*L)-n*width]
        draw.polygon([tuple(q) for q in points],fill=col)
    if state.charging:
        p=screen(f.world(BEAM_ORIGIN)); d,n=basis(f.matrix@BEAM_AXIS)
        q=state.charge; v=.08+.92*q**1.6
        # Staggered inbound motes shrink their orbit before reaching the tip.
        for j in range(13):
            u=(f.t*(1.9+.7*q)+j/13)%1.; a=j*2.399963+f.t*2.8
            radial=(1-u)**1.15*(6+18*q)*factor
            offset=d*(.40*math.cos(a)*radial)+n*(math.sin(a)*radial)
            pos=p+offset; end=p+offset*.64
            brightness=(.28+.72*math.sin(math.pi*u))*(.45+.55*v)
            line(g,pos,end,2.4*factor,color((12,180,62),brightness))
            line(m,pos,end,1.1*factor,color((65,240,115),brightness))
            dot(c,end,max(.40,(.45+.40*q)*factor),color((190,255,220),brightness))
        pulse=.78+.22*math.sin(f.t*31)
        # Accelerating short streaks just before full charge.
        for j in range(4):
            a=j*math.pi/2+f.t*5
            radial=(5+9*q)*factor
            offset=(d*.6*math.cos(a)+n*math.sin(a))*radial
            line(m,p+offset,p+offset*.40,1.1*factor,color((92,255,159),q**3*pulse))
        dot(g,p,(2+6.5*q)*factor,color((20,205,70),v*pulse))
        dot(m,p,(1+2.8*q)*factor,color((65,235,105),v*pulse))
        dot(c,p,(.6+1.15*q)*factor,color((220,255,235),.65+.35*v))
    if state.shot is not None:
        s=state.shot; age=max(0,f.t-s.t); q=s.charge; k=s.scale*6.6/82
        p=screen(s.origin); d,n=basis(s.direction)
        length=(150+225*q)*k; travel=2420*k
        head=min(length,travel*(age+.012)); tail=max(0,travel*(age-.087))
        intensity=clip(1-age/SHOT_TIME)**.55
        width=(2.0+3.7*q)*k
        if head>tail:
            lance(g,p,d,n,tail,head,width*3.0,color((7,155,53),intensity))
            lance(m,p,d,n,tail,head,width*1.45,color((37,235,94),intensity))
            lance(c,p,d,n,tail,head,width,color((123,255,173),intensity))
            lance(c,p,d,n,tail+.02*(head-tail),head,width*.35,color((241,255,245),.72+.28*intensity))
        # Short, dim residual ion line, anchored to the fired world point.
        if .065<age<.19:
            v=clip((age-.065)/.028)*clip((.19-age)/.09)*(.24+.30*q)
            end=min(length,travel*age)*.80
            lance(g,p,d,n,0,end,width*.80,color((8,130,47),v))
            lance(m,p,d,n,0,end,width*.25,color((42,190,85),v))
        if age<.10:
            v=clip(1-age/.10)**1.7
            radius=(4.5+8*q)*k*v
            dot(g,p,radius*1.8,color((25,235,85),v))
            dot(m,p,radius,color((87,255,151),v))
            dot(c,p,radius*.42,color((245,255,248),v))
            # Four short rays only on the early flash; deterministic and scaled.
            if age<.055:
                for j in (-1,1):
                    line(m,p+n*j*radius*.55,p+n*j*radius*2.6,1.2*k,color((90,245,154),v))
    arr=np.asarray(base.convert('RGB'),dtype=np.uint16).copy()
    arr+=np.asarray(halo.filter(ImageFilter.GaussianBlur(max(.8,3.4*factor))),dtype=np.uint16)
    arr+=np.asarray(inner.filter(ImageFilter.GaussianBlur(max(.45,1.15*factor))),dtype=np.uint16)
    arr+=np.asarray(core,dtype=np.uint16)
    return Image.fromarray(np.minimum(arr,255).astype(np.uint8))
