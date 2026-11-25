"""Complete defensive-field choreography; normal cursor restoration is a host handoff."""
from dataclasses import replace
import math
import numpy as np
import special156 as prev
from flight150 import Frame, Jet, PORTS, MODEL_LENGTH, LIFE, LIMIT, MAX_POINTS, pose_matrix, screen, angle_delta
from motion149 import smooth
CENTER=prev.CENTER; SIZE=prev.SIZE
IGNITE=prev.IGNITE; FULL=prev.FULL; RELEASE=prev.RELEASE
DEPART=prev.END; STAGGER=.045; TURN=.16; ACCEL=.085; SPEED=2200.; TRAVEL=.52
END=DEPART+6*STAGGER+TURN+TRAVEL+LIFE
sample_field=prev.sample_field

def start(i):return DEPART+i*STAGGER

def state(t,i,center,size,ref):
    age=max(0.,t-start(i)); k=size/SIZE
    radial=screen(ref.translation)-center
    d=radial/np.linalg.norm(radial); target=math.atan2(-d[1],d[0])
    delta=angle_delta(ref.heading,target)
    h=ref.heading+delta*smooth(age/TURN)
    u=max(0.,age-TURN); a=min(u,ACCEL)
    dist=k*SPEED*(a*a/(2*ACCEL)+max(0.,u-ACCEL))
    speed=k*SPEED*min(1.,u/ACCEL)
    power=smooth(u/.055)
    side=.42*math.sin(math.pi*min(1.,age/TURN))**2 if age<TURN else 0.
    R=pose_matrix(h,0.,0.); tr=ref.translation+np.array([d[0],-d[1],0.])*dist
    return R,tr,h,speed,power,side,delta

def trail(t,i,center,size,ref):
    hist=[]; length=0.; limit=LIMIT*ref.scale*MODEL_LENGTH/82
    for q in np.linspace(t,max(start(i)+TURN,t-LIFE+1e-6),MAX_POINTS):
        R,tr,_,speed,power,_,_=state(float(q),i,center,size,ref)
        if speed<=8 or power<=.045:break
        p=screen(tr+ref.scale*(R@np.asarray(PORTS['rear'][0])))
        if hist:
            a,old,v=hist[-1]; seg=float(np.linalg.norm(p-old))
            if seg<1e-9:continue
            if length+seg>limit:
                f=(limit-length)/seg;hist.append((a+(q-a)*f,old+(p-old)*f,v+(power-v)*f));break
            length+=seg
        hist.append((float(q),p,power))
    return tuple(reversed(hist))

def sample_indexed(t,center=CENTER,size=SIZE):
    t,center,size=prev.prev.launch.validate(t,center,size)
    if t<DEPART:return prev.sample_indexed(t,center,size)
    if t>=END:return ()
    units=[]
    for i,ref in prev.prev.sample_indexed(prev.prev.READY,center,size):
        if t<start(i):units.append((i,replace(ref,t=t)));continue
        R,tr,h,speed,power,side,delta=state(t,i,center,size,ref)
        jets=tuple(Jet(k,tr+ref.scale*(R@p),R@d,power if k=='rear' else side if k==('left' if delta>0 else 'right') else 0.,w*ref.scale) for k,(p,d,w) in PORTS.items())
        trails={k:() for k in PORTS}
        if t>start(i)+TURN:trails['rear']=trail(t,i,center,size,ref)
        units.append((i,Frame(t,True,R,tr,ref.scale,speed,h,0.,0.,jets,trails,ref.deploy_time)))
    return tuple(units)

def sample(t,center=CENTER,size=SIZE):return tuple(f for _,f in sample_indexed(t,center,size))

class SpecialDeparture(prev.SpecialBarrier):
    @property
    def normal_visible(self):return not self.active
    def update(self,t,visible=True,context=None):
        if not self.active:return ()
        t=float(t)
        if not visible or context!=self.context or not math.isfinite(t) or t<self.last or t-self.last>.25 or t-self.start>=END:
            self.reset();return ()
        self.last=t;age=t-self.start
        units=sample_indexed(age,self.center,self.size)
        self.field=sample_field(age,self.center,self.size,units)
        return units
