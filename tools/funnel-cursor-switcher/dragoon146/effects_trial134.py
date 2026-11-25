"""Small blue-white layered exhaust and independent per-port movement trails."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from flight_trial134 import screen,LIFE

def draw_effects(base,state):
    if not state.visible:return base.copy()
    glow=Image.new('RGB',base.size); core=Image.new('RGB',base.size)
    g=ImageDraw.Draw(glow); c=ImageDraw.Draw(core)
    factor=state.scale*6.6/82
    for samples in state.trails.values():
        for (t0,p0,v0),(t1,p1,v1) in zip(samples,samples[1:]):
            a=max(0.,1-(state.t-t0)/LIFE)*min(v0,v1)
            xy=[tuple(p0),tuple(p1)]
            g.line(xy,fill=(int(38*a),int(132*a),int(255*a)),width=max(1,round(5*factor)))
            c.line(xy,fill=(int(90*a),int(185*a),int(255*a)),width=max(1,round(1.3*factor)))
    for idx,j in enumerate(state.jets):
        if j.power<.025:continue
        p=screen(j.origin);d=screen(j.direction);norm=np.linalg.norm(d)
        if norm<.03:continue
        normal=np.array([-d[1],d[0]])/norm
        length=(7+34*j.power)*(1 if idx==0 else .60)*factor
        length*=1+.08*math.sin(state.t*68+idx*2)
        width=max(.75,j.width*(1.1+.7*j.power));end=p+d*length
        for k,col,mul in [(0,(16,75,200),2.3),(1,(32,132,255),1.3),(2,(114,214,255),.65),(3,(230,249,255),.24)]:
            q=p+d*length*(1-.14*k); ww=width*mul
            poly=[tuple(p-normal*ww*.45),tuple(p+d*length*.19-normal*ww),tuple(q),tuple(p+d*length*.19+normal*ww),tuple(p+normal*ww*.45)]
            intensity=min(1,j.power*1.65)
            (g if k<2 else c).polygon(poly,fill=tuple(int(x*intensity) for x in col))
    a=np.asarray(base.convert('RGB'),dtype=np.uint16)+np.asarray(glow.filter(ImageFilter.GaussianBlur(max(.6,2.2*factor))),dtype=np.uint16)+np.asarray(core,dtype=np.uint16)
    return Image.fromarray(np.minimum(a,255).astype(np.uint8))
