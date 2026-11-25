from fleet153 import Idle, idle_angle, smooth, RETURN
import math
import numpy as np

class ConfiguredIdle(Idle):
    def __init__(self, options):
        self.delay=options["delay"]
        self.period=options["turn_period"]
        self.direction=-1 if options["turn_direction"] == "逆回転" else 1
        super().__init__()

    def update(self,t,p,busy,enabled):
        if self.anchor is None or np.linalg.norm(p-self.anchor)>.75:
            self.anchor=p.copy();self.quiet=t
        if busy or not enabled:self.quiet=t
        ready=enabled and not busy and t-self.quiet>=self.delay-1e-9
        if ready:
            if self.start is None:self.start=t;self.return_t=None
            self.angle=self.direction*idle_angle(t-self.start)*3.8/self.period
        else:
            if self.start is not None:
                self.return_angle=math.atan2(math.sin(self.angle),math.cos(self.angle));self.return_t=t;self.start=None
            if self.return_t is not None:
                self.angle=self.return_angle*(1-smooth((t-self.return_t)/RETURN))
                if t-self.return_t>=RETURN:self.return_t=None;self.angle=0.
            else:self.angle=0.
        return self.angle, (t-self.start if self.start is not None else None)

