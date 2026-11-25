"""Trial151 screen-space pink-white fictional cursor beam. Pure time-based FX."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from flight150 import screen, clip, MODEL_LENGTH
from combat151 import beam_origin, BEAM_AXIS, SHOT_TIME

def draw_combat(base,state):
    f=state.flight
    if not f.visible or (not state.charging and state.shot is None):
        return base.copy()
    halo=Image.new('RGB',base.size); inner=Image.new('RGB',base.size); core=Image.new('RGB',base.size)
    g=ImageDraw.Draw(halo); m=ImageDraw.Draw(inner); c=ImageDraw.Draw(core)
    factor=f.scale*MODEL_LENGTH/82
    def color(rgb,v):return tuple(round(x*clip(v)) for x in rgb)
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
        p=screen(f.world(beam_origin(f))); d,n=basis(f.matrix@BEAM_AXIS)
        q=state.charge; v=.14+.86*q
        # Staggered inbound motes shrink their orbit before reaching the tip.
        for j in range(11):
            u=(f.t*(1.9+.7*q)+j/11)%1.; a=j*2.399963+f.t*2.8
            radial=(1-u)**1.15*(5+13*q)*factor
            offset=d*(.40*math.cos(a)*radial)+n*(math.sin(a)*radial)
            pos=p+offset; end=p+offset*.64
            brightness=(.28+.72*math.sin(math.pi*u))*(.45+.55*v)
            line(g,pos,end,2.4*factor,color((195,38,121),brightness))
            line(m,pos,end,1.1*factor,color((255,89,172),brightness))
            dot(c,end,max(.40,(.45+.40*q)*factor),color((255,209,235),brightness))
        pulse=.85+.15*math.sin(f.t*31)
        dot(g,p,(2+5*q)*factor,color((221,45,142),v*pulse))
        dot(m,p,(1+2.2*q)*factor,color((255,110,183),v*pulse))
        dot(c,p,(.6+1.15*q)*factor,color((255,230,247),.65+.35*v))
    if state.shot is not None:
        s=state.shot; age=max(0,f.t-s.t); q=s.charge; k=s.scale*MODEL_LENGTH/82
        p=screen(s.origin); d,n=basis(s.direction)
        length=(100+170*q)*k; travel=1950*k
        head=min(length,travel*(age+.012)); tail=max(0,travel*(age-.075))
        intensity=clip(1-age/SHOT_TIME)**.55
        width=(1.65+2.5*q)*k
        if head>tail:
            lance(g,p,d,n,tail,head,width*3.4,color((193,23,106),intensity))
            lance(m,p,d,n,tail,head,width*1.65,color((255,62,147),intensity))
            lance(c,p,d,n,tail,head,width,color((255,153,207),intensity))
            lance(c,p,d,n,tail+.02*(head-tail),head,width*.42,color((255,242,250),.72+.28*intensity))
        # Short, dim residual ion line, anchored to the fired world point.
        if .065<age<.19:
            v=clip((age-.065)/.028)*clip((.19-age)/.09)*(.24+.30*q)
            end=min(length,travel*age)*.80
            lance(g,p,d,n,0,end,width*.80,color((156,25,90),v))
            lance(m,p,d,n,0,end,width*.25,color((235,68,145),v))
        if age<.10:
            v=clip(1-age/.10)**1.7
            radius=(3.8+6*q)*k*v
            dot(g,p,radius*1.8,color((247,54,153),v))
            dot(m,p,radius,color((255,139,207),v))
            dot(c,p,radius*.42,color((255,244,251),v))
            # Four short rays only on the early flash; deterministic and scaled.
            if age<.055:
                for j in (-1,1):
                    line(m,p+n*j*radius*.55,p+n*j*radius*2.3,1.2*k,color((255,126,201),v))
    b=ImageChops.add(base.convert('RGB'),halo.filter(ImageFilter.GaussianBlur(max(.8,3.4*factor))))
    b=ImageChops.add(b,inner.filter(ImageFilter.GaussianBlur(max(.45,1.15*factor))))
    return ImageChops.add(b,core)
