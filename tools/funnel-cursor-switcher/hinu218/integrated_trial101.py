"""Parallel escort aiming, independent of position and flight simulation."""
from dataclasses import replace
from .integrated_trial100 import FleetCombat as Previous, draw_escort_shots, draw_shots, charge, MUZZLE, FORWARD_POINT
from .flight_trial87 import wrap
from .fire_trial89 import smooth
RETURN_TIME=.24
class FleetCombat(Previous):
    def __init__(self,*args,**kwargs):
        self._clear_aim();super().__init__(*args,**kwargs)
    def _clear_aim(self):
        self.aim_locked=False;self.aim_target=None;self.aim_release=None;self.aim_time=None
    def reset(self):
        super().reset();self._clear_aim()
    def set_count(self,count):
        old=self.fleet.count;super().set_count(count)
        if old!=count:self._clear_aim()
    def set_size_percent(self,value):
        old=self.fleet.size_percent;super().set_size_percent(value)
        if old!=value:self._clear_aim()
    def set_escort_fire_enabled(self,value):
        old=self.escort_fire_enabled;super().set_escort_fire_enabled(value)
        if old!=value:self._clear_aim()
    def update(self,t,xy,enabled=True,context=None,fixed=False):
        p=super().update(t,xy,enabled,context,fixed)
        if not enabled or not self.escort_fire_enabled or not self.fleet.count:
            self._clear_aim();return p
        self.aim_time=t
        busy=p.fire.stage in ('charge','fire') or any(self.escort_fire.pending) or any(x.stage in ('charge','fire') for x in self.escort_fire.poses[:self.fleet.count])
        if busy:
            self.aim_locked=True;self.aim_target=(p.flight.heading,p.flight.pitch);self.aim_release=None
        elif self.aim_locked:
            self.aim_locked=False;self.aim_release=t
        elif self.aim_release is not None and t-self.aim_release>=RETURN_TIME:
            self.aim_release=None;self.aim_target=None
        return p
    def update_fleet(self,t,xy,scale=1.,bounds=None,visible=True,context=None):
        old=self.fleet.last;members=super().update_fleet(t,xy,scale,bounds,visible,context)
        new=self.fleet.last
        if not visible or (old and new and old[2:]!=new[2:]):self._clear_aim()
        return members
    def _aim_mix(self):
        if self.aim_locked:return 1.
        if self.aim_release is not None:return 1.-smooth((self.aim_time-self.aim_release)/RETURN_TIME)
        return 0.
    def escort_render_pose(self,member):
        p=member.pose;q=self._aim_mix()
        if not q or self.aim_target is None:return p
        heading,pitch=self.aim_target
        return replace(p,heading=wrap(p.heading+q*wrap(heading-p.heading)),pitch=p.pitch+q*(pitch-p.pitch))
    def escort_visual(self,member):
        v=super().escort_visual(member)
        # Preserve longitudinal roll, which does not affect the firing axis.
        return replace(v,tilt=v.tilt*(1.-self._aim_mix()))
