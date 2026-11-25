"""Per-unit lateral trail history; existing control untouched."""
from integrated_trial119 import FleetCombat as Previous,draw_escort_shots,draw_shots,charge,MUZZLE,FORWARD_POINT
from effects_trial120 import SideTrails
class FleetCombat(Previous):
    def __init__(self,*args,**kwargs):
        self.side_trails=[SideTrails() for _ in range(4)];super().__init__(*args,**kwargs)
    def reset(self):
        super().reset()
        for s in self.side_trails:s.reset()
    def set_count(self,count):
        old=self.fleet.count;super().set_count(count)
        if old!=count:
            for s in self.side_trails[1:]:s.reset()
    def set_size_percent(self,value):
        old=self.fleet.size_percent;super().set_size_percent(value)
        if old!=value:
            for s in self.side_trails[1:]:s.reset()
    def visual_jets(self,index,t,xy,m,rear_power,right,up,project,*,enabled=True,context=None):
        jets=super().visual_jets(index,t,xy,m,rear_power,right,up,project,enabled=enabled,context=context)
        self.side_trails[index].update(t,xy,jets,enabled=enabled and index<=self.fleet.count,context=context)
        return jets
