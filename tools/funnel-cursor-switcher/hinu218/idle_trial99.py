"""Idle visual rotation, separate from mouse hotspot and combat state."""
import math
from dataclasses import dataclass
from .flight_trial87 import wrap, pose_matrix
from .fire_trial89 import smooth
@dataclass(frozen=True)
class IdleVisual:
    roll:float=0.0
    tilt:float=0.0
    mix:float=0.0
    power:float=0.0
class IdleMotion:
    def __init__(self,delay=.9,period=3.8,return_time=.24):
        if not all(math.isfinite(v) for v in (delay,period,return_time)) or not .1<=delay<=8 or not .8<=period<=8 or not .1<=return_time<=.5:raise ValueError('invalid idle timing')
        self.delay,self.period,self.return_time=delay,period,return_time;self.reset()
    def reset(self):
        self.last=None;self.still=None;self.spin=0.;self.mix=0.;self.phase=0.;self.exit=None;self.active=False;self.result=IdleVisual()
    def update(self,t,xy,*,busy=False,visible=True,enabled=True,context=None):
        xy=tuple(xy)
        if len(xy)!=2 or not all(math.isfinite(v) for v in (t,*xy)):self.reset();raise ValueError('invalid input')
        old=self.last;key=(t,xy,context,bool(busy),bool(visible),bool(enabled))
        if not visible:self.reset();return self.result
        if key==old:return self.result
        if old and (t<old[0] or t-old[0]>.25 or math.dist(xy,old[1])>500 or context!=old[2] or (t==old[0] and xy!=old[1])):self.reset();old=None
        dt=t-old[0] if old else 0.;self.last=key
        stationary=old is None or xy==old[1]
        if busy or not enabled or not stationary:self.still=None
        elif self.still is None:self.still=t
        want=self.still is not None and t-self.still>=self.delay
        if want:
            if not self.active:self.active=True;self.exit=None;self.phase=0.;self.spin=0.
            self.phase+=dt
            ramp=min(self.phase/.45,1.);angle_time=.45*(ramp**3-.5*ramp**4)+max(0.,self.phase-.45)
            self.spin=wrap(math.tau*angle_time/self.period);self.mix=smooth(self.phase/.45)
        else:
            if self.active:self.exit=(t,self.spin,self.mix);self.active=False
            if self.exit is not None:
                start,angle,mix=self.exit;q=smooth((t-start)/self.return_time);self.spin=angle*(1-q);self.mix=mix*(1-q)
                if q>=1:self.exit=None;self.spin=self.mix=self.phase=0.
            else:self.spin=self.mix=self.phase=0.
        pulse=self.mix*(.025+.035*max(0.,math.sin(self.phase*math.tau/1.4))) if not busy else 0.
        self.result=IdleVisual(self.spin,0.,self.mix,pulse);return self.result
    def escort(self,index):
        if type(index) is not int or not 0<=index<3:raise ValueError('invalid escort index')
        q=self.phase*math.tau/(2.9,3.7,4.6)[index]+index*2.1
        return IdleVisual(self.mix*math.radians(12)*math.sin(q),self.mix*math.radians(7)*math.sin(q*.7+.6),self.mix,self.mix*(.018+.032*max(0.,math.sin(q*2.1))))
def visual_matrix(pose,visual,right,up,toward,pivot,screen_offset=(0,0),units_per_px=1.):
    from trimesh.transformations import rotation_matrix
    m=pose_matrix(pose,right,up,toward,pivot,screen_offset,units_per_px)
    return m@rotation_matrix(visual.tilt,(1,0,0),point=pivot)@rotation_matrix(visual.roll,(0,0,1),point=pivot)
def visual_power(pose,visual):return max(pose.power,visual.power)
