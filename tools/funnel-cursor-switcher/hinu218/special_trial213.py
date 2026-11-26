"""HiNu folded launch shape -> stop -> unfold to combat -> charge -> shot -> hold -> refold on exit."""
from .special_trial208 import *
from . import special_trial208 as prev
from .special_trial104 import RACK
from .special_trial102 import PIVOT
from .nozzle_trial119 import normal_ports
# Pair-only shared target; deeper than the earlier near-screen-plane aim.
TARGET=np.array([-75.,60.,-100.])
# Per-unit schedule: delay, entry, hold, bend, charge, post-shot hold, exit.
TIMINGS=((0,.25,.13,.24,.13,.13,.26),(.14,.25,.08,.23,.13,.15,.27),
 (0,.27,.10,.25,.13,.12,.25),(.10,.23,.15,.22,.14,.16,.27),
 (0,.24,.10,.22,.13,.14,.26),(.18,.27,.09,.24,.13,.11,.24))
PAIR_START=(0.,1.12,2.37)
def timing(i):
 d,entry,hold,bend,charge,post,exit=TIMINGS[i]
 bs=d+entry+hold; shot=bs+bend+charge; leave=shot+FIRE+post
 return d,entry,bs,bend,charge,shot,leave,exit,leave+exit
FINALE_START=max(PAIR_START[i//2]+timing(i)[-1] for i in range(6))+.12
HI_END=REENTRY+FINALE_START+FINALE_DURATION+.18

def entry_delay(i):return TIMINGS[i][0]
def event(i,t):
 e=t-REENTRY;p=e-PAIR_START[i//2]
 d,_,_,_,_,shot,_,_,end=timing(i)
 if d<=p<end:return False,p,end,shot
 f=e-FINALE_START
 if 0<=f<FINALE_DURATION:return True,f,FINALE_DURATION,FINALE_SHOT
 return None

def path(i,e,aspect):
 d,ENTRY,_,_,_,_,LEAVE,EXIT,_=timing(i)
 a,c=prev.geometry(i,False,aspect); b=(a+c)*.5; v=norm(b-a);w=norm(c-b)
 # Retain previous offscreen clearance and flight paths.
 a=a-v*2.0; c=c+w*2.0
 if e<ENTRY+entry_delay(i):
  q=max(0.,(e-entry_delay(i))/ENTRY);p=a+(b-a)*(1-(1-q)**2);acc=v*.85*(1-smooth((q-.50)/.50))-v*.9*smooth((q-.50)/.50)*(1-smooth((q-.88)/.12))
 elif e<LEAVE:p=b;acc=np.zeros(3)
 else:
  q=min(1.,(e-LEAVE)/EXIT);p=b+(c-b)*q*q;acc=w*.95*smooth(q/.18)
 return p,acc

def axial_rotation(i,aspect,direction):
 # Same handed folded pose and longitudinal axis as initial rack launch.
 a,c=prev.geometry(i,False,aspect);b=(a+c)*.5
 aim=basis(norm(TARGET-b),i);v=norm(direction)
 x=RACK[i][0]*v
 y=aim[:,1]-x*float(x@aim[:,1])
 if np.linalg.norm(y)<1e-8:y=np.array([0.,0.,1.])-x*x[2]
 y=norm(y);z=np.cross(x,y)
 return np.column_stack((x,y,z))

def entry_rotation(i,aspect):
 a,c=prev.geometry(i,False,aspect);return axial_rotation(i,aspect,c-a)

REFOLD=.12

def pose(i,e,aspect):
 _,_,BEND_START,BEND,_,_,LEAVE,_,_=timing(i)
 p,acc=path(i,e,aspect)
 a,c=prev.geometry(i,False,aspect);b=(a+c)*.5
 aim=basis(norm(TARGET-b),i)
 q=smooth((e-BEND_START)/BEND)
 r=entry_rotation(i,aspect) if q<=0 else aim if q>=1 else blend(entry_rotation(i,aspect),aim,q)
 fold=1-q
 if e>=LEAVE:
  fold=smooth((e-LEAVE)/REFOLD)
  r=blend(aim,axial_rotation(i,aspect,c-b),fold)
 return p,r,acc,fold

@dataclass(frozen=True)
class HingedPair(prev.PairUnit):
 def transform(self):
  m=super().transform();m[:3,3]-=m[:3,:3]@PIVOT;return m
 def part_matrix(self,side):
  angles={'Port':90.,'Starboard':78.,'Fixed':0.} if RACK[self.id][0]<0 else {'Port':-78.,'Starboard':-90.,'Fixed':0.}
  return self.transform()@hinge_matrix(side,angles[side]*self.fold)
 def thrusters(self):return normal_ports(self.transform(),self.power,self.acceleration)

def mobile_unit(i,t,aspect):
 ev=event(i,t)
 if ev is None:return None
 final,e,_,shot=ev
 if final:return prev.mobile_unit(i,prev.REENTRY+prev.FINALE_START+e,aspect)
 CHARGE=timing(i)[4];p,r,acc,fold=pose(i,e,aspect);age=e-shot;f=FirePose()
 if -CHARGE<=age<0:f=FirePose('charge',charge=smooth((age+CHARGE)/CHARGE))
 elif 0<=age<FIRE:f=FirePose('fire',age=age)
 elif FIRE<=age<FIRE+AFTER:f=FirePose('afterglow',age=age)
 rear=max(0.,float(acc@(-r[:,2])))
 return HingedPair(i,tuple(p),tuple(r.ravel()),rear,tuple(acc),True,f,fold)

@lru_cache(maxsize=1024)
def sample(t,kind='HiNu',aspect=1.):
 if kind!='HiNu' or t<REENTRY:return prev.sample(t,kind,aspect)
 if not math.isfinite(t) or not math.isfinite(aspect) or aspect<=0:raise ValueError('invalid time/aspect')
 if t>=HI_END:return ()
 return tuple(u for i in range(6) if (u:=mobile_unit(i,t,aspect)) is not None)

def shot_matrix(i,kind='HiNu',aspect=1.,*,t=None):
 if kind!='HiNu':return prev.shot_matrix(i,kind,aspect,t=t)
 if t is None or t<REENTRY:raise ValueError('HiNu requires current special age')
 ev=event(i,t)
 if ev is None:raise ValueError('no active pass')
 final,e,_,shot=ev
 if final:return prev.shot_matrix(i,kind,aspect,t=prev.REENTRY+prev.FINALE_START+e)
 return mobile_unit(i,REENTRY+PAIR_START[i//2]+shot+1e-9,aspect).transform()

def phase(t,kind='HiNu'):
 if kind!='HiNu' or t<REENTRY:return prev.phase(t,kind)
 if t>=HI_END:return 'off'
 if t>=REENTRY+FINALE_START:return 'moving volley'
 return 'staggered pair'
class SpecialVolley(prev.SpecialVolley):
 @property
 def end(self):return HI_END if self.kind=='HiNu' else HWS_END
 def update(self,t,*,visible=True,context=None):
  if not math.isfinite(t):self.reset();raise ValueError('invalid time')
  if self.start is None:return ()
  if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=self.end:self.reset();return ()
  self.last=t;return sample(t-self.start,self.kind,self.aspect)
