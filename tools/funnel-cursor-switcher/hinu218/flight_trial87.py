"""Visual flight controller. Seconds, physical pixel coordinates; no OS hooks."""
import math
from dataclasses import dataclass
from .thrust_trial86 import Thrust

def clamp(x,a,b):return max(a,min(b,x))
def wrap(x):return (x+math.pi)%math.tau-math.pi
@dataclass(frozen=True)
class Pose:
    heading:float
    bank:float
    pitch:float
    power:float
    speed:float
class Flight:
    def __init__(self,home=math.radians(-135)):
        if not math.isfinite(home):raise ValueError('invalid home')
        self.home=wrap(home);self.thrust=Thrust();self.reset()
    def reset(self):
        self.last=None;self.heading=self.home;self.bank=self.pitch=self.speed=0.;self.thrust.reset()
    def update(self,t,xy,enabled=True,context=None,fixed=False):
        xy=tuple(xy)
        if len(xy)!=2 or not all(math.isfinite(v) for v in (t,*xy)):raise ValueError('invalid input')
        old=self.last;key=(context,bool(fixed))
        if not enabled or old is None or t<old[0] or t-old[0]>.25 or math.dist(xy,old[1])>500 or key!=old[2] or (t==old[0] and xy!=old[1]):self.reset();old=None
        p=self.thrust.update(t,xy,enabled,key)
        if enabled and old is not None and t>old[0]:
            dt=t-old[0];dx,dy=xy[0]-old[1][0],xy[1]-old[1][1];raw=math.hypot(dx,dy)/dt
            acc=clamp((raw-self.speed)/dt,-2500,2500);self.speed+=(1-math.exp(-dt/.09))*(raw-self.speed)
            moving=raw>6;target=self.home if fixed or not moving else math.atan2(dy,dx)
            err=wrap(target-self.heading);self.heading=wrap(self.heading+(1-math.exp(-dt/(.095 if moving else .42)))*err)
            bank=clamp(math.degrees(err)*.72,-30,30) if moving and not fixed else 0.
            pitch=clamp(acc/145,-12,12) if moving or self.speed>12 else 0.
            if fixed:self.heading=self.home
            a=1-math.exp(-dt/.14);self.bank+=a*(bank-self.bank);self.pitch+=a*(pitch-self.pitch)
        self.last=(t,xy,key) if enabled else None
        return Pose(self.heading,self.bank,self.pitch,p,self.speed)

def pose_matrix(pose,right,up,toward,pivot,screen_offset=(0,0),units_per_px=1.):
    """Rigid transform for rear-oblique camera; forward -Z, screen y down."""
    import numpy as np
    from trimesh.transformations import rotation_matrix
    right,up,toward,pivot=map(lambda x:np.asarray(x,dtype=float),(right,up,toward,pivot))
    forward=np.array([0.,0.,-1.]);axis=np.cross(toward,forward);axis/=np.linalg.norm(axis)
    m=rotation_matrix(math.radians(pose.pitch),axis,point=pivot)@rotation_matrix(math.radians(pose.bank),forward,point=pivot)
    f=m[:3,:3]@forward;base=math.atan2(-np.dot(f,up),np.dot(f,right));m=rotation_matrix(-wrap(pose.heading-base),toward,point=pivot)@m
    m[:3,3]+=units_per_px*(screen_offset[0]*right-screen_offset[1]*up)
    return m
