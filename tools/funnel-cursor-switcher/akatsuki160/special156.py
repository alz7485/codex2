"""Seven-node defensive field, preserving Trial155 motion."""
from dataclasses import dataclass, replace
import math
import numpy as np
import special155 as prev
from motion149 import tip,smooth
CENTER=prev.CENTER; SIZE=prev.SIZE
IGNITE=prev.READY+.10; LINK=.36; FILL=.36; FULL=IGNITE+LINK+FILL; RELEASE=FULL+1.02; END=RELEASE+.34
ORDER=tuple(sorted(range(7),key=lambda i:prev.ANGLES[i]))
@dataclass(frozen=True)
class Field:
    t:float
    ids:tuple
    nodes:np.ndarray
    apex:np.ndarray
    edge_progress:tuple
    face_progress:tuple
    opacity:float
    pulses:tuple
    scale:float

def sample_indexed(t,center=CENTER,size=SIZE):
    t,center,size=prev.launch.validate(t,center,size)
    if t<prev.END:return prev.sample_indexed(t,center,size)
    if t>=END:return ()
    return tuple((i,replace(f,t=t)) for i,f in prev.sample_indexed(prev.READY,center,size))

def sample_field(t,center=CENTER,size=SIZE,units=None):
    t,center,size=prev.launch.validate(t,center,size)
    if not IGNITE<t<END:return None
    if units is None:units=sample_indexed(t,center,size)
    frames=dict(units)
    if set(frames)!=set(ORDER):return None
    nodes=np.array([frames[i].world(tip(frames[i].deploy_time)) for i in ORDER])
    k=size/SIZE
    apex=np.array([center[0],-center[1],nodes[:,2].mean()+85*k])
    q=t-IGNITE
    edge=tuple(smooth((q-i*.035)/.15) for i in range(7))
    face=tuple(min(edge[i],smooth((q-LINK-i*.032)/.16)) for i in range(7))
    alpha=1-smooth((t-RELEASE)/(END-RELEASE))
    pulse=tuple(((q*1.75-i/7)%1) if edge[i]>=1 else edge[i] for i in range(7))
    return Field(t,ORDER,nodes,apex,edge,face,alpha,pulse,k)

class SpecialBarrier(prev.SpecialReturn):
    def reset(self):
        super().reset();self.field=None
    def update(self,t,visible=True,context=None):
        if not self.active:return ()
        t=float(t)
        if not visible or context!=self.context or not math.isfinite(t) or t<self.last or t-self.last>.25 or t-self.start>=END:
            self.reset();return ()
        self.last=t;age=t-self.start
        units=sample_indexed(age,self.center,self.size)
        self.field=sample_field(age,self.center,self.size,units)
        return units
