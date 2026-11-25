"""Independent escort motion with visual-only shooting alignment. No OS hooks."""
from dataclasses import dataclass, replace
from collections import deque
from pathlib import Path
import json, math, os, tempfile
import numpy as np
from scipy.spatial.transform import Rotation, Slerp
from flight_trial135 import Flight, TIP, PORTS, Jet, LIFE, LIMIT, MAX_POINTS, clip, approach, screen
from combat_trial137 import Combat, CombatFrame, Shot, BEAM_AXIS, BEAM_ORIGIN, SHOT_TIME

@dataclass(frozen=True)
class Settings:
    escort_count:int=0
    escort_size_percent:int=100
    escort_fire_enabled:bool=True
    def __post_init__(self):
        if type(self.escort_count) is not int or not 0<=self.escort_count<=3: raise ValueError('escort_count 0..3')
        if type(self.escort_size_percent) is not int or not 50<=self.escort_size_percent<=120: raise ValueError('escort_size_percent 50..120')
        if type(self.escort_fire_enabled) is not bool: raise ValueError('escort_fire_enabled bool')
    @classmethod
    def from_dict(cls,d):
        return cls(*(d.get(k,v) for k,v in [('escort_count',0),('escort_size_percent',100),('escort_fire_enabled',True)]))
    @classmethod
    def load(cls,path):
        p=Path(path);return cls.from_dict(json.loads(p.read_text(encoding='utf-8'))) if p.exists() else cls()
    def save(self,path):
        p=Path(path); d=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {};d.update(vars(self))
        fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.',suffix='.tmp')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
            os.replace(tmp,p)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)

BASE=(.68,.61,.54); DELAYS=(.10,.20,.30); RETURN=.24
@dataclass
class FleetFrame:
    main:CombatFrame
    escorts:tuple
    positions:tuple
    synced:bool

class Escort:
    def __init__(self,i):
        self.i=i;self.flight=Flight();self.pos=None;self.vel=np.zeros(2);self.power={k:0. for k in PORTS};self.hist={k:[] for k in PORTS};self.pending=deque();self.shot=None;self.last_R=None;self.last_sync_R=None;self.return_t=None
    def clear_fire(self):
        self.pending.clear();self.shot=None;self.last_sync_R=None;self.return_t=None
    def move(self,t,dt,main,p,size,ratio,context):
        # Formation based only on main's underlying flight heading, never shooting state.
        a=main.flight.heading; front=np.array([math.cos(a),-math.sin(a)]); side=np.array([-front[1],front[0]])
        spacing=size*(.78+.22*ratio); i=self.i
        slots=((.78,-.83),(1.00,.82),(1.62,.04))
        back,lateral=slots[i]; target=p+spacing*(-back*front+lateral*side)
        # Small independent hover, continuous even when stopped.
        target+=size*.045*np.array([math.sin(t*2.1+i*2.2),math.cos(t*1.7+i*2.0)])
        oldv=self.vel.copy()
        if self.pos is None:self.pos=target.copy()
        elif dt>0:
            desired=(target-self.pos)/(.13+.045*i); n=np.linalg.norm(desired)
            desired*=min(1,1100/max(n,1e-9));self.vel=approach(self.vel,desired,dt,.065+.025*i);self.pos+=self.vel*dt
        acc=(self.vel-oldv)/dt if dt>0 else np.zeros(2)
        actual=size*BASE[i]*ratio
        f=self.flight.update(t,self.pos,max(1.,actual),True,context)
        if actual<1.:
            scale=actual/6.6
            f=replace(f,scale=scale,translation=f.world(TIP)-scale*(f.matrix@TIP))
        return f,acc
    def render(self,f,acc,R,dt):
        # All effect origins follow the actual rendered pose, not the unsynchronised flight pose.
        trans=f.world(TIP)-f.scale*(R@TIP); jets=[]
        for k,(p,d,w) in PORTS.items():
            direction=R@d; origin=trans+f.scale*(R@p); moving=clip(f.speed/80)
            if k=='rear':
                forward=-screen(direction); align=clip(np.dot(self.vel,forward)/max(np.linalg.norm(self.vel),1))
                longitudinal=np.dot(acc,forward); desired=moving*align*clip(.20+.70*f.speed/550+max(0,longitudinal)/2800-max(0,-longitudinal)/2100)
            else:desired=moving*clip(max(0,-np.dot(acc,screen(direction)))/1550)
            self.power[k]=approach(self.power[k],desired,dt,.022 if desired>self.power[k] else .045)
            j=Jet(k,origin,direction,self.power[k],w*f.scale);jets.append(j)
            h=self.hist[k];h[:]=[(a,p,v) for a,p,v in h if 0<=f.t-a<LIFE]
            if dt>0 and f.speed>8 and j.power>.045:
                p=screen(j.origin)
                if not h or np.linalg.norm(p-h[-1][1])>1.2:h.append((f.t,p,j.power))
            limit=LIMIT*f.scale*6.6/82;length=0.
            for ix in range(len(h)-1,0,-1):
                seg=float(np.linalg.norm(h[ix][1]-h[ix-1][1]))
                if length+seg>limit:
                    a,p,v=h[ix];b,q,u=h[ix-1];z=(limit-length)/max(seg,1e-12);h[:ix]=[(a+(b-a)*z,p+(q-p)*z,v+(u-v)*z)];break
                length+=seg
            h[:]=h[-MAX_POINTS:]
        self.last_R=R.copy()
        return replace(f,matrix=R,translation=trans,jets=tuple(jets),trails={k:tuple((a,p.copy(),v) for a,p,v in h) for k,h in self.hist.items()})

class Fleet:
    def __init__(self):self.main=Combat();self.reset()
    def reset(self):self.main.reset();self.units=[];self.last=None;self.settings=Settings();self.last_shot=None;self.was_sync=False
    def update(self,t,position,pressed=False,size=82.,visible=True,context=None,settings=Settings()):
        if not isinstance(settings,Settings):raise TypeError('Settings required')
        p=np.asarray(position,dtype=float);t=float(t);size=float(size)
        try:main=self.main.update(t,p,pressed,size,visible,context)
        except ValueError:self.reset();raise
        discontinuity=self.last is None or t<self.last[0] or t-self.last[0]>.25 or size!=self.last[2] or context!=self.last[3] or np.linalg.norm(p-self.last[1])>240
        changed=(settings.escort_count,settings.escort_size_percent)!=(self.settings.escort_count,self.settings.escort_size_percent)
        dt=0. if discontinuity else t-self.last[0]
        if not visible:
            self.units=[];self.last=None;self.last_shot=None;self.was_sync=False;self.settings=settings
            return FleetFrame(main,(),(),False)
        if discontinuity or changed:
            self.units=[Escort(i) for i in range(settings.escort_count)];self.was_sync=False;dt=0.
        if not settings.escort_fire_enabled or self.settings.escort_fire_enabled!=settings.escort_fire_enabled:
            for u in self.units:u.clear_fire()
            self.was_sync=False
        newshot=main.shot is not None and main.shot is not self.last_shot
        if newshot and settings.escort_fire_enabled:
            for u in self.units:u.pending.append((main.shot.t+DELAYS[u.i],main.shot.charge))
        self.last_shot=main.shot
        for u in self.units:
            if u.shot is not None and t-u.shot.t>=SHOT_TIME:u.shot=None
        sync=bool(self.units and settings.escort_fire_enabled and (main.charging or main.shot is not None or any(u.pending or u.shot for u in self.units)))
        frames=[]; ratio=settings.escort_size_percent/100
        for u in self.units:
            f,acc=u.move(t,dt,main,p,size,ratio,context)
            if sync:
                R=main.flight.matrix.copy();u.last_sync_R=R.copy();u.return_t=None
            else:
                if self.was_sync and u.last_sync_R is not None:u.return_t=t
                R=f.matrix
                if u.return_t is not None:
                    x=clip((t-u.return_t)/RETURN);x=x*x*(3-2*x)
                    R=Slerp([0,1],Rotation.from_matrix(np.stack((u.last_sync_R,R))))([x]).as_matrix()[0]
                    if t-u.return_t>=RETURN:u.return_t=None;u.last_sync_R=None
            f=u.render(f,acc,R,dt)
            if settings.escort_fire_enabled and u.shot is None and u.pending and t+1e-9>=u.pending[0][0]:
                due,q=u.pending.popleft();u.shot=Shot(t,tuple(f.world(BEAM_ORIGIN)),tuple(f.matrix@BEAM_AXIS),q,f.scale)
            # Keep charge visual until this unit's delayed launch; no auto-fire while held.
            charging=settings.escort_fire_enabled and (main.charging or (bool(u.pending) and u.shot is None))
            q=main.charge if main.charging else u.pending[0][1] if charging else 0.
            frames.append(CombatFrame(f,q,charging,u.shot,len(u.pending),0.))
        self.last=(t,p.copy(),size,context);self.settings=settings;self.was_sync=sync
        return FleetFrame(main,tuple(frames),tuple(tuple(u.pos) for u in self.units),sync)
