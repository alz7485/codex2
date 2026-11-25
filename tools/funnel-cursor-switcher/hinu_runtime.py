"""Trial122 bridge to the shared preview and transparent Windows overlay."""

from pathlib import Path
import sys

from PIL import Image
from cursor_art import anchors, load_sprite
from effect_settings import BUTTONS, MODIFIERS
from idle_motion import MOTION
from trial_runtime import TrialDisplay

NAMES = {"Hi-νガンダム": "HiNu", "Hi-νガンダムHWS": "HiNu_HWS"}


class HiNuDisplay(TrialDisplay):
    def __init__(self, path, config):
        root = Path(__file__).parent / "hinu122"
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from runtime_render import Renderer, FleetCombat, SpecialVolley

        self.config = config
        self.special = "volley"
        self.pos = None
        self.hot = anchors(load_sprite(path), path)[0]
        self.frame_origin = (0, 0)
        self.renderer = Renderer(NAMES[path.stem])
        self.renderer.draw_beams = False
        f, idle = config["followers"], config["idle"]
        self.control = FleetCombat(
            f["count"] if f["enabled"] else 0,
            f["size_percent"],
            idle_enabled=idle["enabled"] and idle["motion"] == MOTION,
            escort_fire_enabled=f["fire_enabled"],
        )
        self.control.idle_motion.delay = idle["delay"]
        self.control.idle_motion.period = idle["turn_period"] * (
            -1 if idle["turn_direction"] == "逆回転" else 1
        )
        self.volley = SpecialVolley()
        self.context = None
        self.render_origin = None

    def reset(self):
        self.control.reset()
        self.volley.reset()
        self.pos = None
        self.render_origin = None

    def cancel_fire(self):
        self.control.fire.reset()
        self.control.escort_fire.reset()

    def close(self):
        self.renderer.close()

    def step(self, pos, now, events, viewport, scale=1, show_primary=True):
        if pos is None:
            self.reset()
            return None
        left, top, right, bottom = viewport
        context = (viewport, scale)
        if context != self.context:
            self.reset()
            self.context = context
        self.pos = pos
        self.renderer.scale = scale
        opts = self.config[self.special]
        for e in events:
            button = "left" if e.kind == "double" else e.kind
            if (
                opts["enabled"]
                and button == BUTTONS[opts["button"]]
                and e.modifiers == MODIFIERS[opts["modifiers"]]
            ):
                if self.volley.trigger(now, context):
                    self.control.reset()
            elif opts["click_fire_enabled"] and not self.volley.active:
                if button == "left":
                    self.control.down(now)
                elif button == "left_up":
                    self.control.up(now)
        units = self.volley.update(now, context=context)
        if self.volley.active:
            # The choreography uses its own perspective camera and preserves its aspect ratio.
            width = min(right - left, round(720 * scale))
            height = min(bottom - top, round(720 * scale))
            image = self.renderer.special(now - self.volley.start, (width, height))
            origin = (
                left + (right - left - width) // 2,
                top + (bottom - top - height) // 2,
            )
        else:
            side = round(480 * scale)
            origin = (round(pos[0] - side / 2), round(pos[1] - side / 2))
            if self.render_origin is not None:
                rebase_projected(
                    self.control,
                    (
                        self.render_origin[0] - origin[0],
                        self.render_origin[1] - origin[1],
                    ),
                )
            self.render_origin = origin
            self.renderer.screen_origin = origin
            image = self.renderer.normal(
                self.control,
                now,
                pos,
                (side, side),
                viewport,
                opts["orientation_mode"] == "fixed_upper_left",
                context,
            )
        if not self.volley.active and (
            self.control.shots or any(self.control.escort_fire.shots)
        ):
            from dataclasses import replace
            from runtime_render import draw_shots, draw_escort_shots

            dx, dy = origin[0] - left, origin[1] - top

            def shift(shot):
                p, direction = shot.anchor
                return replace(
                    shot, anchor=((p[0] + dx, p[1] + dy), direction), depth=None
                )

            rays = Image.new("RGBA", (right - left, bottom - top))
            rays = draw_shots(
                rays,
                now,
                [shift(s) for s in self.control.shots],
                0.3 * scale,
                self.renderer.kind,
            )
            for shots in self.control.escort_fire.shots:
                rays = draw_escort_shots(
                    rays,
                    now,
                    [replace(s, shot=shift(s.shot)) for s in shots],
                    self.renderer.kind,
                )
            rays.alpha_composite(image, (dx, dy))
            image = rays
            origin = (left, top)
        box = image.getbbox()
        if box:
            self.frame_origin = origin[0] + box[0], origin[1] + box[1]
            return image.crop(box)
        return None


def rebase_projected(control, delta):
    """Translate cached image coordinates while leaving world-space flight state intact."""
    from dataclasses import replace

    def point(p):
        return (p[0] + delta[0], p[1] + delta[1])

    trails = [control.trail, *control.fleet.trails, *control.side_trails]
    for trail in trails:
        for track in trail.tracks:
            values = [
                replace(s, xy=point(s.xy)) if s is not None else None for s in track
            ]
            track.clear()
            track.extend(values)

    def shot(s):
        return replace(s, anchor=(point(s.anchor[0]), s.anchor[1]))

    control.shots = [shot(s) for s in control.shots]
    control.escort_fire.shots = [
        [replace(s, shot=shot(s.shot)) for s in shots]
        for shots in control.escort_fire.shots
    ]
