"""Hi-Nu special: preserve radial launch, then six independent straight-segment flights.
Pure deterministic timeline; side ports remain provisional (Trial104).
"""
from dataclasses import dataclass
import math
import numpy as np
from special_trial106 import sample as opening, phase as opening_phase, END as REENTRY, SpecialRadialLaunch, CAMERA_Z
from thrust_trial86 import clamp,smooth
from nozzle_trial104 import resolve
from rig_trial61 import matrix as hinge_matrix
DURATION=2.15; END=REENTRY+DURATION; SCALE=.34
# Reproducible independent random routes, rejected if center envelopes approach.
# x,y are model center; z is fixed (no camera scaling during this phase).
SEED=107; MIN_GAP=3.45
DELAYS=(0.,.09,.18,.27,.06,.15)
KEYS=(0.,.36,.73,1.)

def _points_at(points,delay,t):
    q=np.clip((np.asarray(t)-delay)/(DURATION-delay),0,1)
    return np.stack([np.interp(q,KEYS,points[:,j]) for j in range(2)],axis=-1)

def _build_routes():
    rng=np.random.default_rng(SEED); ts=np.linspace(0,DURATION,517); out=[]; samples=[]
    for i,delay in enumerate(DELAYS):
        for attempt in range(25000):
            edge=i%4; a=rng.uniform(-8.5,8.5)
            entry=(( -15.5,a),(15.5,a),(a,15.5),(a,-15.5))[edge]
            pts=np.vstack([entry,rng.uniform(-8.8,8.8,(3,2))]); delta=np.diff(pts,axis=0); lengths=np.linalg.norm(delta,axis=1)
            if min(lengths)<4.5 or max(lengths)>24:continue
            turns=np.sum(delta[:-1]*delta[1:],axis=1)/(lengths[:-1]*lengths[1:])
            if np.any(turns>.76):continue
            xy=_points_at(pts,delay,ts)
            if any(np.min(np.linalg.norm(xy[ts>=max(delay,d)]-old[ts>=max(delay,d)],axis=1))<MIN_GAP for old,d in samples):continue
            out.append(tuple(map(tuple,pts)));samples.append((xy,delay));break
        else: raise RuntimeError('could not build separated routes')
    return tuple(out)
ROUTES=_build_routes()

def _angle(v):return math.atan2(v[1],v[0])
def _mix(a,b,q):return a+((b-a+math.pi)%math.tau-math.pi)*q
@dataclass(frozen=True)
class FlightUnit:
    id:int; position:tuple; heading:float; power:float; acceleration:tuple; visible:bool=True
    def transform(self):
        c,s=math.cos(self.heading),math.sin(self.heading); m=np.eye(4)
        r=math.radians(48 if self.id%2==0 else -48); cr,sr=math.cos(r),math.sin(r)
        m[:3,:3]=SCALE*np.array([[s,0,-c],[-c,0,-s],[0,1,0]])@np.array([[cr,-sr,0],[sr,cr,0],[0,0,1]])
        m[:3,3]=self.position;return m
    def part_matrix(self,side):return self.transform()@hinge_matrix(side,0)
    def thrusters(self):return resolve(self.transform(),self.acceleration,gain=1.)

def flight_unit(i,t):
    delay=DELAYS[i]; pts=np.asarray(ROUTES[i]); q=clamp((t-delay)/(DURATION-delay)); seg=min(2,int(np.searchsorted(KEYS,q,side='right')-1)); vectors=np.diff(pts,axis=0); lengths=np.linalg.norm(vectors,axis=1); directions=vectors/lengths[:,None];
    dt=(DURATION-delay); elapsed=(q-KEYS[seg])*dt; heading=_angle(directions[seg]); turn=0.; steer=np.zeros(2)
    if seg>0:
        turn=1-smooth(elapsed/.11); heading=_mix(_angle(directions[seg-1]),heading,1-turn); steer=(directions[seg]-directions[seg-1])*turn*.9
    power=.72+.28*turn; forward=np.array([math.cos(heading),math.sin(heading)]); a=forward*power+steer
    pos=_points_at(pts,delay,t);return FlightUnit(i,(float(pos[0]),float(pos[1]),0.),heading,power,(float(a[0]),float(a[1]),0.),t>=delay)

def phase(age):
    if age<REENTRY:return opening_phase(age)
    return 'high-speed' if age<END else 'off'

def sample(age):
    if not math.isfinite(age):raise ValueError('invalid age')
    if age<REENTRY:return opening(age)
    if age>=END:return ()
    return tuple(flight_unit(i,age-REENTRY) for i in range(6))

class SpecialHighSpeed(SpecialRadialLaunch):
    def trigger(self,t,context=None):
        if not math.isfinite(t):raise ValueError('invalid time')
        if self.start is not None and 0<=t-self.start<END:return False
        self.start=self.last=t;self.context=context;return True
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=END:self.reset();return ()
        self.last=t;return sample(t-self.start)
