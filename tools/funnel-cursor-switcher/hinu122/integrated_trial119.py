"""Normal-flight nozzle adapter for the existing Trial101 fleet controller.
The host calls visual_jets after update/update_fleet and obtaining each render matrix.
No OS hooks and no changes to the movement or firing state.
"""
from integrated_trial101 import FleetCombat as Previous,draw_escort_shots,draw_shots,charge,MUZZLE,FORWARD_POINT
from nozzle_trial119 import NormalJetState,project_ports
class FleetCombat(Previous):
    def __init__(self,*args,**kwargs):
        self.jet_states=[NormalJetState() for _ in range(4)];super().__init__(*args,**kwargs)
    def reset(self):
        super().reset()
        for j in self.jet_states:j.reset()
    def set_count(self,count):
        old=self.fleet.count;super().set_count(count)
        if old!=count:
            for j in self.jet_states[1:]:j.reset()
    def set_size_percent(self,value):
        old=self.fleet.size_percent;super().set_size_percent(value)
        if old!=value:
            for j in self.jet_states[1:]:j.reset()
    def visual_jets(self,index,t,xy,m,rear_power,right,up,project,*,enabled=True,context=None):
        if type(index) is not int or not 0<=index<4:raise ValueError('invalid unit index')
        enabled=enabled and index<=self.fleet.count
        ports=self.jet_states[index].update(t,xy,m,rear_power,right,up,enabled=enabled,context=context)
        return project_ports(ports,m,project)
