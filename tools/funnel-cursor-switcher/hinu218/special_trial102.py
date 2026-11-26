"""Hi-Nu family special opening: six straight rack units, sequential vertical launch.
World coordinates: +Y upward, +Z toward viewer. Model coordinates unchanged.
Pure timeline, separate from regular cursor flight. No Windows hooks.
"""
from dataclasses import dataclass
import math
import numpy as np
from .rig_trial61 import matrix as hinge_matrix
from .thrust_trial86 import smooth, clamp
# right to left; three per wing. Provisional layout, not measured from artwork.
RACK=((6.9,0.,-5.),(4.1,-.7,-5.),(1.4,-1.4,-5.),(-1.4,-1.4,5.),(-4.1,-.7,5.),(-6.9,0.,5.))
PIVOT=np.array([0.,0.,3.35]); BASIS=np.array([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
FIRST=.36; INTERVAL=.14; IGNITION=.075; FLIGHT=.85; DISTANCE=29.; END=FIRST+5*INTERVAL+IGNITION+FLIGHT+.22
@dataclass(frozen=True)
class RackUnit:
    id:int; x:float; y:float; tilt:float; power:float; progress:float; visible:bool
    def transform(self):
        a=math.radians(self.tilt); c,s=math.cos(a),math.sin(a)
        m=np.eye(4);m[:3,:3]=np.array([[c,-s,0.],[s,c,0.],[0.,0.,1.]])@BASIS
        m[:3,3]=np.array([self.x,self.y,0.])-m[:3,:3]@PIVOT
        return m
    def part_matrix(self,side):return self.transform()@hinge_matrix(side,90 if side=='Port' else -90)

def sample(age):
    if not math.isfinite(age):raise ValueError('invalid age')
    if age<0 or age>=END:return ()
    units=[]
    for i,(x,y,tilt) in enumerate(RACK):
        e=age-FIRST-i*INTERVAL
        q=clamp((e-IGNITION)/FLIGHT)
        power=smooth(e/IGNITION) if q<1 else 0.
        units.append(RackUnit(i,x,y+DISTANCE*q*q,tilt,power,q,q<1))
    return tuple(units)

class RackLaunch:
    def __init__(self):self.reset()
    def reset(self):self.start=None;self.context=None;self.last=None
    def trigger(self,t,context=None):
        if not math.isfinite(t):raise ValueError('invalid time')
        if self.start is not None and 0<=t-self.start<END:return False
        self.start=self.last=t;self.context=context;return True
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=END:self.reset();return ()
        self.last=t;return sample(t-self.start)
