"""Trial121: preserve flight, align lateral trail length with common escort size setting."""
from integrated_trial120 import FleetCombat as Previous, draw_escort_shots, draw_shots, charge, MUZZLE, FORWARD_POINT

class FleetCombat(Previous):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sync_side_lengths()

    def _sync_side_lengths(self):
        self.side_trails[0].max_length = 48.
        for state in self.side_trails[1:]:
            state.max_length = 48. * self.fleet.size_percent / 100.

    def set_size_percent(self, value):
        super().set_size_percent(value)
        self._sync_side_lengths()

    def update_fleet(self,t,xy,scale=1.,bounds=None,visible=True,context=None):
        old=self.fleet.last
        members=super().update_fleet(t,xy,scale,bounds,visible,context)
        new=self.fleet.last
        # Host need not project invisible escorts. Clear their visual histories here.
        if not visible or (old is not None and new is not None and old[2:]!=new[2:]):
            for state in self.side_trails[1:]: state.reset()
            for state in self.jet_states[1:]: state.reset()
        return members
