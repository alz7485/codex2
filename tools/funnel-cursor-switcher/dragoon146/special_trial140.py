"""Eight DRAGOON wing launch, independent analytic paths. Screen y down.
Wing layout is an approximation, not an exact reproduction of the anime.
"""
import math
import numpy as np
from flight_trial135 import Frame,Jet,PORTS,pose_matrix,screen,LIFE,LIMIT
ANGLES=(64.,23.,-21.,-62.)
CENTER=(320.,192.); SIZE=74.; HOLD=.60; SLIDE=.22; LAUNCH=.90; ACCEL=.16; SPEED=650.; STAGGER=.055; END=2.20

def smooth(x):
    x=min(1.,max(0.,x));return x*x*(3-2*x)
def travel(t,i):
    u=max(0.,t-LAUNCH-i*STAGGER);a=min(u,ACCEL)
    return 12*smooth((t-HOLD)/SLIDE)+SPEED*a*a/(2*ACCEL)+SPEED*max(0.,u-ACCEL)
def power(t,i):return smooth((t-LAUNCH-i*STAGGER)/.065)
def sample(t,center=CENTER,size=SIZE):
    t=float(t);center=np.asarray(center,float);size=float(size)
    if not math.isfinite(t) or center.shape!=(2,) or not np.isfinite(center).all() or not math.isfinite(size) or not 1<=size<=1024:raise ValueError('invalid input')
    if t<0 or t>=END:return ()
    scale=size/6.6; factor=size/SIZE; units=[]
    for side in (1,-1):
        for i,deg in enumerate(ANGLES):
            h=math.radians(deg if side==1 else 180-deg);bank=0 if side==1 else math.pi
            R=pose_matrix(h,bank,0);d=np.array([math.cos(h),-math.sin(h)])
            root=center+factor*(np.array([side*25.,0.])+35*d)
            rear=root+d*factor*travel(t,i)
            tr=np.array([rear[0],-rear[1],0.])-scale*(R@np.asarray(PORTS['rear'][0]))
            jets=tuple(Jet(k,tr+scale*(R@p),R@v,power(t,i) if k=='rear' else 0.,w*scale) for k,(p,v,w) in PORTS.items())
            hist=[]
            for q in np.linspace(max(0,t-LIFE+1e-6),t,20):
                a=power(q,i);p=root+d*factor*travel(q,i)
                if a>.045 and (not hist or np.linalg.norm(p-hist[-1][1])>1.2*factor):hist.append((float(q),p,a))
            if len(hist)>1:
                limit=LIMIT*size/82; newest=hist[-1][1];old=[]
                for a,p,v in reversed(hist):
                    if np.linalg.norm(p-newest)>limit:
                        b,r,w=old[-1];f=(limit-np.linalg.norm(r-newest))/max(np.linalg.norm(p-r),1e-12)
                        old.append((b+(a-b)*f,r+(p-r)*f,w+(v-w)*f));break
                    old.append((a,p,v))
                hist=list(reversed(old))
            trails={k:() for k in PORTS};trails['rear']=tuple(hist)
            slide_u=min(1.,max(0.,(t-HOLD)/SLIDE))
            speed=factor*(12*6*slide_u*(1-slide_u)/SLIDE+SPEED*min(1.,max(0.,(t-LAUNCH-i*STAGGER)/ACCEL)))
            units.append(Frame(t,True,R,tr,scale,speed,h,bank,0.,jets,trails))
    return tuple(units)
class SpecialLaunch:
    def __init__(self):self.reset()
    def reset(self):self.start=self.last=self.context=self.center=self.size=None
    @property
    def active(self):return self.start is not None
    def trigger(self,t,center=CENTER,size=SIZE,context=None):
        if self.active:return False
        sample(0,center,size)
        if not math.isfinite(float(t)):raise ValueError('invalid time')
        self.start=self.last=float(t);self.context=context;self.center=np.asarray(center,float).copy();self.size=float(size);return True
    def update(self,t,visible=True,context=None):
        if not self.active:return ()
        t=float(t)
        if not visible or context!=self.context or not math.isfinite(t) or t<self.last or t-self.last>.25 or t-self.start>=END:
            self.reset();return ()
        self.last=t;return sample(t-self.start,self.center,self.size)
