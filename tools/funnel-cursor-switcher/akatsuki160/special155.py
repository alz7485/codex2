"""Seven Shiranui return arcs, following Trial154 exactly. Screen-space perspective proxy.
Fixed IDs; off-screen transit is intentionally not simulated. Ring is a provisional staging pose.
"""
import math
import numpy as np
import special154 as launch
from flight150 import Frame, Jet, PORTS, MODEL_LENGTH, LIFE, LIMIT, MAX_POINTS, pose_matrix, screen, angle_delta
from motion149 import DURATION, smooth
CENTER=launch.CENTER; SIZE=launch.SIZE
RETURN=1.78; STAGGER=.045; APPROACH=.42; PAUSE=.07; SETTLE=.20; HOLD=.28
READY=RETURN+6*STAGGER+APPROACH+PAUSE+SETTLE; END=READY+HOLD
# Seven separate radial sectors, preserving the left/right identity of each launched unit.
ANGLES=(141.,39.,180.,0.,218.,322.,270.)
RING=(190.,126.); DIST=650.; BOW=68.; CAMERA=800.

def start(i):return RETURN+i*STAGGER

def progress(u):
    # Constant speed then quadratic braking, C1 at braking boundary.
    u=max(0.,min(1.,u)); b=.20; n=1-b/2
    if u<=1-b:return u/n,1/n
    v=(1-u)/b
    return 1-b*v*v/(2*n),v/n

def _approach(u,i,center,size):
    u=max(0.,min(1.,u)); k=size/SIZE; a=math.radians(ANGLES[i]); e=np.array([math.cos(a),-math.sin(a)]); tangent=np.array([-e[1],e[0]])
    p,v=progress(u); sign=1 if i%2==0 else -1
    # Bow fades out at arrival; tangent stays radial for clean braking.
    wave=math.sin(math.pi*p)**2; dw=math.pi*math.sin(2*math.pi*p)
    goal=center+k*np.array([RING[0]*e[0],RING[1]*e[1]])
    xy=goal+k*(e*DIST*(1-p)+sign*tangent*BOW*wave)
    derivative=k*(-e*DIST+sign*tangent*BOW*dw); vel=derivative*v/APPROACH
    h=math.atan2(-derivative[1],derivative[0]); bank=sign*.42*math.sin(math.pi*u)**2
    # Apparent approach from deep background, then pull back to a common staging plane.
    z=-480+650*smooth(u/.58)-345*smooth((u-.58)/.42)
    pitch=.29*math.sin(math.pi*u)-.36*math.sin(math.pi*max(0.,u-.5)/.5)
    scale=size/MODEL_LENGTH*CAMERA/(CAMERA-z)
    power=(.35+.65*smooth(u/.12))*(1-smooth((u-.8)/.2))
    return xy,z,scale,float(np.linalg.norm(vel)),h,bank,pitch,power

def state(t,i,center,size):
    age=t-start(i); u=age/APPROACH
    xy,z,scale,speed,h,b,p,power=_approach(u,i,center,size)
    if age>=APPROACH:
        target=math.atan2(xy[1]-center[1],center[0]-xy[0]); q=smooth((age-APPROACH-PAUSE)/SETTLE)
        h+=angle_delta(h,target)*q; b=p=0.;speed=power=0.
    R=pose_matrix(h,b,p);tr=np.array([xy[0],-xy[1],z])
    return R,tr,scale,speed,h,b,p,power

def trail(t,i,center,size,scale):
    hist=[]; length=0.;limit=LIMIT*scale*MODEL_LENGTH/82
    for q in np.linspace(t,max(start(i),t-LIFE+1e-6),MAX_POINTS):
        R,tr,s,sp,_,_,_,power=state(float(q),i,center,size)
        # Keep old samples during braking but never add stationary samples.
        if power<=.045 or sp<=8:continue
        pt=screen(tr+s*(R@np.asarray(PORTS['rear'][0])))
        if hist:
            a,old,v=hist[-1];seg=float(np.linalg.norm(pt-old))
            if seg<1e-9:continue
            if length+seg>limit:
                f=(limit-length)/seg;hist.append((a+(q-a)*f,old+(pt-old)*f,v+(power-v)*f));break
            length+=seg
        hist.append((float(q),pt,power))
    return tuple(reversed(hist))

def sample_indexed(t,center=CENTER,size=SIZE):
    t,center,size=launch.validate(t,center,size)
    if t<launch.END:return launch.sample_indexed(t,center,size)
    if t>=END:return ()
    units=[]
    for i in range(7):
        if t<start(i):continue
        R,tr,scale,speed,h,b,p,power=state(t,i,center,size)
        jets=tuple(Jet(k,tr+scale*(R@pos),R@d,power if k=='rear' else 0.,w*scale) for k,(pos,d,w) in PORTS.items())
        trails={k:() for k in PORTS};trails['rear']=trail(t,i,center,size,scale) if t<start(i)+APPROACH+LIFE else ()
        units.append((i,Frame(t,True,R,tr,scale,speed,h,b,p,jets,trails,DURATION)))
    return tuple(units)

def sample(t,center=CENTER,size=SIZE):return tuple(f for _,f in sample_indexed(t,center,size))
class SpecialReturn(launch.SpecialLaunch):
    def update(self,t,visible=True,context=None):
        if not self.active:return ()
        t=float(t)
        if not visible or context!=self.context or not math.isfinite(t) or t<self.last or t-self.last>.25 or t-self.start>=END:
            self.reset();return ()
        self.last=t;return sample_indexed(t-self.start,self.center,self.size)
