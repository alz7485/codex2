"""Two existing rear slits and two effect-only lateral anchors at hinge end-face centers."""
from dataclasses import replace
import numpy as np
from nozzle_trial104 import Port,PORTS as LEGACY
from thrust_trial86 import clamp
PORTS=LEGACY[:2]+(Port('side_minus',(-1.035,0,3.16),(-1,0,0),.10,True),Port('side_plus',(1.035,0,3.16),(1,0,0),.10,True))
SIDE={p.group:p for p in PORTS[2:]}
MODELS={'HiNu':'HiNu_Trial119.glb','HiNu_HWS':'HiNu_HWS_Trial119.glb'}

def world_port(m,p,power):
    m=np.asarray(m,float)
    if m.shape!=(4,4) or not np.isfinite(m).all() or not np.isfinite(power):raise ValueError('invalid port transform/power')
    return p,(m@[*p.origin,1])[:3],m[:3,:3]@p.direction,float(clamp(power))

def remap_special(unit,t):
    """Evaluate corrected +/-X jets without adding geometry or changing motion."""
    import special_trial114 as motion
    from special_trial115 import pulse
    from scipy.spatial.transform import Rotation
    import math
    m=unit.transform();out=[]
    for p,o,v,power in unit.thrusters():
        if p.group=='folded_root_preview':
            q=SIDE['side_plus' if p.direction[0]>0 else 'side_minus']
            out.append(world_port(m,Port(p.group,q.origin,q.direction,q.width,True),power));continue
        if p.group not in SIDE:
            out.append((p,o,v,power));continue
        q=SIDE[p.group];a=np.asarray(unit.acceleration,float);vec=m[:3,:3]@q.direction
        power=clamp(-float(a@vec/np.linalg.norm(vec)))
        if motion.FORMATION<=t<motion.FORMATION+motion.MOVE:
            e=t-motion.FORMATION;i=unit.id;d=motion.ARRIVALS[i]
            power=max(power,pulse(e,d))
            f=(e-d-motion.STOP_HOLD)/motion.TURN
            if 0<f<1:
                r0=motion.basis(motion.direction(i,len(motion.ROUTES[i][0])-2),i);r1=motion.basis(motion.AIM,i)
                rot=Rotation.from_matrix(r0.T@r1).as_rotvec()
                y=float(rot[1])/max(1e-12,float(np.linalg.norm(rot)))
                w=.82*math.sin(math.pi*f)**.65*(.18+.82*max(0.,-q.direction[0]*y))
                power=max(power,w)
        out.append(world_port(m,q,power))
    return tuple(out)

def normal_ports(m,rear_power,world_acceleration=(0,0,0),gain=1.):
    """Use existing flight power for rear pair; lateral acceleration is independent of rear power.
    world_acceleration is normalized by caller (visual control, not force)."""
    a=np.asarray(world_acceleration,float)
    if a.shape!=(3,) or not np.isfinite(a).all() or not np.isfinite(gain) or gain<0:raise ValueError('invalid acceleration')
    out=[]
    for i,p in enumerate(PORTS):
        _,o,v,_=world_port(m,p,0.)
        n=np.linalg.norm(v)
        if n<1e-9:raise ValueError('degenerate nozzle transform')
        power=rear_power if i<2 else -float(a@v/n)*gain
        out.append(world_port(m,p,power))
    return tuple(out)

def project_ports(ports,m,project):
    """Return individual power + (anchor, projected jet vector, transverse half-width).
    project takes a world point and returns XY; width must be perpendicular to jet."""
    m=np.asarray(m,float);out=[]
    for p,o,v,power in ports:
        a=np.asarray(project(o),float)[:2];d=np.asarray(project(o+v),float)[:2]-a
        n=np.linalg.norm(d)
        if n<1e-8:continue
        normal=np.array([-d[1],d[0]])/n
        axes=(0,1) if p.group=='rear' else (1,2)
        widths=(p.width,.013 if p.group=='rear' else .055 if p.group.startswith('side_') else .055)
        width=sum(abs(float((np.asarray(project(o+m[:3,k]*w))[:2]-a)@normal)) for k,w in zip(axes,widths))
        out.append((p,float(power),(tuple(a),tuple(d),max(.65,width))))
    return tuple(out)

class NormalJetState:
    """One per main or escort unit. Derive visual lateral acceleration from cursor motion.
    Existing rear trails and firing state remain untouched. Reset on hide/teleport/context change."""
    def __init__(self):self.reset()
    def reset(self):self.last=None;self.velocity=np.zeros(2);self.acc=np.zeros(2)
    def update(self,t,xy,m,rear_power,right,up,*,enabled=True,context=None):
        xy=np.asarray(xy,float);right=np.asarray(right,float);up=np.asarray(up,float)
        if xy.shape!=(2,) or right.shape!=(3,) or up.shape!=(3,) or not np.isfinite(np.r_[t,xy,right,up,rear_power]).all():raise ValueError('invalid flight input')
        old=self.last
        if not enabled or old is None or t<old[0] or t-old[0]>.25 or np.linalg.norm(xy-old[1])>500 or context!=old[2] or (t==old[0] and not np.array_equal(xy,old[1])):
            self.reset();old=None
        if not enabled:return normal_ports(m,0.)
        if old is not None and t>old[0]:
            dt=t-old[0];raw=(xy-old[1])/dt;mix=1-np.exp(-dt/.055);newv=self.velocity+mix*(raw-self.velocity);acc=(newv-self.velocity)/dt;self.velocity=newv;self.acc+=(1-np.exp(-dt/.045))*(acc-self.acc)
        self.last=(t,xy.copy(),context)
        a=(right*self.acc[0]-up*self.acc[1])/2200.
        return normal_ports(m,rear_power,a)
