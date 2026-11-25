"""Trial115: visual braking/stabilization pulses and stationary turn jets.
Positions, rotations, attack state and timing are exactly Trial114. No new thrust
axis is invented: braking is scripted; the lateral pair is stabilization only.
"""
from dataclasses import dataclass
import math
import numpy as np
import special_trial114 as old
from special_trial114 import (END, FORMATION, REENTRY, SHOT, MOVE, HOLD, CAMERA_Z, SCALE, ARRIVALS, BRAKE, STOP_HOLD, TURN, TARGETS, AIM, RADIUS, phase, shot_matrix, flight_unit)
from special_trial111 import Unit
from scipy.spatial.transform import Rotation

PRE=.035
TAIL=.035

def pulse(e,d):
    x=e-d
    if x < -BRAKE-PRE or x >= TAIL:return 0.
    if x < -BRAKE:return .85*old.smooth((x+BRAKE+PRE)/PRE)
    if x < 0:return .85+.15*old.smooth((x+BRAKE)/BRAKE)
    return 1-old.smooth(x/TAIL)

def turn_power(i,e):
    d=ARRIVALS[i]; q=(e-d-STOP_HOLD)/TURN
    if not 0<q<1:return (0.,0.)
    r0=old.basis(old.direction(i,len(old.ROUTES[i][0])-2),i)
    r1=old.basis(AIM,i)
    local=Rotation.from_matrix(r0.T@r1).as_rotvec()
    # A lateral exhaust at positive local Z supplies a reaction torque about X.
    # Other axes cannot be represented by this nozzle layout: do not fake a nozzle.
    power=.82*math.sin(math.pi*q)**.65
    x=float(local[0])/max(1e-12,float(np.linalg.norm(local)))
    return (power*(.18+.82*max(0.,-x)),power*(.18+.82*max(0.,x)))

@dataclass(frozen=True)
class FxUnit(Unit):
    side_minus:float=0.
    side_plus:float=0.
    def thrusters(self):
        out=[]
        for port,o,v,p in super().thrusters():
            if port.group=='side_minus':p=max(p,self.side_minus)
            if port.group=='side_plus':p=max(p,self.side_plus)
            out.append((port,o,v,float(p)))
        return tuple(out)

def sample(t):
    units=old.sample(t)
    if not FORMATION<=t<FORMATION+MOVE:return units
    result=[]
    for u in units:
        e=t-FORMATION; d=ARRIVALS[u.id]; b=pulse(e,d); m,p=turn_power(u.id,e)
        m=max(b,m);p=max(b,p)
        # preserve existing acceleration; independent visual pulses must remain visible
        # even when scripted speed is exactly zero.
        result.append(FxUnit(u.id,u.position,u.rotation,max(u.power,m,p),u.acceleration,u.visible,u.fire,m,p))
    return tuple(result)

class SpecialVolley(old.SpecialVolley):
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=END:self.reset();return ()
        self.last=t;return sample(t-self.start)

def trail_gain(i,t,history_t):
    """Rapidly retire travel streaks after arrival; keep local turning plumes separate."""
    stop=FORMATION+ARRIVALS[i]
    if t<stop:return 1.
    if history_t>=stop:return 0.
    return max(0.,1-(t-stop)/.065)**2
