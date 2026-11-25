"""Trial158: closed octahedral shield with seventh emitter on a subdivided rear edge.
World xyz, orthographic screen projection. No full mobile suit is added.
"""
from dataclasses import dataclass,replace
import math
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
import special157 as old
import special155 as ret
from flight150 import Frame,Jet,PORTS,MODEL_LENGTH,screen,pose_matrix,angle_delta
from motion149 import tip,smooth,DURATION
CENTER=old.CENTER; SIZE=old.SIZE
IGNITE,FULL,RELEASE,DEPART,END=old.IGNITE,old.FULL,old.RELEASE,old.DEPART,old.END
# IDs 0 top, 1 bottom, 2 left, 3 right, 4 near, 5 far, 6 rear edge relay.
# The horizontal axes are orthogonal in 3D, not in the projection.
V=np.array([[0,115,0],[0,-115,0],[-146,0,65],[146,0,-65],[58,13,130],[-58,-13,-130]],float)
V=np.vstack([V,(V[0]+V[5])/2])
FACES=[]
for pole in (0,1):
    for a,b in zip((2,4,3,5),(4,3,5,2)):
        if pole==0 and 5 in (a,b):
            other=b if a==5 else a; FACES.extend([(0,other,6),(6,other,5)])
        else:FACES.append((pole,a,b))
FACES=tuple(FACES)
EDGES=tuple(sorted({tuple(sorted((a,b))) for f in FACES for a,b in zip(f,f[1:]+f[:1])}-{(2,6),(3,6)}))

def target(i,center,size):
    k=size/SIZE; c=np.array([center[0],-center[1],0.]); p=c+V[i]*k
    forward=-V[i]/np.linalg.norm(V[i]); h=math.atan2(forward[1],forward[0]); pitch=math.asin(forward[2]); R=pose_matrix(h,0.,pitch)
    scale=size/MODEL_LENGTH*.68
    return R,p-scale*(R@tip(DURATION)),scale,h,pitch

def mix_rotation(a,b,q):return Slerp([0.,1.],Rotation.from_matrix(np.stack([a,b])))([q]).as_matrix()[0]

def jets(tr,R,scale,power=0.,side=0.):
    return tuple(Jet(k,tr+scale*(R@p),R@d,power if k=='rear' else side,w*scale) for k,(p,d,w) in PORTS.items())

def arrival(t,i,center,size):
    R,tr,scale,speed,h,b,p,power=ret.state(t,i,center,size)
    R1,tr1,s1,h1,p1=target(i,center,size)
    # Bend approach into the final 3D node, preserving exact return start.
    age=t-ret.start(i); q=smooth(age/ret.APPROACH)
    R0,tr0,s0,*_=ret.state(ret.start(i)+ret.APPROACH+ret.PAUSE+ret.SETTLE,i,center,size)
    tr=tr+(tr1-tr0)*q; scale=scale+(s1-s0)*q
    orient=smooth((age-ret.APPROACH)/max(.001,ret.PAUSE+ret.SETTLE))
    R=mix_rotation(R,R1,orient); h+=angle_delta(h,h1)*orient; p=p*(1-orient)+p1*orient
    if age>=ret.APPROACH+ret.PAUSE+ret.SETTLE:R,tr,scale,h,p=R1,tr1,s1,h1,p1; speed=power=b=0.
    return Frame(t,True,R,tr,scale,speed,h,b,p,jets(tr,R,scale,power),{k:() for k in PORTS},DURATION)

def arrive_trail(t,i,center,size,f):
    hist=[];length=0.;limit=old.LIMIT*f.scale*MODEL_LENGTH/82
    for q in np.linspace(t,max(ret.start(i),t-old.LIFE+1e-6),old.MAX_POINTS):
        x=arrival(float(q),i,center,size); power=x.jets[0].power
        if power<=.045 or x.speed<=8:continue
        pt=screen(x.world(PORTS['rear'][0]))
        if hist:
            a,p,v=hist[-1]; seg=np.linalg.norm(pt-p)
            if seg<1e-9:continue
            if length+seg>limit:
                u=(limit-length)/seg;hist.append((a+(q-a)*u,p+(pt-p)*u,v+(power-v)*u));break
            length+=seg
        hist.append((float(q),pt,power))
    return tuple(reversed(hist))

def depart_state(t,i,center,size):
    R,tr,s,h,p=target(i,center,size); age=max(0.,t-old.start(i)); k=size/SIZE
    d=V[i].copy(); d[2]=0; d/=np.linalg.norm(d); h2=math.atan2(d[1],d[0]); R2=pose_matrix(h2,0.,0.)
    q=smooth(age/old.TURN); R=mix_rotation(R,R2,q); h+=angle_delta(h,h2)*q
    u=max(0.,age-old.TURN); a=min(u,old.ACCEL); dist=k*old.SPEED*(a*a/(2*old.ACCEL)+max(0.,u-old.ACCEL)); tr=tr+d*dist
    return R,tr,s,h,p*(1-q),k*old.SPEED*min(1.,u/old.ACCEL),smooth(u/.055),.32*math.sin(math.pi*min(1.,age/old.TURN))**2

def sample_indexed(t,center=CENTER,size=SIZE):
    t,center,size=ret.launch.validate(t,center,size)
    if t<ret.launch.END:return ret.launch.sample_indexed(t,center,size)
    if t>=END:return ()
    result=[]
    for i in range(7):
        if t<ret.start(i):continue
        if t<DEPART or t<old.start(i):
            f=arrival(t,i,center,size)
            if t<ret.start(i)+ret.APPROACH+old.LIFE:f.trails['rear']=arrive_trail(t,i,center,size,f)
        else:
            R,tr,s,h,p,speed,power,side=depart_state(t,i,center,size)
            f=Frame(t,True,R,tr,s,speed,h,0.,p,jets(tr,R,s,power,side),{k:() for k in PORTS},DURATION)
            hist=[];length=0.;limit=old.LIMIT*s*MODEL_LENGTH/82
            for q in np.linspace(t,max(old.start(i)+old.TURN,t-old.LIFE+1e-6),old.MAX_POINTS):
                if q>t:break
                r,x,_,_,_,sp,pw,_=depart_state(float(q),i,center,size)
                if pw<=.045 or sp<=8:break
                pt=screen(x+s*(r@PORTS['rear'][0]))
                if hist:
                    a,pp,v=hist[-1];seg=np.linalg.norm(pt-pp)
                    if seg<1e-9:continue
                    if length+seg>limit:
                        u=(limit-length)/seg;hist.append((a+(q-a)*u,pp+(pt-pp)*u,v+(pw-v)*u));break
                    length+=seg
                hist.append((float(q),pt,pw))
            f.trails['rear']=tuple(reversed(hist))
        result.append((i,f))
    return tuple(result)

def sample(t,center=CENTER,size=SIZE):return tuple(f for _,f in sample_indexed(t,center,size))
@dataclass(frozen=True)
class Field:
    t:float; nodes:np.ndarray; edges:tuple; faces:tuple; edge_progress:tuple; face_progress:tuple; opacity:float; scale:float

def sample_field(t,center=CENTER,size=SIZE,units=None):
    t,center,size=ret.launch.validate(t,center,size)
    if not IGNITE<t<DEPART:return None
    frames=dict(sample_indexed(t,center,size) if units is None else units)
    if set(frames)!=set(range(7)):return None
    nodes=np.array([frames[i].world(tip(frames[i].deploy_time)) for i in range(7)])
    q=t-IGNITE; ep=tuple(smooth((q-j*.012)/.16) for j in range(len(EDGES)))
    fp=tuple(smooth((q-.36-j*.014)/.22) for j in range(len(FACES)))
    return Field(t,nodes,EDGES,FACES,ep,fp,1-smooth((t-RELEASE)/(DEPART-RELEASE)),size/SIZE)

class SpecialPolyhedron(old.SpecialDeparture):
    def update(self,t,visible=True,context=None):
        if not self.active:return ()
        t=float(t)
        if not visible or context!=self.context or not math.isfinite(t) or t<self.last or t-self.last>.25 or t-self.start>=END:
            self.reset();return ()
        self.last=t;age=t-self.start; units=sample_indexed(age,self.center,self.size);self.field=sample_field(age,self.center,self.size,units);return units
