"""Hi-Nu special: continuous transition to six independent parallel firing poses."""
import math,itertools
from dataclasses import dataclass,replace
import numpy as np
from special_trial107 import sample as prior,phase as prior_phase, END as FORMATION, flight_unit, DURATION, FlightUnit, SCALE, CAMERA_Z, REENTRY, SpecialHighSpeed,_mix
from thrust_trial86 import clamp,smooth
from fire_trial89 import FirePose,FIRE,AFTER
from combat_trial94 import MUZZLE,FORWARD_POINT
MOVE=.85; CHARGE=.78; SHOT=FORMATION+MOVE+CHARGE; END=SHOT+FIRE+AFTER+.22; HEADING=math.pi
STARTS=tuple(flight_unit(i,DURATION) for i in range(6))
# Six lanes with deliberately pronounced real depth; projected positions are chosen first. All forward axes point left.
PROJECTED_SLOTS=np.array([(3.7,-8.7,8.),(-2.1,-5.1,-8.),(4.5,-1.75,0.),(-2.8,1.85,8.),(3.5,5.55,-8.),(-.8,9.1,0.)])
SLOTS=PROJECTED_SLOTS.copy(); SLOTS[:,:2]*=(CAMERA_Z-SLOTS[:,2:3])/CAMERA_Z
DELAYS=np.array([.00,.06,.12,.04,.10,.08]); ARRIVALS=np.array([.70,.79,.85,.74,.82,.77])
P0=np.array([u.position for u in STARTS]); TT=np.linspace(0,MOVE,241)[:,None]; Q=np.clip((TT-DELAYS)/(ARRIVALS-DELAYS),0,1); Q=Q*Q*(3-2*Q)
# Minimize total path length, only among assignments with separated bounding spheres.
choices=[]
for perm in itertools.permutations(range(6)):
    targets=SLOTS[list(perm)]; pts=P0[None]+Q[:,:,None]*(targets-P0)[None]; gap=min(np.linalg.norm(pts[:,i]-pts[:,j],axis=1).min() for i,j in itertools.combinations(range(6),2))
    if gap>3.15: choices.append((np.linalg.norm(targets-P0,axis=1).sum(),perm,float(gap)))
if not choices:raise RuntimeError('no separated formation')
_,ASSIGNMENT,_=min(choices); TARGETS=SLOTS[list(ASSIGNMENT)]
@dataclass(frozen=True)
class VolleyUnit(FlightUnit):
    fire:FirePose=FirePose()

def unit(i,age):
    start=STARTS[i]; e=age-FORMATION; duration=ARRIVALS[i]-DELAYS[i]; u=clamp((e-DELAYS[i])/duration); q=smooth(u); delta=TARGETS[i]-P0[i]; pos=P0[i]+q*delta
    # Blend previous heading into transit direction, then final parallel aim.
    travel=math.atan2(delta[1],delta[0]); head=_mix(start.heading,travel,smooth(u/.30)); head=_mix(head,HEADING,smooth((u-.52)/.48));
    # Analytic visual acceleration, blended at boundary. No fictional reverse port.
    a=delta*(6-12*u)/duration**2 if 0<u<1 else np.zeros(3); a=a/max(1.,float(np.linalg.norm(a))); a=(1-smooth(max(0,e)/.10))*np.array(start.acceleration)+smooth(max(0,e)/.10)*a
    f=FirePose(); power=float(np.linalg.norm(a))
    if e>=MOVE:
        head=HEADING; a=np.zeros(3);power=0.
        if age<SHOT:f=FirePose('charge',charge=smooth((e-MOVE)/CHARGE))
        elif age<SHOT+FIRE:
            b=age-SHOT; recoil=.13*math.sin(math.pi*min(1,b/.12));f=FirePose('fire',recoil=recoil,age=b);pos=pos+np.array([recoil*SCALE,0,0])
        elif age<SHOT+FIRE+AFTER:f=FirePose('afterglow',age=age-SHOT)
    return VolleyUnit(i,tuple(map(float,pos)),head,power,tuple(map(float,a)),True,f)

def phase(age):
    if age<FORMATION:return prior_phase(age)
    if age<FORMATION+MOVE:return 'formation'
    if age<SHOT:return 'charge'
    if age<SHOT+FIRE:return 'volley'
    if age<END:return 'afterglow'
    return 'off'
def sample(age):
    if not math.isfinite(age):raise ValueError('invalid age')
    if age<FORMATION:return prior(age)
    if age>=END:return ()
    return tuple(unit(i,age) for i in range(6))
def shot_matrix(i):return unit(i,SHOT).transform()
class SpecialVolley(SpecialHighSpeed):
    def trigger(self,t,context=None):
        if not math.isfinite(t):raise ValueError('invalid time')
        if self.start is not None and 0<=t-self.start<END:return False
        self.start=self.last=t;self.context=context;return True
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=END:self.reset();return ()
        self.last=t;return sample(t-self.start)
