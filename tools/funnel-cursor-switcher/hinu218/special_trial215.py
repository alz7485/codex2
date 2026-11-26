"""Hi-Nu overlapping paired passes; stationary V finale, six outward exits."""
from .special_trial214 import *
from . import special_trial214 as old
from . import special_trial213 as pair
PAIR_START=(0.,.98,1.96)
FINALE_START=max(PAIR_START[i//2]+timing(i)[-1] for i in range(6))+.12
FINALE_DURATION=1.60
FINALE_STOP=.36
FINALE_OPEN_START=.36
FINALE_OPEN_END=.60
FINALE_CHARGE=.13
FINALE_SHOTS=(.75,.75,.83,.83,.90,.90)
FINALE_SHOT=FINALE_SHOTS[0]
FINALE_LEAVE=1.19
FINALE_CLOSE_START=FINALE_LEAVE
FINALE_CLOSE_END=1.31
HI_END=REENTRY+FINALE_START+FINALE_DURATION+.18
# Six different outward screen directions. +Y is up.
EXIT_DIRS=((-1.,-.08),(-.12,1.),(-.65,-.76),(.65,.76),(.10,-1.),(1.,.10))

def event(i,t):
    e=t-REENTRY
    p=e-PAIR_START[i//2]
    d,_,_,_,_,shot,_,_,end=timing(i)
    if d<=p<end:return False,p,end,shot
    f=e-FINALE_START
    if 0<=f<FINALE_DURATION:return True,f,FINALE_DURATION,FINALE_SHOTS[i]
    return None

def finale_geometry(i,aspect):
    a,b=pair.prev.geometry(i,True,aspect)
    p=(a+b)*.5
    x,y=EXIT_DIRS[i];v=norm(np.array([x*aspect,y,0.]))
    h=(40-p[2])*math.tan(math.radians(17));bound=np.array([h*aspect,h])+RADIUS+2.
    dist=min((math.copysign(bound[k],v[k])-p[k])/v[k] for k in (0,1) if abs(v[k])>1e-9)
    return a,p,p+v*(dist+3.),v

def _axial(i,v,aim):
    x=RACK[i][0]*v;y=aim[:,1]-x*float(x@aim[:,1])
    if np.linalg.norm(y)<1e-8:y=np.array([0.,0.,1.])-x*x[2]
    y=norm(y);return np.column_stack((x,y,np.cross(x,y)))

def finale_pose(i,e,aspect):
    a,p,c,w=finale_geometry(i,aspect);v=norm(p-a);aim=basis(norm(TARGET-p),i)
    incoming=_axial(i,v,aim);outgoing=_axial(i,w,aim)
    if e<FINALE_STOP:
        q=max(0.,e/FINALE_STOP);return a+(p-a)*(1-(1-q)**2),incoming,v*.85*(1-smooth(q)),1.
    if e<FINALE_LEAVE:
        q=smooth((e-FINALE_OPEN_START)/(FINALE_OPEN_END-FINALE_OPEN_START))
        r=incoming if q<=0 else aim if q>=1 else blend(incoming,aim,q)
        return p,r,np.zeros(3),1-q
    q=min(1.,(e-FINALE_LEAVE)/(FINALE_DURATION-FINALE_LEAVE));fold=smooth((e-FINALE_CLOSE_START)/(FINALE_CLOSE_END-FINALE_CLOSE_START))
    return p+(c-p)*q*q,blend(aim,outgoing,fold) if fold<1 else outgoing,w*.95*smooth(q/.18),fold

def mobile_unit(i,t,aspect):
    ev=event(i,t)
    if ev is None:return None
    final,e,_,shot=ev
    if not final:
        return pair.mobile_unit(i,pair.REENTRY+pair.PAIR_START[i//2]+e,aspect)
    p,r,acc,fold=finale_pose(i,e,aspect);age=e-shot;f=FirePose()
    if -FINALE_CHARGE<=age<0:f=FirePose('charge',charge=smooth((age+FINALE_CHARGE)/FINALE_CHARGE))
    elif 0<=age<FIRE:f=FirePose('fire',age=age)
    elif FIRE<=age<FIRE+AFTER:f=FirePose('afterglow',age=age)
    return pair.HingedPair(i,tuple(p),tuple(r.ravel()),max(0.,float(acc@(-r[:,2]))),tuple(acc),True,f,fold)

@lru_cache(maxsize=1024)
def sample(t,kind='HiNu',aspect=1.):
    if kind!='HiNu' or t<REENTRY:return old.sample(t,kind,aspect)
    if not math.isfinite(t) or not math.isfinite(aspect) or aspect<=0:raise ValueError('invalid time/aspect')
    if t>=HI_END:return ()
    return tuple(u for i in range(6) if (u:=mobile_unit(i,t,aspect)) is not None)

def shot_matrix(i,kind='HiNu',aspect=1.,*,t=None):
    if kind!='HiNu' or t is None or t<REENTRY:return old.shot_matrix(i,kind,aspect,t=t)
    ev=event(i,t)
    if ev is None:raise ValueError('no active pass')
    final,e,_,shot=ev
    if not final:return pair.shot_matrix(i,kind,aspect,t=pair.REENTRY+pair.PAIR_START[i//2]+e)
    return mobile_unit(i,REENTRY+FINALE_START+shot+1e-9,aspect).transform()

def phase(t,kind='HiNu'):
    if kind!='HiNu' or t<REENTRY:return old.phase(t,kind)
    if t>=HI_END:return 'off'
    e=t-REENTRY-FINALE_START
    if e<0:return 'overlapping pairs'
    if e<FINALE_STOP:return 'V approach'
    if e<FINALE_LEAVE:return 'V stationary volley'
    return 'outward exit' if e<FINALE_DURATION else 'gap'

class SpecialVolley(old.SpecialVolley):
    @property
    def end(self):return HI_END if self.kind=='HiNu' else HWS_END
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=self.end:self.reset();return ()
        self.last=t;return sample(t-self.start,self.kind,self.aspect)
