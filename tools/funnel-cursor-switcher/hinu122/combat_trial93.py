"""Random inter-plate discharge, no charge axis or ball."""
import math, random
from PIL import Image, ImageDraw, ImageFilter
from combat_trial91 import Combat, RAILS as INNER_RAILS, beam as old_beam
# Additional inner-spar surface points from cross sections of both GLBs.
RAILS=INNER_RAILS+tuple((sign*x,y,z) for sign in (-1,1) for y in (-.18,.18) for x,z in ((.754,.25),(.736,1.25),(.718,2.30),(.835,-3.65)))
PALETTES={'HiNu':((33,119,255),(93,204,255),(231,251,255)), 'HiNu_HWS':((119,48,255),(190,124,255),(249,237,255))}
SIDES={s:tuple(p for p in RAILS if p[0]*s>0) for s in (-1,1)}
def jagged(a,b,rng,n=12):
    pts=[a]
    for j in range(1,n):
        u=j/n;e=math.sin(math.pi*u)
        pts.append((a[0]+(b[0]-a[0])*u+rng.uniform(-.105,.105)*e,a[1]+(b[1]-a[1])*u+rng.uniform(-.15,.15)*e,a[2]+(b[2]-a[2])*u+rng.uniform(-.30,.30)*e))
    return pts+[b]
def arcs(t,q):
    q=max(0.,min(1.,q))
    if q==0:return []
    out=[]
    for k in range(9):
        period=.085+.019*(k%4);phase=t/period+k*.381;tick=math.floor(phase);u=phase-tick
        rng=random.Random(930001+k*1000003+tick*7919)
        if k>=2+int(7*q) or rng.random()>.78+.17*q:continue
        a=rng.choice(SIDES[-1]);b=rng.choice([p for p in SIDES[1] if abs(p[2]-a[2])<2.2])
        if rng.random()<.5:a,b=b,a
        pts=jagged(a,b,rng,rng.randint(8,15));strength=q*min(1.,u*6,(1-u)*6)*rng.uniform(.72,1.)
        out.append((pts,strength,'main'))
        if rng.random()<.68:
            root=pts[rng.randrange(2,len(pts)-2)];side=-1 if rng.random()<.5 else 1
            nearby=[p for p in SIDES[side] if abs(p[2]-root[2])<1.7]
            if nearby:out.append((jagged(root,rng.choice(nearby),rng,7),strength*.67,'branch'))
    return out

def charge(im,t,p,project,depth=None,scale=1.,kind="HiNu"):
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
    out=im.convert('RGBA');out.alpha_composite(halo.filter(ImageFilter.GaussianBlur(max(.7,3.1*scale))));out.alpha_composite(halo.filter(ImageFilter.GaussianBlur(max(.5,1.1*scale))));out.alpha_composite(core)
    return out

from fire_trial89 import smooth, FIRE, AFTER
def draw_beam(im,p,anchor,scale=1.,kind="HiNu"):
 outer,inner,white=PALETTES[kind]
 if anchor is None:return im
 o,v=anchor;age=p.age;length=135*scale;end=length*smooth(age/.055);start=length*smooth((age-FIRE)/AFTER);fade=1-smooth((age-FIRE)/AFTER)
 if end<=start:return im
 a=Image.new('RGBA',im.size);d=ImageDraw.Draw(a)
 def pt(x,y=0):return (o[0]+v[0]*x-v[1]*y,o[1]+v[1]*x+v[0]*y)
 for w,c in [(19,(*outer,90)),(11,(*inner,175)),(6,(*inner,220)),(2,(*white,255))]:d.line([pt(start),pt(end)],fill=(*c[:3],int(c[3]*fade)),width=max(1,round(w*scale*max(.25,fade))))
 if age<.13:
  r=(4+20*age/.13)*scale;alpha=int(200*(1-age/.13));d.line([pt(3*scale+r*.28*math.cos(i*math.tau/48),r*math.sin(i*math.tau/48)) for i in range(49)],fill=(*inner,alpha),width=max(1,round(scale)))
  x,y=o;rr=7*scale*(1-age/.13);d.ellipse((x-rr,y-rr,x+rr,y+rr),fill=(*white,alpha))
 out=im.convert('RGBA');out.alpha_composite(a.filter(ImageFilter.GaussianBlur(3*scale)));out.alpha_composite(a);return out

def beam(im,p,anchor,scale=1.,kind="HiNu"):
    outer,inner,white=PALETTES[kind]
    out=draw_beam(im,p,anchor,scale,kind)
    if anchor is None:return out
    o,v=anchor; age=p.age; end=135*scale*smooth(age/.055); start=135*scale*smooth((age-FIRE)/AFTER); fade=1-smooth((age-FIRE)/AFTER)
    if end<=start:return out
    a=Image.new('RGBA',im.size);d=ImageDraw.Draw(a)
    def pt(x,y=0):return(o[0]+v[0]*x-v[1]*y,o[1]+v[1]*x+v[0]*y)
    for k in range(9):
        u=(k*.137+age*3)%1; x=start+(end-start)*u; y=math.sin(k*2.4+age*24)*4*scale*fade
        d.line([pt(max(start,x-5*scale),y),pt(x,y)],fill=(*white,round(210*fade)),width=max(1,round(scale)))
    if age<.12:
        for k in range(8):
            angle=k*math.tau/8; x=(5+age*90)*scale; y=math.sin(angle)*x; z=math.cos(angle)*x*.6
            d.line([pt(z*.45,y*.45),pt(z,y)],fill=(*white,round(210*(1-age/.12))),width=max(1,round(scale)))
    out.alpha_composite(a.filter(ImageFilter.GaussianBlur(max(.4,scale))));out.alpha_composite(a);return out
