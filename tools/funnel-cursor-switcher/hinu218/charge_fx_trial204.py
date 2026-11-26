"""Trial204: pixel-preserving local FX compositing; original controllers unchanged."""
from .combat_trial93 import *
from dataclasses import replace
from .fx_local204 import blur_over, over

def arc_charge(im,t,p,project,depth=None,scale=1.,kind="HiNu"):
    q=p.charge if p.stage=="charge" else .26*max(0.,1-p.age/.10) if p.stage=="fire" else 0.
    if q<=0:return im
    outer,inner,white=PALETTES[kind];w,h=im.size
    halo=Image.new('RGBA',im.size);hd=ImageDraw.Draw(halo)
    core=Image.new('RGBA',im.size);cd=ImageDraw.Draw(core)
    def visible(pt):
        x,y,z=pt;ix,iy=round(x),round(y)
        return 0<=ix<w and 0<=iy<h and (depth is None or z<=float(depth[iy,ix])+.002)
    def segment(a,b,draw,clr,width):
        n=max(1,math.ceil(math.dist(a[:2],b[:2])/1.4))
        for j in range(n):
            u=tuple(x+(y-x)*j/n for x,y in zip(a,b));v=tuple(x+(y-x)*(j+1)/n for x,y in zip(a,b))
            if visible(tuple((x+y)*.5 for x,y in zip(u,v))):draw.line([u[:2],v[:2]],fill=clr,width=max(1,round(width*scale)))
    for pts,strength,role in arcs(t,q):
        if strength<=0:continue
        pp=[project(v) for v in pts]
        for u,v in zip(pp,pp[1:]):
            segment(u,v,hd,(*outer,round(210*strength)),6)
            segment(u,v,cd,(*inner,round(240*strength)),3)
            segment(u,v,cd,(*white,round(255*strength)),1.3 if role=='main' else 1.)
    out=im.convert('RGBA');blur_over(out,halo,max(.7,3.1*scale));blur_over(out,halo,max(.5,1.1*scale));over(out,core)
    return out

def normal_charge(im,t,p,project,depth=None,scale=1.,kind='HiNu'):
    # Additional independent discharge only toward full charge; no axis or ball.
    if p.stage=='charge':
        out=arc_charge(im,t,p,project,depth,scale,kind)
        surge=smooth((p.charge-.55)/.45)
        if surge>0:
            out=arc_charge(out,t*1.31+.347,replace(p,charge=.73*surge),project,depth,scale,kind)
        return out
    if p.stage=='fire' and p.age<.145:
        return arc_charge(im,t,replace(p,stage='charge',charge=.34*(1-smooth(p.age/.145))),project,depth,scale,kind)
    return im
