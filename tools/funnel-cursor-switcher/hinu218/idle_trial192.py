"""Time-based Hi-Nu idle presentation; only the visual pose changes."""
import math
from dataclasses import replace
from .idle_trial99 import IdleVisual, visual_matrix, visual_power
from .flight_trial87 import wrap
from .fire_trial89 import smooth
from .fleet_trial191 import FleetCombat as Previous, draw_shots, draw_escort_shots, charge, MUZZLE, FORWARD_POINT

TURN=.65
RAMP=.45
RETURN=.24
DELAY=.9
PERIOD=3.8
HEADING=math.radians(-128)

class IdleMotion:
    def __init__(self): self.reset()
    def reset(self):
        self.last=None;self.anchor=None;self.still=None;self.entry=None;self.exit=None
        self.heading=None;self.phase=0.;self.mix=0.;self.clock=0.;self.mode='normal';self.result=IdleVisual()
    def update(self,*args,**kwargs):
        # The inherited update must not apply legacy roll before the combat lock.
        return IdleVisual()
    def advance(self,t,xy,heading,*,enabled,busy,visible,context,fixed):
        xy=tuple(xy);key=(t,xy,heading,enabled,busy,visible,context,fixed)
        if key==self.last:return self.heading,self.result
        old=self.last
        if not visible or busy:
            self.reset();return heading,self.result
        if old and (t<old[0] or t-old[0]>.25 or math.dist(xy,old[1])>500 or context!=old[6] or fixed!=old[7] or (t==old[0] and xy!=old[1])):self.reset()
        self.last=key
        moved=self.anchor is None or math.dist(xy,self.anchor)>.75
        if moved or not enabled:
            self.anchor=xy;self.still=t if enabled else None
        elif self.still is None:self.still=t
        if (moved or not enabled) and self.entry is not None and self.exit is None:
            self.exit=(t,self.heading,wrap(self.phase),self.mix)
        age=-1. if self.still is None else t-self.still-DELAY
        if self.exit is not None:
            start,h,roll,mix=self.exit;u=smooth((t-start)/RETURN)
            self.heading=wrap(h+wrap(heading-h)*u);self.phase=roll*(1-u);self.mix=mix*(1-u);self.mode='recovering'
            if u>=1-1e-10:
                self.entry=self.exit=None;self.heading=heading;self.phase=self.mix=self.clock=0.;self.mode='normal'
        elif enabled and age>=-1e-10:
            if self.entry is None:self.entry=(t,heading)
            start,h=self.entry;age=max(0.,t-start)
            target=heading if fixed else HEADING
            self.heading=wrap(h+wrap(target-h)*smooth(age/TURN))
            self.clock=max(0.,age-TURN);r=min(self.clock/RAMP,1.)
            self.phase=math.tau/PERIOD*(RAMP*(r**3-.5*r**4)+max(0.,self.clock-RAMP));self.mix=smooth(r)
            self.mode='turning' if age<TURN else 'rotating'
        else:
            self.entry=None;self.heading=heading;self.phase=self.mix=self.clock=0.;self.mode='normal'
        self.result=IdleVisual(wrap(self.phase),0.,self.mix,self.mix*(.025+.035*max(0.,math.sin(self.clock*math.tau/1.4))))
        return self.heading,self.result
    def escort(self,index):
        if type(index) is not int or not 0<=index<3:raise ValueError('invalid escort index')
        q=self.clock*math.tau/(2.9,3.7,4.6)[index]+index*2.1
        return IdleVisual(self.mix*math.radians(12)*math.sin(q),self.mix*math.radians(7)*math.sin(q*.7+.6),self.mix,self.mix*(.018+.032*max(0.,math.sin(q*2.1))))

class FleetCombat(Previous):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.idle_motion=IdleMotion()
    def update(self,t,xy,enabled=True,context=None,fixed=False):
        p=super().update(t,xy,enabled,context,fixed)
        busy=(p.fire.stage!='idle' or bool(self.fire.queue) or bool(self.shots) or self.lock is not None or any(self.escort_fire.pending))
        heading,self.primary_visual=self.idle_motion.advance(t,xy,p.flight.heading,enabled=self.idle_enabled,busy=busy,visible=enabled,context=context,fixed=bool(fixed))
        return replace(p,flight=replace(p.flight,heading=heading)) if heading!=p.flight.heading else p
