"""Special-only camera framing and local material glow; no motion modifications."""
import math
from dataclasses import dataclass
from special_trial115 import FORMATION, sample, phase, SpecialVolley, SHOT, END, CAMERA_Z, MOVE, shot_matrix, trail_gain
from thrust_trial86 import smooth

@dataclass(frozen=True)
class CameraPose:
    x:float=0.
    y:float=0.
    z:float=CAMERA_Z
    fov:float=34.

# Camera fixed before first arrival (0.43s); no camera drift during stop/turn/charge.
CAMERA_RAMP=.30
FINAL=CameraPose(1.25,-1.,29.,45.)

def camera_pose(t):
    if not math.isfinite(t):raise ValueError('invalid time')
    q=smooth((t-FORMATION)/CAMERA_RAMP)
    return CameraPose(FINAL.x*q,FINAL.y*q,CAMERA_Z+(FINAL.z-CAMERA_Z)*q,34+(FINAL.fov-34)*q)

# Material emission is a stylized approximation to local light spill, not a light transport solve.
# Explicitly avoid applying tint to exterior armor, hinge covers or nozzle materials.
SPILL={'Inset bevel • gunmetal':.14,'Trial59 dark':.085,'Trial59 steel':.075,'Deep recess':.10,'Blue-black • internal frame':.12,'T82 recessed energy core':.19,'T83 machined aperture bevel':.12}

def material_emission(name,baseline,kind,fire):
    q=fire.charge if fire.stage=='charge' else .5*max(0.,1-fire.age/.145) if fire.stage=='fire' else 0.
    rgb=(.24,.58,1.) if kind=='HiNu' else (.64,.31,1.)
    amount=SPILL.get(name,0.)*q*q
    return tuple(min(1.,v+amount*c) for v,c in zip(baseline,rgb))
