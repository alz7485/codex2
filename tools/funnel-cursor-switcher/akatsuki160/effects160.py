"""Time-coherent layered pale cyan-white exhaust, acceleration-sensitive trails.
Same anchors, same path-length/lifetime limits as Trial134; no new geometry.
"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from flight150 import screen,LIFE,MODEL_LENGTH

def draw_effects(base,state):
    if not state.visible or (not any(j.power>=.025 for j in state.jets) and not any(len(h)>1 for h in state.trails.values())):
        return base.copy()
    glow=Image.new('RGB',base.size); core=Image.new('RGB',base.size)
    g=ImageDraw.Draw(glow); c=ImageDraw.Draw(core)
    factor=state.scale*MODEL_LENGTH/82
    for name,samples in state.trails.items():
        for (t0,p0,v0),(t1,p1,v1) in zip(samples,samples[1:]):
            age=max(0.,min(1.,1-(state.t-t0)/LIFE))
            a=age**1.4*min(v0,v1); xy=[tuple(p0),tuple(p1)]
            # stronger thrust produces a brighter, wider new segment, not a longer lifetime
            gain=1 if name=='rear' else .72
            g.line(xy,fill=tuple(round(x*a*gain) for x in (52,180,246)),width=max(1,round((2+5*a)*factor)))
            c.line(xy,fill=tuple(round(x*a*gain) for x in (151,235,255)),width=max(1,round((.7+1.5*a)*factor)))
    for idx,j in enumerate(state.jets):
        if j.power<.025:continue
        p=screen(j.origin);d=screen(j.direction);norm=np.linalg.norm(d)
        if norm<.03:continue
        normal=np.array([-d[1],d[0]])/norm
        phase=state.t*57+idx*2.13
        flutter=1+.055*math.sin(phase)+.025*math.sin(phase*1.61)
        length=(5+43*j.power**.78)*(1 if idx==0 else .58)*factor*flutter
        width=max(.65*factor,j.width*(.85+.9*j.power));intensity=min(1,j.power*1.5)
        for k,col,mul in [(0,(17,98,215),2.6),(1,(39,169,255),1.55),(2,(122,230,255),.72),(3,(239,253,255),.27)]:
            q=p+d*length*(1-.16*k);ww=width*mul
            poly=[tuple(p-normal*ww*.42),tuple(p+d*length*.15-normal*ww),tuple(p+d*length*.48-normal*ww*.63),tuple(q),tuple(p+d*length*.48+normal*ww*.63),tuple(p+d*length*.15+normal*ww),tuple(p+normal*ww*.42)]
            (g if k<2 else c).polygon(poly,fill=tuple(round(x*intensity) for x in col))
        # Fine filaments remain within the plume; no detached particles or reversed jets.
        if j.power>.10:
            for strand in (-1,0,1):
                off=strand*width*.29; wave=math.sin(phase+strand*1.8)*width*.11
                line=[tuple(p+d*length*.035+normal*off),tuple(p+d*length*.25+normal*(off+wave)),tuple(p+d*length*(.53+.09*math.sin(phase*.8+strand))+normal*off*.22)]
                c.line(line,fill=tuple(round(x*intensity) for x in (182,244,255)),width=max(1,round(factor*.65)))
    # Saturating RGB addition is associative for nonnegative channels.
    return ImageChops.add(ImageChops.add(base.convert('RGB'), glow.filter(ImageFilter.GaussianBlur(max(.55,2.0*factor)))), core)
