from .idle_trial192 import IdleMotion,TURN,RAMP,RETURN,HEADING
from .idle_trial99 import IdleVisual
from .flight_trial87 import wrap
from .fire_trial89 import smooth
import math

class ConfiguredIdle(IdleMotion):
    def __init__(self,options):
        self.delay=options['delay']
        self.period=options['turn_period']*(-1 if options['turn_direction']=='逆回転' else 1)
        super().__init__()
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
            age=-1. if self.still is None else t-self.still-self.delay
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
                self.phase=math.tau/self.period*(RAMP*(r**3-.5*r**4)+max(0.,self.clock-RAMP));self.mix=smooth(r)
                self.mode='turning' if age<TURN else 'rotating'
            else:
                self.entry=None;self.heading=heading;self.phase=self.mix=self.clock=0.;self.mode='normal'
            self.result=IdleVisual(wrap(self.phase),0.,self.mix,self.mix*(.025+.035*max(0.,math.sin(self.clock*math.tau/1.4))))
            return self.heading,self.result
