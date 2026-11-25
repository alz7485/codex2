"""Trial146 RGB reference compositor. Input image is never mutated.
Skip inactive effect passes; retain original layer ordering and active renderers.
Not an OS overlay or a depth-aware compositor.
"""
from effects_trial135 import draw_effects
from combat_effects137 import draw_combat
from combat_effects145 import draw_volley


def compose(base, states, *, special=False):
    if base.mode != 'RGB':
        raise ValueError('RGB canvas required')
    result = base
    shooter = draw_volley if special else draw_combat
    for state in states:
        f = state.flight
        if not f.visible:
            continue
        if any(j.power >= .025 for j in f.jets) or any(len(h)>1 for h in f.trails.values()):
            result = draw_effects(result, f)
        if state.charging or state.shot is not None:
            result = shooter(result, state)
    return result.copy() if result is base else result
