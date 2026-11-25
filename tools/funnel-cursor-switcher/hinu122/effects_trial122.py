"""Trial122: skip empty lateral-trail layers; preserve RGBA copy contract."""
from effects_trial120 import SideTrails, draw_exhaust, draw_side_trails as _draw

def draw_side_trails(background,t,controller):
    # A track without two consecutive samples cannot draw a line.
    if not any(a is not None and b is not None for tr in controller.tracks for a,b in zip(tr,list(tr)[1:])):
        return background.convert('RGBA').copy()
    return _draw(background,t,controller)
