"""Persistent settings adapter for Trial100; bind one common escort-fire checkbox."""
from dataclasses import dataclass
import json
from .escort_settings_trial98 import EscortSettings as Previous

@dataclass(frozen=True)
class EscortSettings(Previous):
    fire_enabled: bool = True

    def __post_init__(self):
        super().__post_init__()
        if type(self.fire_enabled) is not bool:
            raise ValueError('escort_fire_enabled must be bool')

    @classmethod
    def from_json(cls, data):
        v = json.loads(data)
        if not isinstance(v, dict):
            raise ValueError('settings object expected')
        return cls(v.get('escort_count', 0), v.get('escort_size_percent', 100),
                   v.get('escort_fire_enabled', True))

    def to_json(self):
        return json.dumps({'escort_count': self.count,
                           'escort_size_percent': self.size_percent,
                           'escort_fire_enabled': self.fire_enabled}, indent=2)

    def apply(self, controller):
        super().apply(controller)
        controller.set_escort_fire_enabled(self.fire_enabled)
