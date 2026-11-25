"""Independent primary and escort states. Existing click API is unchanged."""
from combat_trial96 import Combat
from escort_trial98 import EscortFleet
class FleetCombat(Combat):
    def __init__(self,count=0,size_percent=100):
        super().__init__();self.fleet=EscortFleet(count,size_percent)
    def reset(self):
        super().reset()
        if hasattr(self,'fleet'):self.fleet.reset()
    def set_count(self,count):self.fleet.set_count(count)
    def set_size_percent(self,value):self.fleet.set_size_percent(value)
    def update_fleet(self,t,xy,scale=1.,bounds=None,visible=True,context=None):
        return self.fleet.update(t,xy,scale,bounds,visible,context)
