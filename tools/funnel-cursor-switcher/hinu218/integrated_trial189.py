"""Hi-Nu normal flight visual update; existing input, fire, idle and flight physics retained."""
from .integrated_trial121 import FleetCombat as Previous, draw_escort_shots, draw_shots, charge, MUZZLE, FORWARD_POINT
from .effects_trial189 import SideTrails, rear_trail
class FleetCombat(Previous):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.trail=rear_trail()
        self.side_trails=[SideTrails() for _ in range(4)]
        self._rebuild_escort_trails()
    def _rebuild_escort_trails(self):
        m=self.fleet.multiplier
        self.fleet.trails=[rear_trail(m) for _ in range(self.fleet.count)]
        self.side_trails[1:]=[SideTrails(m) for _ in range(3)]
    def set_count(self,count):
        old=self.fleet.count;super().set_count(count)
        if old!=count:self._rebuild_escort_trails()
    def set_size_percent(self,value):
        old=self.fleet.size_percent;super().set_size_percent(value)
        if old!=value:self._rebuild_escort_trails()
