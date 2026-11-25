"""Shiranui seven-unit special launch, separate from Fleet153. Analytic reference.
Screen x right/y down. Positions and order are provisional, not an exact anime recreation.
"""
import math
import numpy as np
from flight150 import Frame, Jet, PORTS, MODEL_LENGTH, LIFE, LIMIT, MAX_POINTS, pose_matrix, screen
from motion149 import DURATION, smooth
CENTER=(320.,192.); SIZE=74.; HOLD=.36; SLIDE=.28; LAUNCH=.84; ACCEL=.09; SPEED=1550.; END=1.72
# Stable IDs: upper L/R, outside L/R, lower L/R, center. Center positions in baseline pixels.
LAYOUT=((-52,-68,103,0,.0), (52,-68,77,180,.04),(-132,-3,165,0,.08),(132,-3,15,180,.12),(-54,33,109,0,.16),(54,33,71,180,.20),(0,83,-90,0,.24))
REAR=np.asarray(PORTS['rear'][0]); LOCAL_CENTER=np.array([0.,0.,0.])
def validate(t,center,size):
    t=float(t); center=np.asarray(center,float);size=float(size)
    if not math.isfinite(t) or center.shape!=(2,) or not np.isfinite(center).all() or not math.isfinite(size) or not 1<=size<=1024:raise ValueError('invalid input')
    return t,center,size

def timing(t,i):
    lag=LAYOUT[i][4]; start=LAUNCH+lag; u=max(0.,t-start); a=min(u,ACCEL)
    sep=smooth((t-HOLD-lag)/SLIDE);travel=16*sep+SPEED*a*a/(2*ACCEL)+SPEED*max(0.,u-ACCEL)
    phase=np.clip((t-HOLD-lag)/SLIDE,0,1)
    speed=16*6*phase*(1-phase)/SLIDE+SPEED*min(1.,u/ACCEL)
    dep=float(np.clip(t-HOLD-lag-.10,0,DURATION));power=smooth(u/.06)
    return travel,speed,dep,power

def position(t,i,center,size):
    x,y,deg,bank,_=LAYOUT[i];h=math.radians(deg);b=math.radians(bank);R=pose_matrix(h,b,0.)
    d=np.array([math.cos(h),-math.sin(h)]);travel,speed,dep,power=timing(t,i);factor=size/SIZE
    p=center+factor*(np.array([x,y])+d*travel);tr=np.array([p[0],-p[1],0.]);scale=size/MODEL_LENGTH
    return R,tr,scale,float(speed*factor),h,b,dep,power

def trail(t,i,center,size,R,scale):
    hist=[]; limit=LIMIT*size/82.; length=0.
    for q in np.linspace(t,max(0.,t-LIFE+1e-6),MAX_POINTS):
        _,tr,_,_,_,_,_,power=position(float(q),i,center,size)
        if power<=.045:break
        p=screen(tr+scale*(R@REAR))
        if hist:
            seg=float(np.linalg.norm(p-hist[-1][1]));
            if seg<1e-9:continue
            if length+seg>limit:
                a,old,v=hist[-1];f=(limit-length)/seg
                hist.append((a+(q-a)*f,old+(p-old)*f,v+(power-v)*f));break
            length+=seg
        hist.append((float(q),p,power))
    return tuple(reversed(hist))

def sample_indexed(t,center=CENTER,size=SIZE):
    t,center,size=validate(t,center,size)
    if not 0<=t<END:return ()
    units=[]
    for i in range(7):
        R,tr,scale,speed,h,b,dep,power=position(t,i,center,size)
        jets=tuple(Jet(k,tr+scale*(R@p),R@d,power if k=='rear' else 0.,w*scale) for k,(p,d,w) in PORTS.items())
        trails={k:() for k in PORTS};trails['rear']=trail(t,i,center,size,R,scale)
        units.append((i,Frame(t,True,R,tr,scale,speed,h,b,0.,jets,trails,dep)))
    return tuple(units)

def sample(t,center=CENTER,size=SIZE):return tuple(f for _,f in sample_indexed(t,center,size))
class SpecialLaunch:
    def __init__(self):self.reset()
    def reset(self):self.start=self.last=self.context=self.center=self.size=None
    @property
    def active(self):return self.start is not None
    def trigger(self,t,center=CENTER,size=SIZE,context=None):
        if self.active:return False
        t,center,size=validate(t,center,size)
        self.start=self.last=t;self.center=center.copy();self.size=size;self.context=context;return True
    def update(self,t,visible=True,context=None):
        if not self.active:return ()
        t=float(t)
        if not visible or context!=self.context or not math.isfinite(t) or t<self.last or t-self.last>.25 or t-self.start>=END:
            self.reset();return ()
        self.last=t;return sample_indexed(t-self.start,self.center,self.size)
