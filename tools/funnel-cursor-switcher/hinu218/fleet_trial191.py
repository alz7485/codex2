"""Trial191 escort lifecycle guard; preserve Trial190 flight and pulse."""
import math
from .pulse_trial190 import FleetCombat as Previous, draw_shots, draw_escort_shots, charge, MUZZLE, FORWARD_POINT

class FleetCombat(Previous):
    def _clear_escort_visuals(self):
        self.escort_fire.reset(self.fire.fired)
        self._clear_aim()
        self._clear_escort_tracks()
        for state in self.side_trails[1:]: state.reset()
        for state in self.jet_states[1:]: state.reset()
        for state in self.fleet.trails: state.reset()

    def update_fleet(self,t,xy,scale=1.,bounds=None,visible=True,context=None):
        old=self.fleet.last
        # Let the original controller validate inputs and calculate positions first.
        members=super().update_fleet(t,xy,scale,bounds,visible,context)
        new=self.fleet.last
        if not visible or not self.fleet.count or (old is not None and new != old and (
            new is None or t<=old[0] or t-old[0]>.25 or math.dist(xy,old[1])>500 or new[2:]!=old[2:])):
            self._clear_escort_visuals()
        return members
