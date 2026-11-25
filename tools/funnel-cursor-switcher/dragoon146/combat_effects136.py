"""Stylized green-white beam and muzzle charge; screen overlay, not a weapon simulation."""
import math
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from flight_trial135 import screen
from combat_trial136 import BEAM_ORIGIN,BEAM_AXIS,SHOT_TIME

def draw_combat(base,state):
    f=state.flight
    if not f.visible or (not state.charging and state.shot is None):return base.copy()
    glow=Image.new('RGB',base.size); core=Image.new('RGB',base.size)
    g=ImageDraw.Draw(glow); c=ImageDraw.Draw(core)
    factor=f.scale*6.6/82
    def line(draw,p,q,width,color):
        draw.line([tuple(p),tuple(q)],fill=color,width=max(1,round(width)))
    def dot(draw,p,r,col):
        x,y=p;draw.ellipse((x-r,y-r,x+r,y+r),fill=col)
    if state.charging:
        p=screen(f.world(BEAM_ORIGIN)); d=screen(f.matrix@BEAM_AXIS)
        n=np.linalg.norm(d); normal=np.array([-d[1],d[0]])/max(n,1e-9)
        v=.22+.78*state.charge; phase=f.t*24
        for k in range(5):
            a=phase+k*2*math.pi/5
            q=p+d*(3+7*v)*factor*math.cos(a)+normal*(2+5*v)*factor*math.sin(a)
            line(g,q,p,2.3*factor,(12,round(135*v),round(70*v)))
            dot(c,q,max(.6,factor*.9),(110,round(180+75*v),150))
        dot(g,p,(2+4*v)*factor,(20,round(220*v),90))
        dot(c,p,(.8+1.5*v)*factor,(165,255,190))
    if state.shot is not None:
        s=state.shot; age=max(0,f.t-s.t); q=s.charge; k=s.scale*6.6/82
        p=screen(s.origin); d=screen(s.direction)
        length=(110+155*q)*k; travel=1800*k
        head=min(length,travel*(age+.012)); tail=max(0,travel*(age-.075))
        if head>tail:
            a=p+d*tail;b=p+d*head
            intensity=max(0,1-age/SHOT_TIME)**.45
            for width,col in [(15,(10,110,45)),(9,(25,210,75))]:line(g,a,b,width*k*(.6+.7*q),tuple(round(x*intensity) for x in col))
            line(c,a,b,(3+4*q)*k,(100,255,160));line(c,a,b,(1.2+1.8*q)*k,(230,255,238))
        if age<.075:
            v=1-age/.075;dot(g,p,(5+7*q)*k*v,(35,255,110));dot(c,p,(2+3*q)*k*v,(235,255,240))
    a=np.asarray(base.convert('RGB'),dtype=np.uint16)+np.asarray(glow.filter(ImageFilter.GaussianBlur(max(.8,3*factor))),dtype=np.uint16)+np.asarray(core,dtype=np.uint16)
    return Image.fromarray(np.minimum(a,255).astype(np.uint8))
