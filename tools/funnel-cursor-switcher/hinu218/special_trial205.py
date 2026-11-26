"""HiNu mobile pair passes + moving coordinated finale; HWS and opening unchanged."""
import math
from functools import lru_cache
import numpy as np
from . import special_trial200 as old
from .special_trial111 import basis,blend,norm,RADIUS,SCALE
from .fire_trial89 import FirePose,FIRE,AFTER
from .composition_trial116 import CameraPose
from .thrust_trial86 import smooth
REENTRY=old.REENTRY; HWS_END=old.HWS_END; TARGET=np.array([-420.,330.,-180.])
PASS_DURATION=.90; PAIR_START=(0.,.28,.56); PAIR_SHOT=.43; CHARGE=.10
FINALE_START=1.73; FINALE_DURATION=1.22; FINALE_SHOT=.57
HI_END=REENTRY+FINALE_START+FINALE_DURATION+.18
# Each pair crosses a different direction with distinct depth lanes. Final six use a moving V.
LANES=(((-1.7,.55),(1.7,-.12),5.),((-1.7,.10),(1.7,-.57),-5.),((1.7,.64),(-1.7,-.08),-13.),((1.7,.18),(-1.7,-.54),-22.),((-.45,-1.7),(.72,1.7),14.),((.06,-1.7),(1.23,1.7),-33.))
# Final pattern: transverse spacing and echelon depth, two wings.
V=((-.20,.0,10.),(.20,.0,10.),(-.37,.10,-1.),(.37,.10,-1.),(-.52,.20,-13.),(.52,.20,-13.))
def point(xy,z,aspect):
 h=(40-z)*math.tan(math.radians(17));return np.array([xy[0]*h*aspect,xy[1]*h,z])
def geometry(i,final,aspect):
 if not final:
  a,b,z=LANES[i];a=point(a,z,aspect);b=point(b,z,aspect)
 else:
  side,lag,z=V[i];a=point((1.75+side+lag,-1.75+side-lag),z,aspect);b=point((-1.75+side+lag,1.75+side-lag),z,aspect)
 # Guarantee endpoints fully outside even on narrow displays, by extending along trajectory.
 half=(40-z)*math.tan(math.radians(17)); bounds=np.array([half*aspect,half])+RADIUS+1
 delta=b-a
 for is_start in (True,False):
  p=a if is_start else b;d=-delta if is_start else delta
  if not np.any(np.abs(p[:2])>bounds):
   steps=[(math.copysign(bounds[k]+.01,d[k])-p[k])/d[k] for k in (0,1) if abs(d[k])>1e-9]
   p+=d*max(0.,min(steps))
 return a,b

def event(i,t):
 e=t-REENTRY; p=e-PAIR_START[i//2]
 if 0<=p<PASS_DURATION:return False,p,PASS_DURATION,PAIR_SHOT
 f=e-FINALE_START
 if 0<=f<FINALE_DURATION:return True,f,FINALE_DURATION,FINALE_SHOT
 return None

def matrix_at(i,final,e,aspect):
 duration=FINALE_DURATION if final else PASS_DURATION; shot=FINALE_SHOT if final else PAIR_SHOT
 a,b=geometry(i,final,aspect);p=a+(b-a)*(e/duration);v=norm(b-a);aim=norm(TARGET-p)
 # Banking into aim while moving; keep lock during charge, shot and afterglow.
 q=1. if final else smooth((e-(shot-.25))/.15)*(1-smooth((e-(shot+FIRE+AFTER))/.06))
 r=basis(aim,i) if q==1 else blend(basis(v,i),basis(aim,i),q) if q>0 else basis(v,i)
 return p,r,v

def mobile_unit(i,t,aspect):
 ev=event(i,t)
 if ev is None:return None
 final,e,duration,shot=ev;p,r,v=matrix_at(i,final,e,aspect);f=FirePose();age=e-shot
 if -CHARGE<=age<0:f=FirePose('charge',charge=smooth((age+CHARGE)/CHARGE))
 elif 0<=age<FIRE:f=FirePose('fire',age=age)
 elif FIRE<=age<FIRE+AFTER:f=FirePose('afterglow',age=age)
 # Rear and lateral ports follow direction of movement, not the beam direction.
 rear=.88*max(0.,float(v@(-r[:,2])));acc=v*.92
 return old.RaidUnit(i,tuple(p),tuple(r.ravel()),rear,tuple(acc),True,f)

@lru_cache(maxsize=1024)
def sample(t,kind='HiNu',aspect=1.):
 if kind!='HiNu' or t<REENTRY:return old.sample(t,kind,aspect)
 if not math.isfinite(t) or not math.isfinite(aspect) or aspect<=0:raise ValueError('invalid time/aspect')
 if t>=HI_END:return ()
 return tuple(u for i in range(6) if (u:=mobile_unit(i,t,aspect)) is not None)

def shot_matrix(i,kind='HiNu',aspect=1.,*,t=None):
 if kind!='HiNu':return old.shot_matrix(i,kind,aspect)
 if t is None or t<REENTRY:raise ValueError('HiNu mobile beam requires current special age t')
 ev=event(i,t)
 if ev is None:raise ValueError('no active pass')
 final,_,_,shot=ev;p,r,_=matrix_at(i,final,shot,aspect);m=np.eye(4);m[:3,:3]=r*SCALE;m[:3,3]=p;return m

def camera_pose(t,kind='HiNu'):
 return old.camera_pose(t,kind) if kind!='HiNu' or t<REENTRY else CameraPose()
def phase(t,kind='HiNu'):
 if kind!='HiNu' or t<REENTRY:return old.phase(t,kind)
 if t>=HI_END:return 'off'
 return 'crossfire' if t<REENTRY+FINALE_START else 'moving volley'
class SpecialVolley(old.SpecialVolley):
 @property
 def end(self):return HI_END if self.kind=='HiNu' else HWS_END
 def update(self,t,*,visible=True,context=None):
  if not math.isfinite(t):self.reset();raise ValueError('invalid time')
  if self.start is None:return ()
  if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=self.end:self.reset();return ()
  self.last=t;return sample(t-self.start,self.kind,self.aspect)
