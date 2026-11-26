"""Trial99 plus visual-only staggered escort volleys."""
import math
from dataclasses import dataclass
from .integrated_trial99 import FleetCombat as Previous
from .combat_trial96 import Shot, MAX_SHOTS, draw_shots, MUZZLE, FORWARD_POINT, charge
from .combat_trial95 import beam
from .fire_trial89 import FirePose, FIRE, AFTER
DELAYS=(.10,.20,.30)
@dataclass(frozen=True)
class EscortShot:
    shot: Shot
    scale: float
class EscortFire:
    def __init__(self): self.reset()
    def reset(self,seen=None):
        self.seen=seen;self.pending=[[] for _ in DELAYS];self.latest=[None]*3;self.captured=[None]*3
        self.shots=[[] for _ in DELAYS];self.poses=[FirePose() for _ in DELAYS];self.t=None
    def update(self,t,primary,fired,count):
        if self.t==t:return
        self.t=t
        if fired is not None and fired!=self.seen:
            self.seen=fired
            for i in range(count):self.pending[i].append((fired[0],fired[1]+DELAYS[i]))
        for i in range(count):
            self.shots[i]=[s for s in self.shots[i] if 0<=t-s.shot.time<FIRE+AFTER]
            while self.pending[i] and self.pending[i][0][1]<=t+1e-9:
                serial,due=self.pending[i].pop(0);self.latest[i]=(serial,t)
            last=self.latest[i];age=math.inf if last is None else t-last[1]
            if age<FIRE:self.poses[i]=FirePose('fire',recoil=.13*math.sin(math.pi*min(1.,age/.12)),age=age)
            elif self.pending[i]:self.poses[i]=FirePose('charge',charge=1.)
            elif primary.stage=='charge':self.poses[i]=FirePose('charge',charge=primary.charge)
            elif age<FIRE+AFTER:self.poses[i]=FirePose('afterglow',age=age)
            else:self.poses[i]=FirePose()
    def capture(self,t,i,muzzle,direction,scale,depth_origin=None,depth_per_pixel=None,channel_pixels=0.):
        if self.t!=t or not 0<=i<3:return ()
        event=self.latest[i]
        if event and event[1]==t and self.captured[i]!=event:
            self.captured[i]=event
            if all(math.isfinite(v) for v in (*muzzle,*direction,scale,channel_pixels)) and scale>0:
                n=math.hypot(*direction)
                if n>1e-6:
                    depth=(float(depth_origin),float(depth_per_pixel)) if depth_origin is not None and depth_per_pixel is not None and all(math.isfinite(v) for v in (depth_origin,depth_per_pixel)) else None
                    shot=Shot(event[0],t,(tuple(muzzle),tuple(v/n for v in direction)),depth,max(0.,channel_pixels))
                    self.shots[i].append(EscortShot(shot,scale));self.shots[i]=self.shots[i][-MAX_SHOTS:]
        return tuple(self.shots[i])
class FleetCombat(Previous):
    def __init__(self,count=0,size_percent=100,*,idle_enabled=True,escort_fire_enabled=True):
        if type(escort_fire_enabled) is not bool:raise ValueError('escort_fire_enabled must be bool')
        self.escort_fire_enabled=escort_fire_enabled;self.escort_fire=EscortFire();super().__init__(count,size_percent,idle_enabled=idle_enabled)
    def reset(self):
        super().reset();self.escort_fire.reset()
    def set_count(self,count):
        old=self.fleet.count;super().set_count(count)
        if count!=old:self.escort_fire.reset(self.fire.fired)
    def set_size_percent(self,value):
        old=self.fleet.size_percent;super().set_size_percent(value)
        if value!=old:self.escort_fire.reset(self.fire.fired)
    def set_escort_fire_enabled(self,value):
        if type(value) is not bool:raise ValueError('escort_fire_enabled must be bool')
        if value!=self.escort_fire_enabled:self.escort_fire_enabled=value;self.escort_fire.reset(self.fire.fired)
    def update(self,t,xy,enabled=True,context=None,fixed=False):
        p=super().update(t,xy,enabled,context,fixed)
        if enabled and self.escort_fire_enabled:self.escort_fire.update(t,p.fire,self.fire.fired,self.fleet.count)
        else:self.escort_fire.reset(self.fire.fired)
        return p
    def update_fleet(self,t,xy,scale=1.,bounds=None,visible=True,context=None):
        old=self.fleet.last;members=super().update_fleet(t,xy,scale,bounds,visible,context)
        new=self.fleet.last
        if not visible or (old and new and old[2:]!=new[2:]):self.escort_fire.reset(self.fire.fired)
        return members
    def escort_fire_pose(self,member):return self.escort_fire.poses[member.id]
    def escort_projected(self,t,member,nozzles,muzzle,direction,*,scale=1.,depth_origin=None,depth_per_pixel=None,channel_pixels=0.):
        self.fleet.projected(t,member,nozzles)
        if not self.escort_fire_enabled or self.fleet.last is None or self.fleet.last[0]!=t or not 0<=member.id<len(self.fleet.result) or self.fleet.result[member.id]!=member or member.opacity<=0:return ()
        return self.escort_fire.capture(t,member.id,muzzle,direction,scale*member.ratio,depth_origin,depth_per_pixel,channel_pixels)
def draw_escort_shots(im,t,shots,kind='HiNu',*,depth=None):
    for s in shots:
        if 0<=t-s.shot.time<FIRE+AFTER:im=beam(im,s.shot.pose(t),s.shot.anchor,s.scale,kind,depth=depth,shot_depth=s.shot.depth,channel_pixels=s.shot.length)
    return im
