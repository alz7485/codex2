"""Fast direct insertion, abrupt braking, locked formation before synchronized volley."""
import itertools, math
import numpy as np
from . import special_trial112 as old
from .special_trial112 import (REENTRY, FORMATION, CAMERA_Z, SCALE, AIM, RADIUS, FirePose, FIRE, AFTER, CHARGE, basis, blend, norm, make, world, clamp, smooth, SpecialVolley as Previous, STARTS, P0, V0, MUZZLE, FORWARD_POINT, ray_gap)
# Deliberately asymmetric diagonal composition, in projected coordinates with genuine depth.
SLOTS=np.array([world(-9,8,-15),world(-3,7,-9),world(-7,1,-3),world(3,4,4),world(-1,-5,10),world(7,-6,18)])
SLOT_ARR=np.array([.44,.48,.53,.59,.64,.72]); MOVE=float(max(SLOT_ARR)); HOLD=.24
SHOT=FORMATION+MOVE+HOLD+CHARGE; END=SHOT+FIRE+AFTER+.22
RAMP=.075; BRAKE=.115
# Piecewise integrated velocity: short initial turn, constant cruise, last-moment braking.
def cruise(i,s):
    d=SLOT_ARR[s]; return (SLOTS[s]-P0[i]-.5*RAMP*V0[i])/(d-.5*(RAMP+BRAKE))
def path(i,s,t):
    d=SLOT_ARR[s]; v=cruise(i,s); t=np.clip(np.asarray(t),0,d)[...,None]
    u=np.minimum(t,RAMP); w=np.clip(t-RAMP,0,d-RAMP-BRAKE); b=np.clip(t-(d-BRAKE),0,BRAKE)
    return P0[i]+V0[i]*u+.5*(v-V0[i])*u*u/RAMP+v*w+v*(b-.5*b*b/BRAKE)
TS=np.linspace(0,MOVE,361)
CACHE={(i,s):path(i,s,TS) for i in range(6) for s in range(6)}
choices=[]
for perm in itertools.permutations(range(6)):
    pp=[CACHE[i,s] for i,s in enumerate(perm)]
    gap=min(np.linalg.norm(pp[i]-pp[j],axis=1).min() for i,j in itertools.combinations(range(6),2))
    if gap>2*RADIUS+.10:
        cost=sum(np.linalg.norm(cruise(i,s)) for i,s in enumerate(perm))
        choices.append((cost,perm,gap))
if not choices:raise RuntimeError('no safe fast approach')
_,ASSIGNMENT,_=min(choices); TARGETS=SLOTS[list(ASSIGNMENT)]; ARRIVALS=SLOT_ARR[list(ASSIGNMENT)]
assert ray_gap(TARGETS)>0

def pos(i,e):return path(i,ASSIGNMENT[i],e)
def unit(i,age):
    e=age-FORMATION; d=ARRIVALS[i]; v=cruise(i,ASSIGNMENT[i]); p=pos(i,e)
    r0=np.asarray(STARTS[i].rotation).reshape(3,3)
    r=blend(r0,basis(v,i),smooth(e/RAMP)); a=norm(v)*.86
    if e<RAMP:a=(1-smooth(e/RAMP))*np.array(STARTS[i].acceleration)+smooth(e/RAMP)*norm(v-V0[i])
    if e>=d-BRAKE:
        q=clamp((e-d+BRAKE)/BRAKE);r=blend(r,basis(AIM,i),smooth(q));a=-norm(v)*(.95 if e<d else 0.)
    if e>=d:p=TARGETS[i].copy();r=basis(AIM,i);a=np.zeros(3)
    f=FirePose()
    if age>=FORMATION+MOVE+HOLD:
        if age<SHOT:f=FirePose('charge',charge=smooth((age-(FORMATION+MOVE+HOLD))/CHARGE))
        elif age<SHOT+FIRE:
            b=age-SHOT; recoil=.13*math.sin(math.pi*min(1,b/.12));p=p-AIM*recoil*SCALE;f=FirePose('fire',recoil=recoil,age=b)
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
