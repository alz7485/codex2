"""Trial112: continuous, staggered convergence and composition-led volley."""
import itertools, math
import numpy as np
from . import special_trial111 as old
from .special_trial111 import (REENTRY, CAMERA_Z, SCALE, AIM, RADIUS, FirePose, FIRE, AFTER,
    basis, blend, norm, make, world, clamp, smooth, SpecialVolley as Previous)
from .combat_trial94 import MUZZLE, FORWARD_POINT
# Cut into the last inbound straight segments before the old staging stops.
CUT=2.72
FORMATION=REENTRY+CUT
MOVE=1.34; HOLD=.19; CHARGE=old.CHARGE
SHOT=FORMATION+MOVE+HOLD+CHARGE; END=SHOT+FIRE+AFTER+.22
STARTS=tuple(old.flight_unit(i,CUT) for i in range(6))
P0=np.array([u.position for u in STARTS]); V0=np.array([(np.array(old.flight_unit(i,CUT+.001).position)-np.array(old.flight_unit(i,CUT-.001).position))/.002 for i in range(6)])
# Projected composition: irregular diagonal spread; near hero at lower right, far pair high left.
SLOTS=np.array([world(-5.9,6.4,-13),world(2.1,7.6,-9),world(-7.1,-.3,0),world(.8,1.3,5),world(5.8,-5.5,18),world(-3.2,-7.1,9)])
SLOT_ARR=np.array([.81,.88,1.02,1.08,1.34,1.18])
# Cubic Hermite preserves incoming velocity and settles to zero, with optional overshoot/return.
def hermite(p,q,v,w,d,t):
    u=np.clip(np.asarray(t)/d,0,1)[...,None]
    return (2*u**3-3*u**2+1)*p+(u**3-2*u**2+u)*d*v+(-2*u**3+3*u**2)*q+(u**3-u**2)*d*w

def eval_path(i,slot,offset,t):
    dest=SLOTS[slot]; duration=SLOT_ARR[slot]; t=np.asarray(t)
    if np.linalg.norm(offset)<1e-9:
        return hermite(P0[i],dest,V0[i],np.zeros(3),duration,t)
    d=duration*.76; mid=dest+offset
    first=hermite(P0[i],mid,V0[i],np.zeros(3),d,t)
    second=hermite(mid,dest,np.zeros(3),np.zeros(3),duration-d,t-d)
    return np.where((t<d)[...,None],first,second)

def ray_gap(targets):
    gap=math.inf
    for i,p in enumerate(targets):
        m=make(i,p,basis(AIM,i),np.zeros(3)).transform(); o=(m@[*MUZZLE,1])[:3]
        for j,q in enumerate(targets):
            if i!=j:
                d=q-o;gap=min(gap,np.linalg.norm(d-max(0,np.dot(d,AIM))*AIM)-RADIUS)
    return gap
TS=np.linspace(0,MOVE,323)
# Select assignment by sampled sphere separation and travel length. Two safe overshoots added afterward.
CACHE={(i,s):eval_path(i,s,np.zeros(3),TS) for i in range(6) for s in range(6)}
choices=[]
for perm in itertools.permutations(range(6)):
    pp=[CACHE[i,s] for i,s in enumerate(perm)]
    g=min(np.linalg.norm(pp[i]-pp[j],axis=1).min() for i,j in itertools.combinations(range(6),2))
    if g>2*RADIUS+.12:
        cost=sum(np.linalg.norm(np.diff(p,axis=0),axis=1).sum() for p in pp)
        choices.append((cost,perm,g))
if not choices:raise RuntimeError('no safe convergence assignment')
_,ASSIGNMENT,_=min(choices)
OFFSETS=np.zeros((6,3)); tracks=[CACHE[i,s] for i,s in enumerate(ASSIGNMENT)]
# Prefer late arrivals and visibly lateral overshoot. Keep a genuine braking/return interval.
for i in sorted(range(6),key=lambda i:SLOT_ARR[ASSIGNMENT[i]],reverse=True):
    if np.count_nonzero(np.linalg.norm(OFFSETS,axis=1))>=2:break
    for off in ([2.2,0,0],[-2.2,0,0],[0,-2.2,0],[0,2.2,0],[1.5,-1.4,0],[-1.5,1.4,0]):
        p=eval_path(i,ASSIGNMENT[i],np.array(off),TS)
        if all(np.min(np.linalg.norm(p-q,axis=1))>2*RADIUS+.10 for j,q in enumerate(tracks) if j!=i):
            OFFSETS[i]=off; tracks[i]=p;break
TARGETS=SLOTS[list(ASSIGNMENT)];ARRIVALS=SLOT_ARR[list(ASSIGNMENT)]
assert ray_gap(TARGETS)>0

def pos(i,e):return eval_path(i,ASSIGNMENT[i],OFFSETS[i],e)
def unit(i,age):
    e=age-FORMATION; u=clamp(e/ARRIVALS[i]); p=pos(i,e)
    r0=np.asarray(STARTS[i].rotation).reshape(3,3)
    v=(pos(i,e+.002)-pos(i,e-.002))/.004
    # Aim starts aligning during the final approach; rotation remains continuous.
    r=basis(v,i) if np.linalg.norm(v)>.01 else basis(AIM,i)
    r=blend(r0,r,smooth(e/.14));r=blend(r,basis(AIM,i),smooth((u-.62)/.38))
    a=(pos(i,e+.008)-2*p+pos(i,e-.008))/.008**2
    a=a/max(1.,np.linalg.norm(a));a=(1-smooth(e/.10))*np.array(STARTS[i].acceleration)+smooth(e/.10)*a
    f=FirePose()
    if e>=ARRIVALS[i]:r=basis(AIM,i);a=np.zeros(3)
    if age>=FORMATION+MOVE+HOLD:
        if age<SHOT:f=FirePose('charge',charge=smooth((age-(FORMATION+MOVE+HOLD))/CHARGE))
        elif age<SHOT+FIRE:
            b=age-SHOT;recoil=.13*math.sin(math.pi*min(1,b/.12));p=p-AIM*recoil*SCALE;f=FirePose('fire',recoil=recoil,age=b)
        elif age<SHOT+FIRE+AFTER:f=FirePose('afterglow',age=age-SHOT)
    return make(i,p,r,a,fire=f)
def phase(t):
    if t<FORMATION:return old.phase(t)
    if t<FORMATION+MOVE:return 'formation'
    if t<FORMATION+MOVE+HOLD:return 'ready'
    if t<SHOT:return 'charge'
    if t<SHOT+FIRE:return 'volley'
    return 'afterglow' if t<END else 'off'
def sample(t):
    if not math.isfinite(t):raise ValueError('invalid age')
    if t<FORMATION:return old.sample(t)
    if t<END:return tuple(unit(i,t) for i in range(6))
    return ()
flight_unit=old.flight_unit
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
