"""HWS independent sequential attacks; HiNu delegates unchanged to Trial119.
Fast pre-aimed raid; all eight passes track one distant upper-left target throughout entry and exit.
All positions are world-space, seconds. Preview composition uses a square viewport;
pass actual viewport aspect to the HWS controller for proper offscreen endpoints.
"""
import math
import numpy as np
from .special_trial119 import sample as old_sample, phase as old_phase, SpecialVolley as OldVolley, END as HI_END, REENTRY, shot_matrix as old_shot_matrix
from .special_trial111 import Unit, basis, blend, norm, RADIUS, SCALE
from .composition_trial116 import camera_pose as old_camera, CameraPose
from .fire_trial89 import FirePose, FIRE, AFTER
from .thrust_trial86 import smooth, clamp
from .nozzle_trial119 import normal_ports
from dataclasses import dataclass
# start, entry edge, attack xy, depth, exit edge, legacy aim (unused)
TARGET=(-420.,330.,-180.)
WAVES=(
 (0.00,(-1.5,.66),(-.57,.43), 6.,(.35,1.5),(.86,-.37,-.34)),
 (.11,(.35,-1.5),(.46,-.38),-8.,(1.5,.20),(-.83,.48,-.39)),
 (.48,(1.5,.68),(.65,.58),-16.,(-.15,1.5),(-.78,-.52,-.35)),
 (.70,(-.72,-1.5),(-.35,-.56),10.,(-1.5,-.10),(.82,.48,-.31)),
 (.78,(-1.5,-.12),(-.65,.05),-3.,(.30,-1.5),(.87,.26,-.41)),
 (1.35,(.65,1.5),(.28,.32),3.,(1.5,-.52),(-.72,-.54,-.40)),
 (1.40,(-1.5,-.82),(-.45,-.44),-5.,(-1.5,.06),(0.,0.,0.)),
 (1.46,(1.5,-.7),(.62,-.50),12.,(.18,-1.5),(0.,0.,0.)),
)
ENTRY=.20; TURN=0.; CHARGE=.09; SHOT_AT=ENTRY+CHARGE
EXIT_TURN=0.; EXIT=.24; LEAVE=SHOT_AT+FIRE; DURATION=LEAVE+EXIT
HWS_END=REENTRY+WAVES[-1][0]+DURATION+.15
@dataclass(frozen=True)
class RaidUnit(Unit):
    def thrusters(self):
        return normal_ports(self.transform(),self.power,self.acceleration)

def camera_pose(t,kind='HiNu'):
    if kind=='HiNu':return old_camera(t)
    return CameraPose() # fixed throughout: no sudden camera cut

def _point(xy,z,aspect):
    h=(40-z)*math.tan(math.radians(17));return np.array([xy[0]*h*aspect,xy[1]*h,z])

def _geometry(i,aspect):
    _,entry,xy,z,exit,aim=WAVES[i]
    # guarantee complete exit at both edges even for narrow viewports
    def outside(p,depth):
        v=_point(p,depth,aspect);h=(40-depth)*math.tan(math.radians(17))
        axis=int(np.argmax(np.abs(p)));half=h*(aspect if axis==0 else 1.)
        v[axis]=math.copysign(max(abs(v[axis]),half+RADIUS+1.0),p[axis]);return v
    a=outside(entry,z-2);b=_point(xy,z,aspect);c=outside(exit,z-3);f=norm(np.asarray(TARGET)-b);return a,b,c,f

def raid_unit(i,t,aspect=1.):
    e=t-REENTRY-WAVES[i][0]
    if not 0<=e<DURATION:return None
    a,b,c,f=_geometry(i,aspect);v=norm(b-a);w=norm(c-b)
    p=b;acc=np.zeros(3);power=0.;fire=FirePose()
    if e<ENTRY:
        q=e/ENTRY;p=a+(b-a)*(1-(1-q)**2)
        power=.9*(1-smooth((q-.64)/.36))*max(0.,float(v@norm(np.asarray(TARGET)-p)))
        acc=v*.9*(1-smooth((q-.64)/.36))-v*.95*smooth((q-.64)/.36)
    elif e<SHOT_AT:
        fire=FirePose('charge',charge=smooth((e-ENTRY)/CHARGE))
    elif e<LEAVE:
        fire=FirePose('fire',age=e-SHOT_AT)
    else:
        q=clamp((e-LEAVE)/EXIT);p=b+(c-b)*q*q
        acc=w*.98;power=.98*smooth(q/.16)*max(0.,float(w@norm(np.asarray(TARGET)-p)))
        if e<SHOT_AT+FIRE+AFTER:fire=FirePose('afterglow',age=e-SHOT_AT)
    # Aim follows the common remote target, never the velocity. No turn-in or turn-out.
    r=basis(norm(np.asarray(TARGET)-p),i)
    return RaidUnit(i,tuple(p),tuple(r.ravel()),power,tuple(acc),True,fire)

def sample(t,kind='HiNu',aspect=1.):
    if not math.isfinite(t) or not math.isfinite(aspect) or aspect<=0:raise ValueError('invalid time/aspect')
    if kind=='HiNu':return old_sample(t)
    if kind!='HiNu_HWS':raise ValueError('unknown kind')
    if t<REENTRY:return old_sample(t)
    if t>=HWS_END:return ()
    return tuple(u for i in range(len(WAVES)) if (u:=raid_unit(i,t,aspect)) is not None)

def shot_matrix(i,kind='HiNu',aspect=1.):
    if kind=='HiNu':return old_shot_matrix(i)
    _,p,_,f=_geometry(i,aspect);m=np.eye(4);m[:3,:3]=basis(f,i)*SCALE;m[:3,3]=p;return m

def phase(t,kind='HiNu'):
    if kind=='HiNu' or t<REENTRY:return old_phase(t)
    return 'raid' if t<HWS_END else 'off'

class SpecialVolley(OldVolley):
    def __init__(self,kind='HiNu',aspect=1.):
        if kind not in ('HiNu','HiNu_HWS') or not math.isfinite(aspect) or aspect<=0:raise ValueError('invalid kind/aspect')
        self.kind=kind;self.aspect=aspect;super().__init__()
    @property
    def end(self):return HI_END if self.kind=='HiNu' else HWS_END
    def trigger(self,t,context=None):
        if not math.isfinite(t):raise ValueError('invalid time')
        if self.start is not None and 0<=t-self.start<self.end:return False
        self.start=self.last=t;self.context=context;return True
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=self.end:self.reset();return ()
        self.last=t;return sample(t-self.start,self.kind,self.aspect)
