"""Hi-Nu folded wing launch: each unit flies along its own outward long axis.
No camera approach, no rotation, no barrier. Provisional folded-root exhaust.
"""
import math
import numpy as np
from .special_trial104 import WingUnit, RACK, HOLD, GAP, CAMERA_Z, SCALE, SpecialWingLaunch
from .thrust_trial86 import clamp, smooth
from .nozzle_trial104 import Port
# Trial77 individual acceleration duration .66 s; shortened by ~12%.
FLIGHT=.58; DISTANCE=26.; EXIT=HOLD+FLIGHT; END=EXIT+GAP
class RadialWingUnit(WingUnit):
    def heading(self):
        axis=self.transform()[:3,0]*self.side
        return axis/np.linalg.norm(axis)
    def thrusters(self):
        # Folded pose points along +/- local X, unlike the normal combat axis.
        # Trial85 has no measured exhaust along X. Explicit visual placeholder
        # on the opposite root cheek; not a verified fourth nozzle design.
        p=Port('folded_root_preview',(-self.side*1.06,0.,3.29),(-self.side,0.,0.),.13,True)
        m=self.transform();return ((p,(m@[*p.origin,1])[:3],m[:3,:3]@p.direction,self.power),)
def phase(age):
    if age<0 or age>=END:return 'off'
    if age<HOLD:return 'rack'
    if age<EXIT:return 'launch'
    return 'gap'
def sample(age):
    if not math.isfinite(age):raise ValueError('invalid age')
    if phase(age) in ('off','gap'):return ()
    q=clamp((age-HOLD)/FLIGHT)
    power=smooth((age-HOLD+.065)/.10) if age>=HOLD-.065 else 0.
    units=[]
    for k,(s,i,x,y,tilt) in enumerate(RACK):
        u=RadialWingUnit(k,s,x,y,0.,tilt,power);d=u.heading()*DISTANCE*q*q
        units.append(RadialWingUnit(k,s,x+d[0],y+d[1],0.,tilt,power))
    return tuple(units)
class SpecialRadialLaunch(SpecialWingLaunch):
    def trigger(self,t,context=None):
        if not math.isfinite(t):raise ValueError('invalid time')
        if self.start is not None and 0<=t-self.start<END:return False
        self.start=self.last=t;self.context=context;return True
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=END:self.reset();return ()
        self.last=t;return sample(t-self.start)
