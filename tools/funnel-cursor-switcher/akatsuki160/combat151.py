"""Single-unit fictional cursor combat. Time in seconds, input sampled button state.
Flight150 is unmodified. Shot coordinates are frozen in screen-world space on launch.
"""
from dataclasses import dataclass, replace
from collections import deque
import math
import numpy as np
from flight150 import Flight, PORTS, Jet, clip
from motion149 import tip, DURATION

CHARGE_TIME=.75
SHOT_TIME=.22
MAX_QUEUE=4
def beam_origin(frame): return tip(frame.deploy_time)  # provisional geometry tip
BEAM_AXIS=np.array([0.,0.,-1.])

@dataclass(frozen=True)
class Shot:
    t:float
    origin:tuple
    direction:tuple
    charge:float
    scale:float

@dataclass
class CombatFrame:
    flight:object
    charge:float
    charging:bool
    shot:Shot|None
    pending:int
    recoil:float

class Combat:
    def __init__(self):
        self.flight=Flight(); self.reset()
    def reset(self):
        self.flight.reset(); self.last=None; self.pressed=False; self.start=None
        self.queue=deque(); self.shot=None; self.block=False
    def update(self,t,position,pressed=False,size=82.,visible=True,context=None,deploy_time=DURATION):
        p=np.asarray(position,dtype=float); t=float(t); size=float(size); pressed=bool(pressed); deploy_time=float(deploy_time)
        if not math.isfinite(deploy_time) or not math.isfinite(t) or not math.isfinite(size) or not 1<=size<=1024 or p.shape!=(2,) or not np.isfinite(p).all():
            self.reset(); raise ValueError('invalid combat input')
        discontinuity=(self.last is not None and (t<self.last[0] or (t==self.last[0] and not np.array_equal(p,self.last[1])) or t-self.last[0]>.25 or size!=self.last[2] or context!=self.last[3] or np.linalg.norm(p-self.last[1])>240))
        if not visible or discontinuity:
            self.reset(); self.block=pressed
        f=self.flight.update(t,p,size,visible,context,deploy_time)
        if not visible:return CombatFrame(f,0.,False,None,0,0.)
        self.last=(t,p.copy(),size,context)
        if self.block:
            if not pressed:self.block=False
        elif pressed and not self.pressed:
            self.start=t
        elif not pressed and self.pressed and self.start is not None:
            if len(self.queue)<MAX_QUEUE:self.queue.append(clip((t-self.start)/CHARGE_TIME))
            self.start=None
        self.pressed=pressed
        if self.shot is not None and t-self.shot.t>=SHOT_TIME:self.shot=None
        if self.shot is None and self.queue:
            q=self.queue.popleft()
            self.shot=Shot(t,tuple(f.world(beam_origin(f))),tuple(f.matrix@BEAM_AXIS),q,f.scale)
        charge=clip((t-self.start)/CHARGE_TIME) if self.start is not None else 0.
        # Smooth damped visual reaction around the forward axis. Tip and beam axis remain fixed.
        recoil=0.
        if self.shot is not None:
            age=t-self.shot.t
            u=clip(age/.085)
            recoil=(.065+.135*self.shot.charge)*math.sin(math.pi*u)**2*math.exp(-1.1*u) if age<.085 else 0.
        if recoil:
            c,s=math.cos(recoil),math.sin(recoil)
            R=f.matrix@np.array([[c,-s,0],[s,c,0],[0,0,1.]])
            anchor=beam_origin(f)
            trans=f.world(anchor)-f.scale*(R@anchor)
            jets=tuple(Jet(j.name,trans+f.scale*(R@PORTS[j.name][0]),R@PORTS[j.name][1],j.power,j.width) for j in f.jets)
            f=replace(f,matrix=R,translation=trans,jets=jets)
        return CombatFrame(f,charge,self.start is not None,self.shot,len(self.queue),recoil)
