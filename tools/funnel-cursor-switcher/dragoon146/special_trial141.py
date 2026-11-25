"""Trial140 launch followed by eight independent high-speed flybys.
Positions are projected screen coordinates, with depth-layered 3D models and
perspective-like size changes. No Windows host dependency.
"""
import math
import numpy as np
import special_trial140 as launch
from flight_trial135 import Frame, Jet, PORTS, pose_matrix, screen, LIFE, LIMIT, angle_delta
CENTER=launch.CENTER; SIZE=launch.SIZE; REENTRY=2.52; END=4.62
BRAKE=.045; STOP=.065; TURN=.15; ACCEL=.09
# start time relative to REENTRY, start/end or start/stop/end, depth, axial roll
ROUTES=(
 (0.,((-190,72),(830,300)),-390,.12),
 (.09,((810,25),(-200,262)),185,-.22),
 (.19,((80,-185),(555,565)),-225,.22),
 (.27,((850,355),(-210,85)),255,.32),
 (.36,((-190,325),(208,172),(118,-210)),-105,-.18),
 (.45,((490,570),(380,222),(850,140)),105,.16),
 (.60,((675,-190),(58,575)),-480,-.25),
 (.72,((-220,192),(850,83)),0,.18),
)

def heading(d):return math.atan2(-d[1],d[0])
def smooth(x):return launch.smooth(x)
def motion(i,t):
    delay,pts,z,roll=ROUTES[i];u=t-REENTRY-delay;p=np.asarray(pts,float); v0=p[1]-p[0];dist=np.linalg.norm(v0);d=v0/dist
    speed=960. if len(p)==2 else 890.; h=heading(d); endtime=dist/speed
    if u<0:return None
    if len(p)==2:
        if u>=endtime:return None
        return p[0]+d*speed*u,h,roll,speed,1.,np.zeros(2),False
    # Brake to a complete stop at the corner, hold, rotate in place, then accelerate.
    cruise=endtime-BRAKE/2; stop_t=cruise+BRAKE; turn_t=stop_t+STOP; go_t=turn_t+TURN
    d2=p[2]-p[1];dist2=np.linalg.norm(d2);d2/=dist2;h2=heading(d2);ang=angle_delta(h,h2)
    if u<cruise:return p[0]+d*speed*u,h,roll,speed,1.,np.zeros(2),False
    if u<stop_t:
        x=u-cruise;f=x/BRAKE
        return p[1]-d*(speed*BRAKE/2-speed*x+speed*x*x/(2*BRAKE)),h,roll*(1-f),speed*(1-f),1-f,-d*speed/BRAKE,False
    if u<turn_t:return p[1],h,0.,0.,0.,np.zeros(2),True
    if u<go_t:
        f=(u-turn_t)/TURN;return p[1],h+ang*smooth(f),.19*math.sin(math.pi*f)*np.sign(ang),0.,0.,np.zeros(2),True
    x=u-go_t;a=min(x,ACCEL);travel=speed*(a*a/(2*ACCEL)+max(0,x-ACCEL))
    if travel>=dist2:return None
    return p[1]+d2*travel,h2,roll*smooth(x/ACCEL),speed*min(1,x/ACCEL),smooth(x/ACCEL),d2*speed/ACCEL if x<ACCEL else np.zeros(2),False

def raw(i,t,center,size):
    q=motion(i,t)
    if q is None:return None
    p,h,b,v,rear,a,still=q;depth=ROUTES[i][2];factor=size/SIZE
    # Distances are separate layers in the preview, and size follows a pinhole scale law.
    scale=size/6.6*800/(800-depth);p=np.asarray(center)+(p-np.asarray(CENTER))*factor
    R=pose_matrix(h,b,0.);tr=np.array([p[0],-p[1],depth*factor]);jets=[]
    for k,(o,d,w) in PORTS.items():
        direction=R@d
        # No fictitious reverse jet. During stationary yaw use one short side pulse.
        power=rear if k=='rear' else min(1.,max(0.,-np.dot(a,screen(direction))/4500))
        if still and k!='rear':
            dt=.001;prev=motion(i,t-dt)
            rate=0 if prev is None else angle_delta(prev[1],h)/dt
            power=max(power,min(.7,max(0.,rate*(1 if k=='left' else -1)/18)))
        jets.append(Jet(k,tr+scale*(R@o),direction,power,w*scale))
    return Frame(t,True,R,tr,scale,v*factor,h,b,0.,tuple(jets),{k:() for k in PORTS})

def sample_indexed(t,center=CENTER,size=SIZE):
    t=float(t);size=float(size);center=np.asarray(center,float)
    if not math.isfinite(t) or center.shape!=(2,) or not np.isfinite(center).all() or not math.isfinite(size) or not 1<=size<=1024:raise ValueError('invalid input')
    if t<launch.END:return tuple(enumerate(launch.sample(t,center,size)))
    if t<REENTRY or t>=END:return ()
    out=[]
    for i in range(8):
        u=raw(i,t,center,size)
        if u is None:continue
        hist={k:[] for k in PORTS}
        for q in np.linspace(max(REENTRY,t-LIFE+1e-6),t,12):
            old=raw(i,q,center,size)
            if old is None or old.speed<8:continue
            for j in old.jets:
                h=hist[j.name];p=screen(j.origin)
                if j.power>.045 and (not h or np.linalg.norm(p-h[-1][1])>1.2):h.append((float(q),p,j.power))
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

def sample(t,center=CENTER,size=SIZE):
    """Compact display list. Use sample_indexed for persistent unit identity."""
    return tuple(u for _,u in sample_indexed(t,center,size))

class SpecialFlyby(launch.SpecialLaunch):
    def update(self,t,visible=True,context=None):
        if not self.active:return ()
        t=float(t)
        if not visible or context!=self.context or not math.isfinite(t) or t<self.last or t-self.last>.25 or t-self.start>=END:
            self.reset();return ()
        self.last=t;return sample(t-self.start,self.center,self.size)
