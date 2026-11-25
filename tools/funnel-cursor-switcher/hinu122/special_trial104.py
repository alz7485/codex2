"""Replacement opening: folded wings, simultaneous forward exit. No barrier."""
from dataclasses import dataclass
import math
import numpy as np
from rig_trial61 import matrix as hinge_matrix
from special_trial102 import RackLaunch,PIVOT
from thrust_trial86 import clamp,smooth
from nozzle_trial104 import resolve
HOLD=.80;FLIGHT=.80;GAP=.40;EXIT=HOLD+FLIGHT;END=EXIT+GAP
CAMERA_Z=40.;DISTANCE=37.8;SCALE=.86
RACK=tuple((s,i,s*(2.15+2.10*i),4.5-.25*i,8+11*i) for s in (-1,1) for i in range(3))
@dataclass(frozen=True)
class WingUnit:
    id:int; side:int; x:float; y:float; z:float; tilt:float; power:float; visible:bool=True
    def transform(self):
        a=math.radians((-90+self.tilt) if self.side>0 else (90-self.tilt))
        c,s=math.cos(a),math.sin(a);m=np.eye(4);m[:3,:3]=SCALE*np.array([[c,-s,0],[s,c,0],[0,0,1]])@np.diag([1.,-1.,-1.]);m[:3,3]=np.array([self.x,self.y,self.z])-m[:3,:3]@PIVOT;return m
    def part_matrix(self,side):
        a={'Port':90,'Starboard':78,'Fixed':0} if self.side<0 else {'Port':-78,'Starboard':-90,'Fixed':0}
        return self.transform()@hinge_matrix(side,a[side])
    def thrusters(self):return resolve(self.transform(),(0,0,self.power))
def phase(age):
    if age<0 or age>=END:return 'off'
    if age<HOLD:return 'rack'
    if age<EXIT:return 'launch'
    return 'gap'
def sample(age):
    if not math.isfinite(age):raise ValueError('invalid age')
    if phase(age) in ('off','gap'):return ()
    q=clamp((age-HOLD)/FLIGHT);z=DISTANCE*q*q;power=smooth((age-HOLD+.10)/.14) if age>=HOLD-.10 else 0.
    return tuple(WingUnit(k,s,x,y,z,tilt,power) for k,(s,i,x,y,tilt) in enumerate(RACK))
class SpecialWingLaunch(RackLaunch):
    def trigger(self,t,context=None):
        if not math.isfinite(t):raise ValueError('invalid time')
        if self.start is not None and 0<=t-self.start<END:return False
        self.start=self.last=t;self.context=context;return True
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=END:self.reset();return ()
        self.last=t;return sample(t-self.start)
