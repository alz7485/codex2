"""Trial111: fast 3D passes, independent stop/turn/go and rear-oblique volley."""
import math,itertools
from dataclasses import dataclass
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from .special_trial109 import TARGETS, STARTS as OLD_STARTS, CAMERA_Z, SCALE, REENTRY, MOVE, CHARGE, SpecialVolley as Previous
from .special_trial106 import sample as opening, phase as opening_phase
from .thrust_trial86 import clamp,smooth
from .nozzle_trial104 import resolve
from .rig_trial61 import matrix as hinge_matrix
from .fire_trial89 import FirePose,FIRE,AFTER
DURATION=3.45; FORMATION=REENTRY+DURATION; SHOT=FORMATION+MOVE+CHARGE; END=SHOT+FIRE+AFTER+.22
AIM=np.array([-.66,.43,-.62]); AIM/=np.linalg.norm(AIM)
STOP_IDS=(1,4); RADIUS=1.4506875696759138
# Screen-space key positions converted into real world coordinates. All segments are straight in 3D.
def world(x,y,z):return np.array([x*(CAMERA_Z-z)/CAMERA_Z,y*(CAMERA_Z-z)/CAMERA_Z,z])
def norm(v):return v/max(1e-12,np.linalg.norm(v))
def basis(v,i):
    f=norm(v); x=norm(np.cross(f,[0,0,1]))
    if np.linalg.norm(x)<.01:x=norm(np.cross(f,[0,1,0]))
    y=np.cross(-f,x); r=math.radians(48 if i%2==0 else -48); c,s=math.cos(r),math.sin(r)
    return np.column_stack((x*c+y*s,-x*s+y*c,-f))
def blend(a,b,q):return Slerp([0,1],Rotation.from_matrix(np.stack([a,b])))([clamp(q)]).as_matrix()[0]
# Each path: (time, position). Stop units have duplicate points with actual dwell;
# pass units cross screen without stopping; all make a second entry before formation.
def eval_pos(times,pts,t):
    t=np.asarray(t); return np.stack([np.interp(t,times,pts[:,j]) for j in range(3)],axis=-1)
def build(seed):
    rng=np.random.default_rng(seed); ts=np.linspace(0,DURATION,829); out=[]; tracks=[]
    def edge(k,z):
        a=rng.uniform(-8,8); x,y=[(-22,a),(22,a),(a,22),(a,-22)][k%4];return world(x,y,z)
    for i in range(6):
        for attempt in range(1200):
            near=[12,5,-22,-12,8,-26][i]; z1=near+rng.uniform(-3,3);z2=near+rng.uniform(-6,6)
            d=.03+i*.065+rng.uniform(0,.07); t1=d+rng.uniform(.24,.42); t2=t1+rng.uniform(.20,.34); t3=t2+rng.uniform(.28,.48)
            # Exit again before next entry; the path between exit and entry is routed outside screen.
            e0=i%4; e1=(e0+2)%4; e2=(e1+(1 if i%2 else -1))%4
            p0=edge(e0,z1); p1=world(rng.uniform(-6,6),rng.uniform(-7,7),near); p2=edge(e1,z2)
            if i in STOP_IDS:
                times=[0,d,t1,t2,t3]; pts=[p0,p0,p1,p1,p2]
            else:
                t3=d+rng.uniform(.36,.57);times=[0,d,t3];pts=[p0,p0,p2]
            # route around the frame via corner, not through it
            sx=1 if e1==1 or e2==1 else -1;sy=1 if e1==2 or e2==2 else -1
            corner=world(sx*23,sy*23,z2); p3=edge(e2,near+rng.uniform(-5,5)); t4=t3+.18;t5=t4+.22
            end=np.array(OLD_STARTS[i].position);times += [t4,t5,max(t5+.03,rng.uniform(1.12,1.72)),DURATION-rng.uniform(.08,.30),DURATION];pts += [corner,p3,p3,end,end]
            times=np.array(times);pts=np.array(pts);xy=eval_pos(times,pts,ts)
            if np.any(np.diff(times)<=0) or any(np.min(np.linalg.norm(xy-old,axis=1))<3.10 for old in tracks):continue
            out.append((times,pts));tracks.append(xy);break
        else:return None
    return tuple(out)
from .special_trial110 import ROUTES as BASE_ROUTES, seed
# Keep the previously validated terminal positions; select only separated enhancements.
ROUTES=[(t.copy(),p.copy()) for t,p in BASE_ROUTES]
TS=np.linspace(0,DURATION,829)
def acceptable(i,t,p):
    xy=eval_pos(t,p,TS)
    return np.all(np.diff(t)>0) and all(np.min(np.linalg.norm(xy-eval_pos(ot,op,TS),axis=1))>3.02 for j,(ot,op) in enumerate(ROUTES) if j!=i)
DEPTH_CHANGES={}
for i,dz in ((0,8),(5,-7),(2,-5)):
    t,p=ROUTES[i]; old=p.copy()
    for factor in (1,.75,.5,.25):
        p=old.copy(); z=p[:-2,2]+dz*factor; p[:-2,:2]*=((CAMERA_Z-z)/(CAMERA_Z-p[:-2,2]))[:,None];p[:-2,2]=z
        if acceptable(i,t,p):ROUTES[i]=(t,p);DEPTH_CHANGES[i]=dz*factor;break
EXTRA_PASSES=[]
# Replace offscreen wait with an extra crossing and route along the frame perimeter.
for i in (0,2,3,5):
    t,p=ROUTES[i]; z=p[4,2]; start=t[4]; end=t[-2]; rng=np.random.default_rng(111+i)
    for trial in range(80):
        if end-start<1.15:break
        # Opposite of entry screen edge, then an exterior corner and re-entry.
        pp=p[4,:2]*CAMERA_Z/(CAMERA_Z-z); axis=int(np.argmax(abs(pp))); sign=np.sign(pp[axis]); a=np.zeros(2);a[axis]=-sign*22;a[1-axis]=rng.uniform(-8,8)
        c=np.array(a); c[1-axis]=22*(1 if trial%2 else -1)
        e=c.copy(); e[axis]=rng.uniform(-8,8)
        nt=np.r_[t[:5],start+.40,start+.57,start+.74,end,t[-1]]; np_=np.vstack([p[:5],world(*a,z),world(*c,z),world(*e,z),p[-2:]])
        if acceptable(i,nt,np_):ROUTES[i]=(nt,np_);EXTRA_PASSES.append(i);break
# Near-camera first pass only; exterior route need not move closer.
t,p=ROUTES[0]; old=p.copy()
for dz in (9,7,5,3,1):
    p=old.copy(); z=p[:3,2]+dz; p[:3,:2]*=((CAMERA_Z-z)/(CAMERA_Z-p[:3,2]))[:,None];p[:3,2]=z
    if acceptable(0,t,p):ROUTES[0]=(t,p);DEPTH_CHANGES[0]=dz;break
ROUTES=tuple(ROUTES)
@dataclass(frozen=True)
class Unit:
    id:int; position:tuple; rotation:tuple; power:float; acceleration:tuple; visible:bool=True; fire:FirePose=FirePose()
    def transform(self):
        m=np.eye(4);m[:3,:3]=SCALE*np.asarray(self.rotation).reshape(3,3);m[:3,3]=self.position;return m
    def part_matrix(self,side):return self.transform()@hinge_matrix(side,0)
    def thrusters(self):return resolve(self.transform(),self.acceleration)
def make(i,pos,r,a,visible=True,fire=FirePose()):
    a=np.asarray(a);return Unit(i,tuple(pos),tuple(r.ravel()),float(np.linalg.norm(a)),tuple(a),visible,fire)
def flight_unit(i,t):
    times,pts=ROUTES[i]; t=max(0,min(DURATION,t)); k=min(len(times)-2,max(0,int(np.searchsorted(times,t,side='right')-1))); q=clamp((t-times[k])/(times[k+1]-times[k])); v=pts[k+1]-pts[k]; moving=np.linalg.norm(v)>1e-8
    def direction(indices):
        for j in indices:
            if np.linalg.norm(pts[j+1]-pts[j])>1e-8:return norm(pts[j+1]-pts[j])
        return AIM
    prev=direction(range(k-1,-1,-1)); nex=direction(range(k+1,len(times)-1)); f=norm(v) if moving else prev
    # braking/launch ramps around a stop; constant speed for through passes.
    if moving:
        r=basis(f,i); a=f*.84; stop_next=k+1<len(times)-1 and np.linalg.norm(pts[k+2]-pts[k+1])<1e-8
        if stop_next and q>.79:a=-f*(q-.79)/.21 + r[:,1]*(.85*math.sin(math.pi*(q-.79)/.21))
        elif k>0 and np.linalg.norm(pts[k]-pts[k-1])<1e-8:a=f*(1-.28*q)
        if k>0 and np.linalg.norm(pts[k]-pts[k-1])>1e-8 and q<.12:
            r=blend(basis(prev,i),r,smooth(q/.12));a=norm(f-prev)*.9
    else:
        r=blend(basis(prev,i),basis(nex,i),smooth(q)); r=r@Rotation.from_rotvec([0,0,math.radians(18)*math.sin(math.pi*q)*(1 if i%2 else -1)]).as_matrix();a=norm(nex-prev)*(.98*math.sin(math.pi*q)) if 0<k<len(times)-2 else np.zeros(3)
        if k==0:r=basis(nex,i)
        if k==len(times)-2:r=basis(prev,i)
    pos=eval_pos(times,pts,t);return make(i,pos,r,a,t>=times[1])
STARTS=tuple(flight_unit(i,DURATION) for i in range(6))
# Use existing safe position mapping; new aim is real 3D, not image rotation.
from .special_trial109 import DELAYS,ARRIVALS

def unit(i,age):
    start=STARTS[i]; e=age-FORMATION; duration=ARRIVALS[i]-DELAYS[i];u=clamp((e-DELAYS[i])/duration);q=smooth(u);p0=np.array(start.position);delta=TARGETS[i]-p0;pos=p0+q*delta
    r0=np.asarray(start.rotation).reshape(3,3);r=blend(r0,basis(delta,i),smooth(u/.4));r=blend(r,basis(AIM,i),smooth((u-.45)/.55)); a=norm(delta)*(1-2*u)*math.sin(math.pi*u);f=FirePose()
    if e>=MOVE:
        r=basis(AIM,i);a=np.zeros(3)
        if age<SHOT:f=FirePose('charge',charge=smooth((e-MOVE)/CHARGE))
        elif age<SHOT+FIRE:
            b=age-SHOT; recoil=.13*math.sin(math.pi*min(1,b/.12));f=FirePose('fire',recoil=recoil,age=b);pos=pos-AIM*recoil*SCALE
        elif age<SHOT+FIRE+AFTER:f=FirePose('afterglow',age=age-SHOT)
    return make(i,pos,r,a,fire=f)
def phase(t):
    if t<REENTRY:return opening_phase(t)
    if t<FORMATION:return 'high-speed'
    if t<FORMATION+MOVE:return 'formation'
    if t<SHOT:return 'charge'
    if t<SHOT+FIRE:return 'volley'
    return 'afterglow' if t<END else 'off'
def sample(t):
    if not math.isfinite(t):raise ValueError('invalid age')
    if t<REENTRY:return opening(t)
    if t<FORMATION:return tuple(flight_unit(i,t-REENTRY) for i in range(6))
    if t<END:return tuple(unit(i,t) for i in range(6))
    return ()
def shot_matrix(i):return unit(i,SHOT).transform()
class SpecialVolley(Previous):
    def trigger(self,t,context=None):
        if not math.isfinite(t):raise ValueError('invalid time')
        if self.start is not None and 0<=t-self.start<END:return False
        self.start=self.last=t;self.context=context;return True
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=END:self.reset();return ()
        self.last=t;return sample(t-self.start)
