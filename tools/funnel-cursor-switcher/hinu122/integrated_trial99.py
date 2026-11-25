"""Trial98 API plus explicit idle visual transform state for the renderer."""
from integrated_trial98 import FleetCombat as Previous
from idle_trial99 import IdleMotion,IdleVisual
class FleetCombat(Previous):
    def __init__(self,count=0,size_percent=100,*,idle_enabled=True):
        if type(idle_enabled) is not bool:raise ValueError('idle_enabled must be bool')
        self.idle_enabled=idle_enabled;self.idle_motion=IdleMotion();self.primary_visual=IdleVisual();super().__init__(count,size_percent)
    def reset(self):
        super().reset();self.idle_motion.reset();self.primary_visual=IdleVisual()
    def set_idle_enabled(self,value):
        if type(value) is not bool:raise ValueError('idle_enabled must be bool')
        self.idle_enabled=value
    def update(self,t,xy,enabled=True,context=None,fixed=False):
        p=super().update(t,xy,enabled,context,fixed)
        busy=p.fire.stage!='idle' or bool(self.fire.queue) or bool(self.shots)
        self.primary_visual=self.idle_motion.update(t,xy,busy=busy,visible=enabled,enabled=self.idle_enabled,context=(context,bool(fixed)))
        return p
    def escort_visual(self,member):return self.idle_motion.escort(member.id)
