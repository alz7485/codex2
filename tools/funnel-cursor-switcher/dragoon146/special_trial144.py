"""Eight-unit fictional special volley. Prior flight unchanged; fixed projected depth layers."""
import math
from dataclasses import replace
import numpy as np
import special_trial143 as old
from flight_trial135 import PORTS, Jet, pose_matrix, screen, angle_delta, LIFE, LIMIT, clip
from combat_trial137 import CombatFrame, Shot, BEAM_ORIGIN, BEAM_AXIS, SHOT_TIME
CENTER=old.CENTER; SIZE=old.SIZE
CHARGE=old.END; CHARGE_TIME=.68; FIRE=CHARGE+CHARGE_TIME
DEPART=FIRE+SHOT_TIME+.10; STAGGER=.045; TURN=.14; ACCEL=.075; SPEED=2400.; TRAVEL=.55
ORDER=(0,1,2,3,4,5,6,7)
HEADINGS=tuple(map(math.radians,(150,110,55,190,235,5,275,320)))
END=DEPART+7*STAGGER+TURN+ACCEL+TRAVEL+.12

def departure_times(i):
    start=DEPART+ORDER.index(i)*STAGGER
    return start,start+TURN,start+TURN+ACCEL,start+TURN+ACCEL+TRAVEL

def raw(i,t,center=CENTER,size=SIZE):
    f=old.raw(i,max(old.READY,t),center,size)
    start,go,cruise,finish=departure_times(i)
    if t>=finish:return None
    if t<start:return replace(f,t=t)
    fac=size/SIZE; h0=old.FIRE_HEADING; h1=HEADINGS[i]; delta=angle_delta(h0,h1)
    p=f.translation.copy(); v=0.; rate=0.; rear=0.
    if t<go:
        u=clip((t-start)/TURN); ease=u*u*(3-2*u); h=h0+delta*ease
        b=old.FIRE_BANK*(1-ease); pitch=old.FIRE_PITCH*(1-ease); rate=delta*6*u*(1-u)/TURN
    else:
        h=h1; b=0.;pitch=0.; age=t-go; a=min(age,ACCEL)
        dist=SPEED*(.5*a*a/ACCEL+max(0.,age-ACCEL)); v=SPEED*min(1.,age/ACCEL);rear=v/SPEED
        p+=np.array([math.cos(h),math.sin(h),0.])*dist*fac
    R=pose_matrix(h,b,pitch)
    jets=tuple(Jet(k,p+f.scale*(R@o),R@d,rear if k=='rear' else min(.7,max(0.,rate*(1 if k=='left' else -1)/18)),w*f.scale) for k,(o,d,w) in PORTS.items())
    return replace(f,t=t,matrix=R,translation=p,speed=v*fac,heading=h,bank=b,pitch=pitch,jets=jets,trails={k:() for k in PORTS})

def sample_combat_indexed(t,center=CENTER,size=SIZE):
    t=float(t);size=float(size);center=np.asarray(center,float)
    if not math.isfinite(t) or center.shape!=(2,) or not np.isfinite(center).all() or not math.isfinite(size) or not 1<=size<=1024:raise ValueError('invalid input')
    if t<CHARGE:return tuple((i,CombatFrame(f,0.,False,None,0,0.)) for i,f in old.sample_indexed(t,center,size))
    if t>=END:return ()
    out=[]
    for i in range(8):
        f=raw(i,t,center,size)
        if f is None:continue
        charging=t<FIRE; q=clip((t-CHARGE)/CHARGE_TIME) if charging else 0.
        shot=None
        if FIRE<=t<FIRE+SHOT_TIME:
            origin=old.raw(i,old.READY,center,size)
            shot=Shot(FIRE,tuple(origin.world(BEAM_ORIGIN)),tuple(origin.matrix@BEAM_AXIS),1.,origin.scale)
        if t>=DEPART:
            hist={k:[] for k in PORTS};go=departure_times(i)[1]
            if t>go:
                for z in np.linspace(max(go,t-LIFE+1e-6),t,12):
                    prev=raw(i,z,center,size)
                    if prev is None or prev.speed<8:continue
                    for j in prev.jets:
                        p=screen(j.origin); h=hist[j.name]
                        if j.power>.045 and (not h or np.linalg.norm(p-h[-1][1])>1.2*size/SIZE):h.append((float(z),p,j.power))
                for k,h in hist.items():
                    limit=LIMIT*f.scale*6.6/82;length=0.
                    for n in range(len(h)-1,0,-1):
                        a,p,v=h[n-1];b,r,w=h[n];seg=np.linalg.norm(p-r)
                        if length+seg>limit:
                            u=(limit-length)/max(seg,1e-12);h[:n]=[(b+(a-b)*u,r+(p-r)*u,w+(v-w)*u)];break
                        length+=seg
                    f.trails[k]=tuple(h)
        out.append((i,CombatFrame(f,q,charging,shot,0,0.)))
    return tuple(out)

def sample_indexed(t,center=CENTER,size=SIZE):return tuple((i,c.flight) for i,c in sample_combat_indexed(t,center,size))
def sample(t,center=CENTER,size=SIZE):return tuple(f for _,f in sample_indexed(t,center,size))

class SpecialVolley(old.SpecialFormation):
    """Returns indexed CombatFrame tuples; host uses stable IDs and both FX renderers."""
    def update(self,t,visible=True,context=None):
        if not self.active:return ()
        t=float(t)
        if not visible or context!=self.context or not math.isfinite(t) or t<self.last or t-self.last>.25 or t-self.start>=END:
            self.reset();return ()
        self.last=t;return sample_combat_indexed(t-self.start,self.center,self.size)
