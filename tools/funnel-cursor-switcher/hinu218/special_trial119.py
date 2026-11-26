"""Trial117 choreography, effect-only hinge-end anchors. Old units are delegated unchanged."""
from . import special_trial117 as old
from .special_trial117 import END,phase,camera_pose,material_emission,trail_gain,residual,shot_matrix,SHOT,FORMATION,REENTRY,BASE_END
from .nozzle_trial119 import remap_special
class UnitView:
    def __init__(self,unit,t):self.unit=unit;self.t=t
    def __getattr__(self,name):return getattr(self.unit,name)
    def thrusters(self):return remap_special(self.unit,self.t)
def sample(t):return tuple(UnitView(u,t) for u in old.sample(t))
class SpecialVolley(old.SpecialVolley):
    def update(self,t,*args,**kwargs):
        units=super().update(t,*args,**kwargs)
        return tuple(UnitView(u,t-self.start) for u in units) if units else ()
