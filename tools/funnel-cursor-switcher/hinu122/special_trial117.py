"""Post-volley hold, staggered stationary turns, and high-speed 3D departures.
Earlier choreography unchanged. No OS hooks; completion explicitly signals host restore.
"""
import math
import numpy as np
from dataclasses import replace
import special_trial115 as old
from composition_trial116 import camera_pose, material_emission, FINAL
from special_trial115 import FORMATION, REENTRY, SHOT, MOVE, HOLD, CAMERA_Z, SCALE, AIM, RADIUS, shot_matrix, flight_unit, trail_gain as old_trail_gain
from special_trial113 import basis,blend,make,norm
from fire_trial89 import FirePose,FIRE,AFTER
from thrust_trial86 import smooth,clamp
BASE_END=old.END
# Depart after the beam is gone and the previous still hold has elapsed.
ORDER=(3,2,1,4,0,5)
DELAY={i:k*.075 for k,i in enumerate(ORDER)}
TURN=.14; ACCEL=.10; TRAVEL=.43; FINAL_GAP=.12
# Real world radial outward directions, with diverse depth components.
DEPTH=(-.34,-.65,.18,-.32,-.18,.28)
DIRS=[]; LENGTHS=[]
for i,p in enumerate(old.TARGETS):
    xy=norm(p[:2]-np.array([FINAL.x,FINAL.y])); d=norm(np.r_[xy,DEPTH[i]])
    # move far enough to exit the frustum even for the receding machines
    focal=math.tan(math.radians(FINAL.fov/2))
    length=next(s for s in np.arange(4.,180.,.25) if max(abs((p+s*d)[:2]-[FINAL.x,FINAL.y])) > (FINAL.z-(p+s*d)[2])*focal+2*RADIUS and FINAL.z-(p+s*d)[2]>RADIUS+.35)
    DIRS.append(d);LENGTHS.append(float(length))
DIRS=np.array(DIRS); LENGTHS=np.array(LENGTHS)
END=BASE_END+max(DELAY.values())+TURN+TRAVEL+FINAL_GAP

def residual(t):
    # Retain existing flash, then add weak intermittent discharge until beam fade ends.
    a=t-SHOT
    return .24*(1-smooth((a-.145)/(.4-.145))) if .145<=a<.4 else 0.

def depart(i,t):
    e=t-BASE_END-DELAY[i]; p=old.TARGETS[i]; d=DIRS[i]; r0=basis(AIM,i); r1=basis(d,i)
    if e<=0:return make(i,p,r0,np.zeros(3))
    if e<TURN:
        q=e/TURN;r=blend(r0,r1,smooth(q));a=r[:,1]*(.65*math.sin(math.pi*q));return make(i,p,r,a)
    e-=TURN
    if e>=TRAVEL:return make(i,p+d*LENGTHS[i],r1,np.zeros(3),visible=False)
    # Integrate ramp to constant cruise speed, then continue straight out of frame.
    v=LENGTHS[i]/(TRAVEL-ACCEL/2); u=min(e,ACCEL); distance=v*(u*u/(2*ACCEL)+max(0.,e-ACCEL))
    return make(i,p+d*distance,r1,d*(.72+.28*(1-smooth(e/ACCEL))))

def sample(t):
    if not math.isfinite(t):raise ValueError('invalid time')
    if t<BASE_END:return old.sample(t)
    if t>=END:return ()
    return tuple(depart(i,t) for i in range(6))

def phase(t):
    if t<BASE_END:return old.phase(t)
    if t<END-FINAL_GAP:return 'breakaway'
    return 'restore' if t<END else 'off'

def trail_gain(i,t,history_t):
    if t<BASE_END:return old_trail_gain(i,t,history_t)
    begin=BASE_END+DELAY[i]+TURN
    return 1. if history_t>=begin else 0.

class SpecialVolley(old.SpecialVolley):
    def trigger(self,t,context=None):
        if not math.isfinite(t):raise ValueError('invalid time')
        if self.start is not None and 0<=t-self.start<END:return False
        self.start=self.last=t;self.context=context;return True
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=END:self.reset();return ()
        self.last=t;return sample(t-self.start)
    @property
    def active(self):return self.start is not None
