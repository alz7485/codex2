"""Dragoon normal-flight reference. Coordinates: screen x right/y down; world y up.
Trial135: quicker heading response, stronger speed-weighted bank and exhaust. Visual control, not a physics solver. No Windows hooks or cursor modification.
"""
from dataclasses import dataclass
import math
import numpy as np

TIP=np.array([-.1855,0.,-3.38])
# Effect-only locations; estimated from Trial133's rear rail gap and outer hull.
PORTS={
    'rear': ((.151,0.,3.22),(0.,0.,1.),.11),
    'left': ((-.102,0.,1.8),(-1.,0.,0.),.055),
    'right': ((.776,0.,1.8),(1.,0.,0.),.055),
}
LIFE=.18; LIMIT=48.; MAX_POINTS=32

def clip(x,lo=0.,hi=1.): return min(hi,max(lo,float(x)))
def approach(a,b,dt,tau): return a+(b-a)*(-math.expm1(-dt/tau))
def angle_delta(a,b): return math.atan2(math.sin(b-a),math.cos(b-a))
def pose_matrix(heading,bank,pitch):
    c,s=math.cos(heading),math.sin(heading)
    base=np.array([[s,0,-c],[-c,0,-s],[0,1,0.]])
    cb,sb=math.cos(bank),math.sin(bank);cp,sp=math.cos(pitch),math.sin(pitch)
    roll=np.array([[cb,-sb,0],[sb,cb,0],[0,0,1.]])
    tilt=np.array([[1,0,0],[0,cp,-sp],[0,sp,cp]])
    return base@roll@tilt

def screen(v): return np.array([v[0],-v[1]])
@dataclass
class Jet:
    name:str; origin:np.ndarray; direction:np.ndarray; power:float; width:float
@dataclass
class Frame:
    t:float; visible:bool; matrix:np.ndarray; translation:np.ndarray; scale:float
    speed:float; heading:float; bank:float; pitch:float; jets:tuple; trails:dict
    def world(self,p): return self.translation+self.scale*(self.matrix@np.asarray(p))

class Flight:
    def __init__(self): self.reset()
    def reset(self):
        self.last_t=None; self.last_pos=None; self.context=None; self.scale=None
        self.heading=math.pi/3; self.velocity=np.zeros(2);self.bank=self.pitch=0.
        self.power={k:0. for k in PORTS};self.trails={k:[] for k in PORTS}
    def update(self,t,position,size=82.,visible=True,context=None):
        t=float(t);size=float(size);pos=np.asarray(position,dtype=float)
        if not math.isfinite(t) or not math.isfinite(size) or not 1<=size<=1024 or pos.shape!=(2,) or not np.isfinite(pos).all():
            self.reset(); raise ValueError('finite time/position and size in [1,1024] required')
        scale=size/6.6
        if not visible:
            self.reset(); return Frame(t,False,np.eye(3),np.zeros(3),scale,0.,0.,0.,0.,(),{})
        if (self.last_t is None or self.context!=context or self.scale!=scale or t<self.last_t or t-self.last_t>.25 or np.linalg.norm(pos-self.last_pos)>240):
            self.reset();self.last_t=t;self.last_pos=pos.copy();self.context=context;self.scale=scale
        dt=t-self.last_t
        speed=0.; turn=0.; accel=np.zeros(2)
        if dt>0:
            raw=(pos-self.last_pos)/dt;speed=float(np.linalg.norm(raw))
            old=self.velocity.copy();self.velocity=approach(old,raw,dt,.038);accel=(self.velocity-old)/dt
            if speed>5:
                target=math.atan2(-raw[1],raw[0]); change=angle_delta(self.heading,target)
                turn=clip(change*(-math.expm1(-dt/.052)),-15*dt,15*dt)/dt
                self.heading+=turn*dt
            front=np.array([math.cos(self.heading),-math.sin(self.heading)])
            longitudinal=float(np.dot(accel,front)); alignment=clip(np.dot(raw,front)/max(speed,1))
            moving=clip(speed/80)
            bank_gain=.052+.024*clip(speed/650)
            self.bank=approach(self.bank,clip(-turn*bank_gain,-.62,.62)*moving,dt,.060 if speed>8 else .085)
            self.pitch=approach(self.pitch,clip(longitudinal*.000085,-.23,.22)*moving,dt,.075)
            R=pose_matrix(self.heading,self.bank,self.pitch)
            desired={'rear':moving*alignment*clip(.20+.70*speed/550+max(0,longitudinal)/2800-max(0,-longitudinal)/2100)}
            for name,(_,d,_) in PORTS.items():
                if name=='rear':continue
                force=-np.dot(accel,screen(R@d)); desired[name]=moving*clip(max(0,force)/1550)
            # Actual direction is never flipped; only intensity is varied.
            for name in PORTS: self.power[name]=approach(self.power[name],desired[name],dt,.022 if desired[name]>self.power[name] else .045)
            self.last_t=t;self.last_pos=pos.copy()
        R=pose_matrix(self.heading,self.bank,self.pitch); origin=np.array([pos[0],-pos[1],0.])-scale*(R@TIP)
        jets=tuple(Jet(k,origin+scale*(R@p),R@d,self.power[k],w*scale) for k,(p,d,w) in PORTS.items())
        for j in jets:
            hist=self.trails[j.name]; hist[:]=[(a,p,v) for a,p,v in hist if 0<=t-a<LIFE]
            if dt>0 and speed>8 and j.power>.045:
                p=screen(j.origin)
                if not hist or np.linalg.norm(p-hist[-1][1])>1.2:
                    hist.append((t,p,j.power))
            # Path length bound, newest point first; trim oldest segment by interpolation.
            limit=LIMIT*size/82.; length=0.
            for i in range(len(hist)-1,0,-1):
                seg=float(np.linalg.norm(hist[i][1]-hist[i-1][1]))
                if length+seg>limit:
                    a,p,v=hist[i];b,q,u=hist[i-1]; f=(limit-length)/max(seg,1e-12)
                    hist[:i]=[(a+(b-a)*f,p+(q-p)*f,v+(u-v)*f)]
                    break
                length+=seg
            hist[:]=hist[-MAX_POINTS:]
        return Frame(t,True,R,origin,scale,speed,self.heading,self.bank,self.pitch,jets,{k:tuple((a,p.copy(),v) for a,p,v in h) for k,h in self.trails.items()})
