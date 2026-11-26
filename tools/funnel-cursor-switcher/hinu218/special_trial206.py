"""Hi-Nu symmetric staggered opening only; all later action and HWS delegate to 205."""
from .special_trial205 import *
from . import special_trial205 as previous
from .special_trial106 import RadialWingUnit, HOLD, FLIGHT, DISTANCE
from .special_trial104 import RACK
from .special_trial119 import UnitView
from .thrust_trial86 import clamp, smooth
from functools import lru_cache
PAIR_IDS=((2,5),(1,4),(0,3))
PAIR_DELAY=.15
DELAYS={i:k*PAIR_DELAY for k,pair in enumerate(PAIR_IDS) for i in pair}
LAUNCH_END=HOLD+FLIGHT+2*PAIR_DELAY

def launch_age(i,t):return t-DELAYS[i]

@lru_cache(maxsize=1024)
def sample(t,kind='HiNu',aspect=1.):
    if kind!='HiNu' or t>=REENTRY:return previous.sample(t,kind,aspect)
    if not math.isfinite(t) or not math.isfinite(aspect) or aspect<=0:raise ValueError('invalid time/aspect')
    if t<0 or t>=LAUNCH_END:return ()
    units=[]
    for i,(s,k,x,y,tilt) in enumerate(RACK):
        local=launch_age(i,t)
        if local>=HOLD+FLIGHT:continue
        q=clamp((local-HOLD)/FLIGHT)
        power=smooth((local-HOLD+.065)/.10) if local>=HOLD-.065 else 0.
        u=RadialWingUnit(i,s,x,y,0.,tilt,power)
        d=u.heading()*DISTANCE*q*q
        units.append(UnitView(RadialWingUnit(i,s,x+d[0],y+d[1],0.,tilt,power),local))
    return tuple(units)

def phase(t,kind='HiNu'):
    if kind!='HiNu' or t>=REENTRY:return previous.phase(t,kind)
    if t<0:return 'off'
    if t<HOLD:return 'rack'
    return 'pair launch' if t<LAUNCH_END else 'gap'

class SpecialVolley(previous.SpecialVolley):
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=self.end:self.reset();return ()
        self.last=t;return sample(t-self.start,self.kind,self.aspect)
