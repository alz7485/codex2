"""Trial114: visible high-speed fly-throughs, re-entry, stop THEN aim."""
import math,json
from pathlib import Path
import numpy as np
from . import special_trial113 as old
from .special_trial113 import (REENTRY,FORMATION,CAMERA_Z,SCALE,AIM,RADIUS,FirePose,FIRE,AFTER,CHARGE,basis,blend,norm,make,world,clamp,smooth,STARTS,P0,V0,TARGETS,MUZZLE,FORWARD_POINT,ray_gap)
RAMP=.04; BRAKE=.045; STOP_HOLD=.065; TURN=.19; HOLD=.19
# Each route stores absolute local times and world positions of offscreen waypoints.
# Initial ramp and terminal braking integrate linear velocity; intervening legs are straight.
DIRECT_ARR=np.array([.52,.47,.43,.48,.53,.58])
def evaluate(i,route,t,velocity=False):
    times,points=route; t=np.asarray(t,dtype=float); end=times[-1]; q=np.clip(t,0,end)[...,None]
    a=times[1]; p0=points[0]; p1=points[1]; first=(p1-p0-.5*RAMP*V0[i])/(a-.5*RAMP-(.5*BRAKE if len(times)==2 else 0))
    u=np.minimum(q,RAMP); w=np.clip(q-RAMP,0,a-RAMP-(BRAKE if len(times)==2 else 0)); p=p0+V0[i]*u+.5*(first-V0[i])*u*u/RAMP+first*w
    v=V0[i]+(first-V0[i])*u/RAMP
    if len(times)==2:
        b=np.clip(q-(a-BRAKE),0,BRAKE);p+=first*(b-.5*b*b/BRAKE);v=v*(1-b/BRAKE)
    for k in range(1,len(times)-1):
        dur=times[k+1]-times[k];last=k==len(times)-2;d=points[k+1]-points[k];speed=d/(dur-(.5*BRAKE if last else 0)); elapsed=np.clip(q-times[k],0,dur)
        if last:
            b=np.clip(elapsed-(dur-BRAKE),0,BRAKE);pseg=points[k]+speed*(np.minimum(elapsed,dur-BRAKE)+b-.5*b*b/BRAKE);vseg=speed*(1-b/BRAKE)
        else:pseg=points[k]+speed*elapsed;vseg=np.broadcast_to(speed,pseg.shape)
        p=np.where(q>=times[k],pseg,p);v=np.where(q>=times[k],vseg,v)
    p=np.where(q>=end,points[-1],p);v=np.where(q>=end,0.,v)
    return v if velocity else p

def direct(i):return np.array([0.,DIRECT_ARR[i]]),np.array([P0[i],TARGETS[i]])
def load():
    data=json.loads(Path(__file__).with_name('routes114.json').read_text());return tuple((np.array(r['times']),np.array(r['points'])) for r in data)
# Allow offline path generation without the route file.
if Path(__file__).with_name('routes114.json').exists():
    ROUTES=load(); ARRIVALS=np.array([r[0][-1] for r in ROUTES]); MOVE=float(max(ARRIVALS)+STOP_HOLD+TURN); SHOT=FORMATION+MOVE+HOLD+CHARGE; END=SHOT+FIRE+AFTER+.22

def pos(i,e):return evaluate(i,ROUTES[i],e)
def direction(i,k):
    ts,ps=ROUTES[i]
    if k==0:return norm(evaluate(i,ROUTES[i],RAMP+1e-5,True))
    return norm(ps[k+1]-ps[k])
def unit(i,age):
    e=age-FORMATION;ts,ps=ROUTES[i];d=ARRIVALS[i];p=pos(i,e);k=int(np.clip(np.searchsorted(ts,e,side='right')-1,0,len(ts)-2)); f=direction(i,k);r=basis(f,i);a=f*.95
    if k==0:
        q=smooth(e/RAMP);r=blend(np.asarray(STARTS[i].rotation).reshape(3,3),r,q);a=(1-q)*np.asarray(STARTS[i].acceleration)+q*a
    elif e-ts[k]<.035:
        prev=direction(i,k-1);q=smooth((e-ts[k])/.035);r=blend(basis(prev,i),r,q);a=norm(f-prev)*.98
    if d-BRAKE<=e<d:a=-f
    if e>=d:
        # Hold incoming orientation at the EXACT stop, then rotate about fixed center.
        p=TARGETS[i].copy();incoming=direction(i,len(ts)-2);r0=basis(incoming,i);q=clamp((e-d-STOP_HOLD)/TURN);r=blend(r0,basis(AIM,i),smooth(q));a=np.zeros(3)
        if 0<q<1:a=r[:,0]*(.55*math.sin(math.pi*q))
        if q>=1:r=basis(AIM,i)
    fire=FirePose()
    if age>=FORMATION+MOVE+HOLD:
        if age<SHOT:fire=FirePose('charge',charge=smooth((age-(FORMATION+MOVE+HOLD))/CHARGE))
        elif age<SHOT+FIRE:
            b=age-SHOT;recoil=.13*math.sin(math.pi*min(1,b/.12));p=p-AIM*recoil*SCALE;fire=FirePose('fire',recoil=recoil,age=b)
        elif age<SHOT+FIRE+AFTER:fire=FirePose('afterglow',age=age-SHOT)
    return make(i,p,r,a,fire=fire)
def phase(t):
    if t<FORMATION:return old.phase(t)
    if t<FORMATION+max(ARRIVALS):return 'fast entry'
    if t<FORMATION+MOVE:return 'stop / turn'
    if t<FORMATION+MOVE+HOLD:return 'ready'
    if t<SHOT:return 'charge'
    if t<SHOT+FIRE:return 'volley'
    return 'afterglow' if t<END else 'off'
def sample(t):
    if not math.isfinite(t):raise ValueError('invalid age')
    if t<FORMATION:return old.sample(t)
    if t<END:return tuple(unit(i,t) for i in range(6))
    return ()
def shot_matrix(i):return unit(i,SHOT).transform()
flight_unit=old.flight_unit
class SpecialVolley(old.SpecialVolley):
    def trigger(self,t,context=None):
        if not math.isfinite(t):raise ValueError('invalid time')
        if self.start is not None and 0<=t-self.start<END:return False
        self.start=self.last=t;self.context=context;return True
    def update(self,t,*,visible=True,context=None):
        if not math.isfinite(t):self.reset();raise ValueError('invalid time')
        if self.start is None:return ()
        if not visible or context!=self.context or t<self.last or t-self.last>.25 or t-self.start>=END:self.reset();return ()
        self.last=t;return sample(t-self.start)
