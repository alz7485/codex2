"""Host-independent mode switch; Trial158 geometry and choreography unchanged.
The host supplies monotonic seconds, cursor position, and a rising-edge special request.
No OS input hooks, cursor hiding, or renderer ownership here.
"""
from dataclasses import dataclass
import math
import numpy as np
from fleet153 import Fleet, Settings, FleetFrame
from special158 import SpecialPolyhedron
from motion149 import DURATION

@dataclass(frozen=True)
class RuntimeFrame:
    mode: str
    normal: FleetFrame | None = None
    special: tuple = ()
    field: object = None

class Runtime:
    def __init__(self):
        self.fleet=Fleet(); self.effect=SpecialPolyhedron(); self.reset()
    def reset(self):
        self.fleet.reset(); self.effect.reset(); self.last=None
        self.request=False; self.block=False
    def update(self,t,position,pressed=False,*,special_requested=False, special_center=None,
               size=82.,visible=True,context=None,settings=Settings(),deploy_time=DURATION):
        try:
            t=float(t); p=np.asarray(position,float); size=float(size); dep=float(deploy_time)
            center=p if special_center is None else np.asarray(special_center,float)
            if (not math.isfinite(t) or not math.isfinite(dep) or not 1<=size<=1024 or
                p.shape!=(2,) or center.shape!=(2,) or not np.isfinite(p).all() or not np.isfinite(center).all() or not isinstance(settings,Settings)):
                raise ValueError('invalid runtime input')
        except (TypeError,ValueError,OverflowError):
            self.reset();raise
        pressed=bool(pressed); req=bool(special_requested); edge=req and not self.request
        broken=self.last is not None and (t<self.last[0] or t-self.last[0]>.25 or size!=self.last[1] or context!=self.last[2])
        if broken or not visible:
            self.fleet.reset();self.effect.reset();self.block=pressed;edge=False
        self.request=req; self.last=(t,size,context) if visible else None
        if not visible:return RuntimeFrame('hidden')
        if edge and not self.effect.active:
            self.fleet.reset(); self.block=pressed; self.effect.trigger(t,center,size,context)
        if self.effect.active:
            units=self.effect.update(t,context=context)
            if self.effect.active:
                self.block=pressed
                return RuntimeFrame('special',special=units,field=self.effect.field)
            # No stale normal beam, idle or escort history on return. Ignore held input until release.
            self.fleet.reset(); self.block=pressed
        if self.block:
            if not pressed:self.block=False
            effective=False
        else:effective=pressed
        f=self.fleet.update(t,p,effective,size,True,context,settings,dep)
        return RuntimeFrame('normal',normal=f)
