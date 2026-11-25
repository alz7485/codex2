"""Eight DRAGOONs: preserve Trial141, then assemble a staggered depth formation.
Screen-coordinate choreography with depth layers, not a full perspective camera.
"""
import math
import numpy as np
import special_trial141 as old
from flight_trial135 import Frame, Jet, PORTS, pose_matrix, screen, LIFE, LIMIT, angle_delta
CENTER=old.CENTER; SIZE=old.SIZE
ASSEMBLY=old.END+.20; BRAKE=.045; STOP=.065; TURN=.19; HOLD=.28; SPEED=1080.
FIRE_HEADING=math.radians(148); FIRE_BANK=.18; FIRE_PITCH=-.16
# entry, final center, depth, entry roll. IDs remain stable across the whole show.
ROUTES=(
 ((-190,0),(100,72),-480,.13),
 ((210,-180),(211,55),-390,-.16),
 ((820,0),(325,86),-300,.22),
 ((-170,350),(131,175),-210,-.18),
 ((230,570),(267,164),-105,.16),
 ((850,240),(411,180),0,-.24),
 ((320,570),(344,310),125,.20),
 ((850,570),(518,293),255,-.20),
)
def timings(i):
    p,q,_,_=ROUTES[i]; dist=np.linalg.norm(np.subtract(q,p)); start=ASSEMBLY+i*.045
    brake=start+dist/SPEED-BRAKE/2; stop=brake+BRAKE; turn=stop+STOP; ready=turn+TURN
    return start,brake,stop,turn,ready
READY=max(timings(i)[-1] for i in range(8)); END=READY+HOLD

def motion(i,t):
    p,q,depth,roll=ROUTES[i];p=np.array(p,float);q=np.array(q,float);d=(q-p)/np.linalg.norm(q-p);h=old.heading(d)
    start,brake,stop,turn,ready=timings(i)
    if t<start:return None
    if t<brake:return p+d*SPEED*(t-start),h,roll,0.,SPEED,1.,np.zeros(2),0.
    if t<stop:
        x=(t-brake)/BRAKE;remain=SPEED*BRAKE/2*(1-x)**2
        return q-d*remain,h,roll*(1-x),0.,SPEED*(1-x),1-x,-d*SPEED/BRAKE,0.
    if t<turn:return q,h,0.,0.,0.,0.,np.zeros(2),0.
    if t<ready:
        x=(t-turn)/TURN; f=old.smooth(x);delta=angle_delta(h,FIRE_HEADING)
        return q,h+delta*f,FIRE_BANK*f,FIRE_PITCH*f,0.,0.,np.zeros(2),delta*6*x*(1-x)/TURN
    return q,FIRE_HEADING,FIRE_BANK,FIRE_PITCH,0.,0.,np.zeros(2),0.

def raw(i,t,center=CENTER,size=SIZE):
    m=motion(i,t)
    if m is None:return None
    p,h,b,pitch,v,rear,a,rate=m;depth=ROUTES[i][2];factor=size/SIZE
    scale=size/6.6*800/(800-depth);p=np.asarray(center)+(p-np.asarray(CENTER))*factor
    R=pose_matrix(h,b,pitch);tr=np.array([p[0],-p[1],depth*factor]);jets=[]
    for k,(o,d,w) in PORTS.items():
        direction=R@d
        power=rear if k=='rear' else max(min(1.,max(0.,-np.dot(a,screen(direction))/4500)),min(.7,max(0.,rate*(1 if k=='left' else -1)/18)))
        jets.append(Jet(k,tr+scale*(R@o),direction,power,w*scale))
    return Frame(t,True,R,tr,scale,v*factor,h,b,pitch,tuple(jets),{k:() for k in PORTS})

def sample_indexed(t,center=CENTER,size=SIZE):
    t=float(t);size=float(size);center=np.asarray(center,float)
    if not math.isfinite(t) or center.shape!=(2,) or not np.isfinite(center).all() or not math.isfinite(size) or not 1<=size<=1024:raise ValueError('invalid input')
    if t<old.END:return old.sample_indexed(t,center,size)
    if t<ASSEMBLY or t>=END:return ()
    out=[]
    for i in range(8):
        u=raw(i,t,center,size)
        if u is None:continue
        hist={k:[] for k in PORTS};start=timings(i)[0]
        for q in np.linspace(max(start,t-LIFE+1e-6),t,12):
            prev=raw(i,q,center,size)
            if prev is None or prev.speed<8:continue
            for j in prev.jets:
                h=hist[j.name];p=screen(j.origin)
                if j.power>.045 and (not h or np.linalg.norm(p-h[-1][1])>1.2*size/SIZE):h.append((float(q),p,j.power))
        for k,h in hist.items():
            limit=LIMIT*u.scale*6.6/82;length=0.
            for n in range(len(h)-1,0,-1):
                a,p,v=h[n-1];b,r,w=h[n];seg=np.linalg.norm(p-r)
                if length+seg>limit:
                    f=(limit-length)/max(seg,1e-12);h[:n]=[(b+(a-b)*f,r+(p-r)*f,w+(v-w)*f)];break
                length+=seg
            u.trails[k]=tuple(h)
        out.append((i,u))
    return tuple(out)

def sample(t,center=CENTER,size=SIZE):return tuple(u for _,u in sample_indexed(t,center,size))

class SpecialFormation(old.SpecialFlyby):
    def update(self,t,visible=True,context=None):
        if not self.active:return ()
        t=float(t)
        if not visible or context!=self.context or not math.isfinite(t) or t<self.last or t-self.last>.25 or t-self.start>=END:
            self.reset();return ()
        self.last=t;return sample(t-self.start,self.center,self.size)
