"""Queued click-to-fire, independent frozen shots. No OS input hooks."""
import math
from collections import deque
from dataclasses import dataclass
from combat_trial95 import Combat as Previous, charge, beam, MUZZLE, FORWARD_POINT
from fire_trial89 import FirePose, smooth, FIRE, AFTER
from combat_trial91 import CHARGE, RECOVER
FOLLOWUP=.20
MAX_QUEUE=4
MAX_SHOTS=4
@dataclass
class Request:
    down:float
    up:float|None=None
    start:float|None=None
    duration:float=CHARGE
@dataclass(frozen=True)
class Shot:
    id:int
    time:float
    anchor:tuple
    depth:tuple|None
    length:float
    def pose(self,t):
        a=max(0.,t-self.time)
        return FirePose('fire' if a<FIRE else 'afterglow',age=a)
class RepeatFire:
    def __init__(self):self.reset()
    def reset(self):
        self.queue=deque();self.held=None;self.last=None;self.fired=None;self.serial=0;self.context=None
    cancel=reset
    def valid(self,t):return math.isfinite(t) and (self.last is None or t>=self.last)
    def down(self,t):
        if not self.valid(t) or self.held is not None or len(self.queue)>=MAX_QUEUE:return False
        r=Request(t);self.queue.append(r);self.held=r;self.last=t;return True
    def up(self,t):
        if not self.valid(t) or self.held is None:return False
        self.held.up=t;self.held=None;self.last=t;return True
    def update(self,t,enabled=True,context=None):
        if not enabled or not self.valid(t) or (self.last is not None and t-self.last>.25) or (self.context is not None and context!=self.context):
            self.reset();return FirePose()
        self.last=t;self.context=context
        age=math.inf if self.fired is None else t-self.fired[1]
        if age<FIRE:
            return FirePose('fire',recoil=.13*math.sin(math.pi*min(1.,age/.12)),age=age)
        if self.queue:
            r=self.queue[0]
            if r.start is None:
                r.duration=FOLLOWUP if age<FIRE+AFTER+RECOVER else CHARGE
                r.start=max(r.down,self.fired[1]+FIRE) if self.fired is not None else r.down
                if r.duration==CHARGE:r.start=max(r.down,t-.25)
            if r.up is not None and t>=max(r.up,r.start+r.duration)-1e-9:
                self.queue.popleft();self.serial+=1;self.fired=(self.serial,t)
                return FirePose('fire')
            return FirePose('charge',charge=smooth((t-r.start)/r.duration))
        if age<FIRE+AFTER:return FirePose('afterglow',age=age)
        if age<FIRE+AFTER+RECOVER:return FirePose('recover',age=age)
        return FirePose()
class Combat(Previous):
    def __init__(self):
        super().__init__();self.fire=RepeatFire();self.shots=[];self.captured=0
    def reset(self):
        super().reset();self.shots=[];self.captured=0
    def update(self,t,xy,enabled=True,context=None,fixed=False):
        p=super().update(t,xy,enabled,context,fixed)
        self.shots=[s for s in self.shots if 0<=t-s.time<FIRE+AFTER]
        return p
    def projected(self,t,xy,p,nozzles,muzzle,direction,enabled=True,context=None,fixed=False,*,depth_origin=None,depth_per_pixel=None,channel_pixels=None):
        if not enabled or self.last!=(t,tuple(xy),(context,bool(fixed))):return ()
        self.trail.update(t,xy,p.flight,nozzles,enabled,context,fixed)
        fired=self.fire.fired
        if fired and fired[0]>self.captured:
            self.captured=fired[0]
            if t==fired[1] and all(math.isfinite(v) for v in (*muzzle,*direction)):
                n=math.hypot(*direction)
                if n>1e-6:
                    depth=(float(depth_origin),float(depth_per_pixel)) if depth_origin is not None and depth_per_pixel is not None and all(math.isfinite(v) for v in (depth_origin,depth_per_pixel)) else None
                    length=max(0.,float(channel_pixels)) if channel_pixels is not None and math.isfinite(channel_pixels) else 0.
                    self.shots.append(Shot(fired[0],t,(tuple(muzzle),tuple(v/n for v in direction)),depth,length));self.shots=self.shots[-MAX_SHOTS:]
        return tuple(self.shots)
def draw_shots(im,t,shots,scale=1.,kind='HiNu',*,depth=None):
    for s in shots:
        if 0<=t-s.time<FIRE+AFTER:
            im=beam(im,s.pose(t),s.anchor,scale,kind,depth=depth,shot_depth=s.depth,channel_pixels=s.length)
    return im
