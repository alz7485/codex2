"""Pure pose controller: -Z is nose. Time in seconds, angles in radians."""
import numpy as np
import trimesh as tm
DURATION=.72
SLIDE_PREFIX=('front_gold_shell','nose_dark_cap','forward_ridge','forward_rail','front_vent')
HINGE_PREFIX=('rear_hinged_armor','rear_ridge')
def smooth(x):
    x=float(np.clip(x,0,1));return x*x*(3-2*x)
def pose(t):
    return smooth((t-.05)/.34), smooth((t-.17)/.42), smooth((t-.22)/.45)
def transform(name,t):
    slide,upper,lower=pose(t)
    if name.startswith(SLIDE_PREFIX):return tm.transformations.translation_matrix([0,0,-.38*slide])
    if name.startswith(HINGE_PREFIX):
        s=int(name.rsplit('_',1)[1]);base=.43 if s==1 else -.22;angle=.58*upper if s==1 else .48*lower
        return tm.transformations.rotation_matrix(-s*angle,[1,0,0],point=[0,base,1.04])
    return np.eye(4)
def tip(t):return np.array([0,-.14,-3.02-.38*pose(t)[0]])
def anchored_transform(name,t):
    return tm.transformations.translation_matrix(-tip(t))@transform(name,t)
