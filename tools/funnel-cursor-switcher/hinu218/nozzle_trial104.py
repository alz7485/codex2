"""Three-direction visual thruster layout. Rear pair measured, side ports provisional."""
from dataclasses import dataclass
import numpy as np
@dataclass(frozen=True)
class Port:
    group:str; origin:tuple; direction:tuple; width:float; provisional:bool=False
PORTS=(Port('rear',(0,-.105,3.576),(0,0,1),.129),Port('rear',(0,.105,3.576),(0,0,1),.129),Port('side_minus',(0,-.508,3.29),(0,-1,0),.10,True),Port('side_plus',(0,.508,3.29),(0,1,0),.10,True))
def resolve(transform, acceleration, gain=1.):
    m=np.asarray(transform,float);a=np.asarray(acceleration,float)
    if m.shape!=(4,4) or a.shape!=(3,) or not np.isfinite(m).all() or not np.isfinite(a).all() or not np.isfinite(gain) or gain<0:raise ValueError('invalid thrust input')
    out=[]
    for p in PORTS:
        v=m[:3,:3]@p.direction;norm=np.linalg.norm(v)
        if norm<1e-9:raise ValueError('degenerate transform')
        power=float(np.clip(-np.dot(a,v/norm)*gain,0,1));origin=(m@[*p.origin,1])[:3]
        out.append((p,origin,v,power))
    return tuple(out)
