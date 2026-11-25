"""Host settings adapter. UI should expose one integer percent control."""
from dataclasses import dataclass
import json
from escort_trial98 import EscortFleet
@dataclass(frozen=True)
class EscortSettings:
    count:int=0
    size_percent:int=100
    def __post_init__(self):
        if type(self.count) is not int or not 0<=self.count<=3:raise ValueError('count must be 0..3')
        EscortFleet.validate_size(self.size_percent)
    @classmethod
    def from_json(cls, data):
        v=json.loads(data)
        if not isinstance(v,dict):raise ValueError('settings object expected')
        return cls(v.get('escort_count',0),v.get('escort_size_percent',100))
    def to_json(self):
        return json.dumps({'escort_count':self.count,'escort_size_percent':self.size_percent},indent=2)
    def apply(self, fleet):
        fleet.set_count(self.count)
        fleet.set_size_percent(self.size_percent)
