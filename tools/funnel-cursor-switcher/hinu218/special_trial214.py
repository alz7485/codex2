"""Hi-Nu finale: moving depth V, three overlapping volleys, fold and depart.
All pre-finale behavior and HWS are delegated unchanged to Trial213.
"""
from .special_trial213 import *
from . import special_trial213 as old
from scipy.interpolate import PchipInterpolator

FINALE_DURATION=1.44
FINALE_SHOTS=(.57,.57,.65,.65,.72,.72)
FINALE_SHOT=FINALE_SHOTS[0]
FINALE_CHARGE=.13
FINALE_OPEN_START=.14
FINALE_OPEN_END=.43
FINALE_CLOSE_START=1.13
FINALE_CLOSE_END=1.31
HI_END=REENTRY+FINALE_START+FINALE_DURATION+.18
# Faster entrance/exit and an uninterrupted, slower moving firing pass.
_progress=PchipInterpolator([0,.40,.99,FINALE_DURATION],[0,.40,.61,1.],extrapolate=False)

def event(i,t):
    e=t-(REENTRY+FINALE_START)
    if 0<=e<FINALE_DURATION:return True,e,FINALE_DURATION,FINALE_SHOTS[i]
    if t<REENTRY+FINALE_START:return old.event(i,t)
    return None

def finale_pose(i,e,aspect):
    a,b=old.prev.geometry(i,True,aspect)
    v=norm(b-a); p=a+(b-a)*float(_progress(np.clip(e,0,FINALE_DURATION)))
    # Same folded geometry and pivot as the individual passes. Align folded long axis to travel.
    aim=basis(norm(TARGET-p),i)
    x=RACK[i][0]*v;y=aim[:,1]-x*float(x@aim[:,1])
    if np.linalg.norm(y)<1e-8:y=np.array([0.,0.,1.])-x*x[2]
    y=norm(y);axial=np.column_stack((x,y,np.cross(x,y)))
    opened=smooth((e-FINALE_OPEN_START)/(FINALE_OPEN_END-FINALE_OPEN_START))
    opened*=1-smooth((e-FINALE_CLOSE_START)/(FINALE_CLOSE_END-FINALE_CLOSE_START))
    r=axial if opened<=0 else aim if opened>=1 else blend(axial,aim,opened)
    thrust=.45+.48*(1-smooth((e-.18)/.25))+.42*smooth((e-.99)/.24)
    acc=v*min(.95,thrust)
    return p,r,acc,1-opened

def mobile_unit(i,t,aspect):
    if t<REENTRY+FINALE_START:return old.mobile_unit(i,t,aspect)
    ev=event(i,t)
    if ev is None:return None
    _,e,_,shot=ev;p,r,acc,fold=finale_pose(i,e,aspect);age=e-shot;f=FirePose()
    if -FINALE_CHARGE<=age<0:f=FirePose('charge',charge=smooth((age+FINALE_CHARGE)/FINALE_CHARGE))
    elif 0<=age<FIRE:f=FirePose('fire',age=age)
    elif FIRE<=age<FIRE+AFTER:f=FirePose('afterglow',age=age)
    rear=max(0.,float(acc@(-r[:,2])))
    return old.HingedPair(i,tuple(p),tuple(r.ravel()),rear,tuple(acc),True,f,fold)

@lru_cache(maxsize=1024)
def sample(t,kind='HiNu',aspect=1.):
    if kind!='HiNu' or t<REENTRY+FINALE_START:return old.sample(t,kind,aspect)
    if not math.isfinite(t) or not math.isfinite(aspect) or aspect<=0:raise ValueError('invalid time/aspect')
    if t>=HI_END:return ()
    return tuple(u for i in range(6) if (u:=mobile_unit(i,t,aspect)) is not None)

def shot_matrix(i,kind='HiNu',aspect=1.,*,t=None):
    if kind!='HiNu' or t is None or t<REENTRY+FINALE_START:return old.shot_matrix(i,kind,aspect,t=t)
    if event(i,t) is None:raise ValueError('no active pass')
    return mobile_unit(i,REENTRY+FINALE_START+FINALE_SHOTS[i]+1e-9,aspect).transform()

def phase(t,kind='HiNu'):
    if kind!='HiNu' or t<REENTRY+FINALE_START:return old.phase(t,kind)
    if t>=HI_END:return 'off'
    return 'V formation ripple' if t<REENTRY+FINALE_START+FINALE_DURATION else 'gap'
class SpecialVolley(old.SpecialVolley):
    @property
    def end(self):return HI_END if self.kind=='HiNu' else HWS_END
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=self.end:self.reset();return ()
        self.last=t;return sample(t-self.start,self.kind,self.aspect)
