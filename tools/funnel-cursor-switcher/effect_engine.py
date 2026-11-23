"""One input sample and one transparent frame for both Windows and the editor."""

import math
import random
from collections import deque
from dataclasses import dataclass

from PIL import Image, ImageColor, ImageDraw

from cursor_art import NOZZLES, OVERLAY_SIZE, anchors

from effect_settings import BUTTONS, MODIFIERS, SPECIAL, special_group
from flight_art import FlightArt
from idle_motion import MOTION, STEPS, idle_sheet, turn_frame

CENTER = OVERLAY_SIZE // 2
TAU = math.tau


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def point(x, y, radius, angle):
    return x + radius * math.cos(angle), y + radius * math.sin(angle)


def box(x, y, r):
    return x - r, y - r, x + r, y + r


def dot(draw, xy, radius, fill):
    draw.ellipse(box(*xy, radius), fill=fill)


def tint(color, opacity):
    return (*color, round(255 * clamp(opacity)))


@dataclass
class ClickEvent:
    kind: str
    pos: tuple
    time: float
    modifiers: int = 0


class ClickTracker:
    def __init__(self, interval=0.5, area=(4, 4)):
        self.interval, self.area = interval, area
        self.previous = None

    def press(self, button, pos, now, modifiers=0):
        last = self.previous
        self.previous = (pos, now) if button == "left" else None
        if button == "left" and last and now - last[1] <= self.interval:
            if all(abs(a - b) <= radius / 2 for a, b, radius in zip(pos, last[0], self.area)):
                self.previous = None
                button = "double"
        return ClickEvent(button, pos, now, modifiers)


class Layer:
    def __init__(self, config, engine):
        self.c, self.e = config, engine
        self.color = self.rgb(config.get("color", "機体色"))

    def rgb(self, value):
        return self.e.colors[0] if value == "機体色" else ImageColor.getrgb(value)

    def ink(self, strength=1):
        return tint(self.color, self.c["opacity"] * strength)


class Boost(Layer):
    def update(self):
        e, c = self.e, self.c
        slow, fast = sorted((c["minimum"], c["maximum"]))
        speed = clamp(e.speed / 1000) * c["response"]
        length = (slow + (fast - slow) * speed) * c["length"]
        blend = 1 - math.exp(-e.dt / (0.001 + 0.08 * c["smoothing"]))
        self.length = getattr(self, "length", length) * (1 - blend) + length * blend
        self.flame = clamp(1 - e.still / 0.075) if e.has_moved else 0
        self.speed = speed
        return self.flame > 0

    def draw(self, frame, draw):
        e, c = self.e, self.c
        ax, ay = e.axis
        nx, ny = -ay, ax
        shapes = {
            "機体別": e.nozzle,
            "単針": "needle",
            "広口": "flare",
            "二連": "twin",
            "扇形": "fan",
            "リボン": "ribbons",
        }
        x0, y0 = e.rear
        strength = self.flame * c["opacity"] * c["intensity"] * (0.68 + 0.32 * self.speed)
        for i, (base, tip, scale, width) in enumerate(NOZZLES[shapes[c["shape"]]]):
            x, y = x0 + nx * base, y0 + ny * base
            reach = self.length * scale * (0.65 + 0.35 * self.flame)
            width *= c["width"] * (0.82 + 0.38 * self.speed)
            color = e.colors[i % len(e.colors)] if c["color"] == "機体色" else self.color
            for ratio, alpha in ((1.8, 0.12), (1.35, 0.32), (1, 0.86), (0.47, 1)):
                w = width * ratio
                fraction = min(1.03, 0.45 + 0.55 * ratio)
                head = x0 + (ax * reach + nx * tip) * fraction, y0 + (ay * reach + ny * tip) * fraction
                ink = tuple((channel + 510) // 3 for channel in color) if ratio < 0.5 else color
                draw.polygon(
                    [(x - nx * w, y - ny * w), head, (x + nx * w, y + ny * w)],
                    fill=tint(ink, strength * alpha),
                )


class Trail(Layer):
    def __init__(self, config, engine):
        super().__init__(config, engine)
        self.samples = deque(maxlen=config["count"])
        self.last = -math.inf

    def update(self):
        e, c = self.e, self.c
        if e.moved and e.now - self.last >= c["interval"] / 1000:
            speed = clamp(e.speed / 950)
            life = c["duration"] / 1000 * (1 - c["response"] * (1 - speed) * 0.48)
            self.samples.append((e.pos, e.now, life, e.heading))
            self.last = e.now
        while self.samples and e.now - self.samples[0][1] >= self.samples[0][2]:
            self.samples.popleft()
        return bool(self.samples)

    def draw(self, frame, draw):
        e, c = self.e, self.c
        previous = None
        last_mid = None
        for pos, born, life, heading in list(self.samples)[-max(2, round(len(self.samples) * e.budget)) :]:
            remaining = clamp(1 - (e.now - born) / life)
            x, y = e.local(pos)
            if c["style"] == "残像":
                e.fly(frame, (x, y), heading, int(born * 8) % 4, 30, remaining * c["opacity"] * 0.46)
                continue
            x += e.rear[0] - CENTER + e.axis[0] * 12
            y += e.rear[1] - CENTER + e.axis[1] * 12
            width = max(1, round(c["width"] * remaining))
            ink = self.ink(remaining * 0.63)
            if previous and math.dist(previous, (x, y)) <= 90:
                px, py = previous
                if c["style"] == "ワイヤー":
                    middle = (px + x) / 2, (py + y) / 2 + min(7, abs(x - px) * 0.22)
                    draw.line([previous, middle, (x, y)], fill=ink, width=width)
                elif c["style"] == "曲線":
                    # Quadratic segment between successive midpoints through the sample.
                    mid = (px + x) / 2, (py + y) / 2
                    start = last_mid if last_mid is not None else previous
                    curve = [
                        (
                            (1 - t) ** 2 * start[0] + 2 * t * (1 - t) * px + t * t * mid[0],
                            (1 - t) ** 2 * start[1] + 2 * t * (1 - t) * py + t * t * mid[1],
                        )
                        for t in (0, 0.25, 0.5, 0.75, 1)
                    ]
                    draw.line(curve, fill=ink, width=width)
                    last_mid = mid
                elif c["style"] == "直線":
                    draw.line([previous, (x, y)], fill=ink, width=width)
            else:
                last_mid = None
            dot(draw, (x, y), width / 2, ink)
            previous = x, y


class Click(Layer):
    def __init__(self, config, engine):
        super().__init__(config, engine)
        self.events = deque(maxlen=20)

    def update(self):
        for event in self.e.clicks:
            if event.kind == "double":
                for old in reversed(self.events):
                    if old.kind == "left":
                        self.events.remove(old)
                        break
            self.events.append(event)
        while self.events and self.e.now - self.events[0].time >= self.c["duration"] / 1000:
            self.events.popleft()
        return bool(self.events)

    def draw(self, frame, draw):
        c, e = self.c, self.e
        for event in self.events:
            x, y = e.local(event.pos)
            t = clamp((e.now - event.time) * 1000 / c["duration"])
            radius = 3 + c["radius"] * (0.2 + c["growth"] * t)
            ink = tint(self.rgb(c[event.kind + "_color"]), c["opacity"] * c["intensity"] * (1 - t))
            style = c[event.kind]
            if style == "光輪":
                draw.ellipse(box(x, y, radius), outline=ink, width=2)
            elif style == "六角形":
                draw.line([point(x, y, radius, i * TAU / 6) for i in range(7)], fill=ink, width=2)
            else:
                for i in range(2 if style == "ビーム" else 8):
                    angle = (i * math.pi if style == "ビーム" else i * TAU / 8) + math.pi / 4
                    draw.line(
                        [point(x, y, radius * 0.42, angle), point(x, y, radius, angle)], fill=ink, width=2
                    )


class Idle(Layer):
    def __init__(self, config, engine):
        super().__init__(config, engine)
        self.level = 0
        self.last_input = -math.inf

    def update(self):
        e, c = self.e, self.c
        if e.clicks:
            self.last_input = e.now
        rest = e.now - max(e.last_motion, self.last_input)
        if e.idle_sheet and c.get("motion") == MOTION and rest >= c["delay"]:
            direction = -1 if c["turn_direction"] == "逆回転" else 1
            e.idle_turn_step = int((rest - c["delay"]) / c["turn_period"] * STEPS * direction) % STEPS
        target = 1 if self.e.still >= self.c["delay"] else 0
        step = self.e.dt * 1000 / self.c["fade"]
        self.level += clamp(target - self.level, -step, step)
        return self.level > 0

    def draw(self, frame, draw):
        c, e = self.c, self.e
        if e.idle_sheet and c.get("motion") == MOTION:
            return
        phase = e.now * TAU / c["period"]
        light = (0.68 + 0.32 * math.sin(phase)) * self.level * c["intensity"]
        x, y = point(*e.rear, c["drift"], phase)
        for r, a in ((6, 0.12), (4, 0.28), (2, 0.85)):
            dot(draw, (x, y), r, self.ink(a * light))


class Particles(Layer):
    def __init__(self, config, engine):
        super().__init__(config, engine)
        self.items = deque(maxlen=config["maximum"])
        self.credit = 0

    def update(self):
        e, c = self.e, self.c
        while self.items and e.now - self.items[0][0] >= c["life"]:
            self.items.popleft()
        rate = 0
        if e.moved and c["moving"]:
            rate = c["rate"] * (1 - c["response"] * (1 - clamp(e.speed / 750)))
        elif not e.moved and c["resting"] and e.still > 0.3:
            rate = c["rate"] * 0.15
        self.credit += e.dt * rate * e.budget
        n = int(self.credit)
        self.credit -= n
        offset = (e.pos[0] + e.rear[0] - CENTER, e.pos[1] + e.rear[1] - CENTER)
        origins = [offset] * n
        if c["burst"]:
            for event in e.clicks:
                origins.extend([event.pos] * max(1, round(c["rate"] * 0.15 * e.budget)))
        limit = max(1, round(c["maximum"] * e.budget))
        for pos in origins[:limit]:
            angle = math.atan2(e.axis[1], e.axis[0]) + math.radians(c["spread"]) * e.rng.uniform(-0.5, 0.5)
            speed = e.rng.uniform(9, 57)
            self.items.append((e.now, pos, speed * math.cos(angle), speed * math.sin(angle)))
        while len(self.items) > limit:
            self.items.popleft()
        return bool(self.items)

    def draw(self, frame, draw):
        e, c = self.e, self.c
        for born, pos, vx, vy in self.items:
            age = max(0, e.now - born)
            x, y = e.local(pos)
            x += vx * age
            y += vy * age + 0.5 * c["gravity"] * age**2
            life = clamp(1 - age / c["life"])
            r = max(0.65, c["size"] * life)
            shape = c["style"]
            if shape == "火花":
                draw.line(
                    [(x, y), (x - vx * 0.09, y - vy * 0.09)], fill=self.ink(life), width=max(1, round(r))
                )
            elif shape == "破片":
                draw.polygon([(x - r, y), (x, y - r * 2), (x + r, y), (x, y + r)], fill=self.ink(life))
            elif shape == "煙":
                dot(draw, (x, y), c["size"] * (1.2 + age * 2), self.ink(life * 0.23))
            elif shape == "推進剤":
                draw.ellipse(box(x, y, r + 1), outline=self.ink(life * 0.68))
            else:
                dot(draw, (x, y), r, self.ink(life))


class Deploy(Layer):
    def __init__(self, config, engine):
        super().__init__(config, engine)
        self.level = 0
        self.held_until = -math.inf

    def update(self):
        e, c = self.e, self.c
        triggers = (("移動再開", e.started), ("停止", e.stopped), ("クリック", bool(e.clicks)))
        if any(active and c["trigger"] in ("すべて", name) for name, active in triggers):
            self.held_until = e.now + ((1 - self.level) * c["opening"] + c["hold"]) / 1000
        if e.now < self.held_until:
            self.level = min(1, self.level + e.dt * 1000 / c["opening"])
        else:
            self.level = max(0, self.level - e.dt * 1000 / c["closing"])
        e.deploy = self.level if c["ease"] == "機械的" else self.level**2 * (3 - 2 * self.level)
        return self.level > 0

    def draw(self, frame, draw):
        c, e = self.c, self.e
        r = 5 + c["distance"] * e.deploy
        for i in range(3):
            start = i * 120 + c["rotation"] * e.deploy
            draw.arc(box(CENTER, CENTER, r), start, start + 32, fill=self.ink(e.deploy * 0.82), width=2)


class Rare(Layer):
    def __init__(self, config, engine):
        super().__init__(config, engine)
        self.next = None
        self.start = -math.inf
        self.mode = None

    def update(self):
        e, c = self.e, self.c
        if e.moved:
            self.start = -math.inf
        if self.next is None or e.moved:
            self.next = e.now + c["cooldown"] + e.rng.expovariate(c["frequency"] / 60)
        if e.now >= self.next:
            candidates = [k for k in ("spin", "formation", "flash") if c[k]]
            self.mode = e.rng.choice(candidates) if candidates else None
            self.start = e.now
            self.next = None
        self.phase = clamp((e.now - self.start) / 0.8)
        e.rare_formation = math.sin(math.pi * self.phase) if self.mode == "formation" else 0
        return self.mode is not None and self.phase < 1

    def draw(self, frame, draw):
        strength = math.sin(math.pi * self.phase)
        for i in range(3):
            angle = i * TAU / 3 + self.phase * (TAU if self.mode == "spin" else 0.35)
            x, y = point(CENTER, CENTER, 24 + strength * 8, angle)
            if self.mode == "flash":
                draw.line([(x - 3, y), (x + 3, y)], fill=self.ink(strength))
                draw.line([(x, y - 3), (x, y + 3)], fill=self.ink(strength))
            else:
                dot(draw, (x, y), 2, self.ink(strength))


class Followers(Layer):
    def __init__(self, config, engine):
        super().__init__(config, engine)
        self.size = max(4, round(38 * config["scale"]))
        self.headings = []
        self.positions = []
        self.reaction = -math.inf

    def update(self):
        e, c = self.e, self.c
        if e.clicks:
            self.reaction = e.now
        kick = clamp(1 - (e.now - self.reaction) / 0.36)
        radius = c["distance"] * (1 + 0.16 * e.deploy)
        n = c["count"]
        blend = 1 - math.exp(-e.dt / c["lag"])
        for i in range(n):
            slot = i - (n - 1) / 2
            angle = e.heading + math.pi
            if e.still >= 0.14 or not e.has_moved:
                angle = e.now * TAU * c["orbit"] + i * TAU / n + e.rare_formation * 0.65
                r = radius
            elif c["formation"] == "縦列":
                r = radius * (0.65 + 0.36 * i)
            elif c["formation"] == "横列":
                angle += slot * 0.65
                r = radius * (1 + 0.16 * abs(slot))
            else:
                angle += slot * 0.80
                r = radius * (0.75 + 0.20 * abs(slot))
            target = point(0, 0, r, angle + kick * 1.8)
            if i == len(self.positions):
                self.positions.append(target)
                self.headings.append(e.heading)
            else:
                # Preserve world-space inertia while bounding travel after a rapid sweep.
                ox, oy = self.positions[i]
                self.positions[i] = (clamp(ox - e.delta[0], -95, 95), clamp(oy - e.delta[1], -95, 95))
            ox, oy = self.positions[i]
            x, y = ox + (target[0] - ox) * blend, oy + (target[1] - oy) * blend
            # Keep the whole sprite outside the pointing area, even while changing sides.
            length = math.hypot(x, y)
            if length < 18:
                x, y = point(0, 0, 18, math.atan2(y, x))
            self.positions[i] = x, y
            # Relative displacement includes camera compensation, giving world flight velocity.
            if math.hypot(x - ox, y - oy) > 0.012:
                self.headings[i] = math.atan2(y - oy, x - ox)
        return True

    def draw(self, frame, draw):
        c = self.c
        for index, (dx, dy) in enumerate(self.positions):
            x, y = CENTER + dx, CENTER + dy
            if c["style"] == "装備画像":
                pose = (int(self.e.now * 5) + index) % 4
                self.e.fly(frame, (x, y), self.headings[index], pose, self.size, c["opacity"])
            else:
                r = self.size / 2
                shape = [
                    (x - r, y - r),
                    (x + r * 0.65, y - r * 0.25),
                    (x + r, y + r),
                    (x - r * 0.35, y + r * 0.5),
                ]
                draw.polygon(
                    shape, outline=self.ink(), fill=self.ink(0.65) if c["style"] == "光の菱形" else None
                )


class SpecialEffect(Layer):
    COOLDOWN = 3.0

    def __init__(self, config, engine):
        super().__init__(config, engine)
        self.event = None
        self.last_launch = -math.inf
        self.lifetime = config["duration"]

    def update(self):
        for event in self.e.inputs:
            button = "left" if event.kind == "double" else event.kind
            if (
                button == BUTTONS[self.c["button"]]
                and event.modifiers == MODIFIERS[self.c["modifiers"]]
                and event.time - self.last_launch >= self.COOLDOWN
            ):
                self.event = event
                self.last_launch = event.time
        if self.event and self.e.now - self.event.time >= self.lifetime:
            self.event = None
        return self.event is not None


class SpiralBits(SpecialEffect):
    STRAIGHT_AT = 0.60
    STAGGER = 0.035
    LIGHT_ONLY = 0.32
    REVEAL = 0.16
    LAUNCH_BLUE = (75, 175, 255)

    def __init__(self, config, engine):
        super().__init__(config, engine)
        self.lifetime += (config["count"] - 1) * self.STAGGER

    def location(self, origin, index, progress):
        # Begin gently and accelerate through the spiral before departure.
        spiral = min(progress, self.STRAIGHT_AT)
        travel = 0.936 * (spiral / self.STRAIGHT_AT) ** 2
        radius = self.c["radius"] * travel
        angle = -3 * math.pi / 4 + TAU * (index / self.c["count"] + self.c["turns"] * travel)
        start = point(*origin, radius, angle)
        if progress <= self.STRAIGHT_AT:
            return start
        # Leave the spiral along its tangent and keep flying beyond the edge.
        turn = TAU * self.c["turns"] * travel
        dx = math.cos(angle) - turn * math.sin(angle)
        dy = math.sin(angle) + turn * math.cos(angle)
        length = math.hypot(dx, dy)
        nx, ny = dx / length, dy / length
        exits = [((OVERLAY_SIZE + 48 if n > 0 else -48) - s) / n
                 for n, s in zip((nx, ny), start) if abs(n) > 1e-9]
        distance = max(0, min(exits)) * (progress - self.STRAIGHT_AT) / (0.92 - self.STRAIGHT_AT)
        return start[0] + nx * distance, start[1] + ny * distance

    def draw(self, frame, draw):
        origin = self.e.local(self.event.pos)
        for index in range(self.c["count"]):
            age = self.e.now - self.event.time - index * self.STAGGER
            progress = age / self.c["duration"]
            if not 0 <= progress < 1:
                continue
            fade = 1  # Disappear by leaving the viewport, keeping full opacity.
            reveal = clamp((progress - self.LIGHT_ONLY) / self.REVEAL)
            color = tuple(round(a + (b - a) * reveal) for a, b in zip(self.LAUNCH_BLUE, self.color))
            def glow(strength):
                return tint(color, fade * self.c["opacity"] * strength)

            head = self.location(origin, index, progress)
            path_strength = clamp((self.STRAIGHT_AT + 0.10 - progress) / 0.10)
            if path_strength > 0:
                # Retain the full spiral until straight departure, then fade
                # the stored curve while the equipment continues off-screen.
                path_progress = min(progress, self.STRAIGHT_AT)
                steps = max(2, math.ceil(path_progress * 160))
                trail = [self.location(origin, index, path_progress * i / steps) for i in range(steps + 1)]
                draw.line(trail, fill=tint(self.LAUNCH_BLUE, self.c["opacity"] * path_strength * 0.75), width=2)
            last = head
            for step in range(1, 7) if reveal > 0 else ():
                tail = self.location(origin, index, max(0, progress - step * 0.017))
                draw.line([last, tail], fill=glow((7 - step) / 8), width=2 if step < 3 else 1)
                last = tail
            if reveal < 1:
                dot(draw, head, 3, glow((1 - reveal) * 0.3))
                dot(draw, head, 1.4, glow(1 - reveal))
            if reveal <= 0:
                continue
            ahead = self.location(origin, index, min(1, progress + 0.001))
            heading = math.atan2(ahead[1] - head[1], ahead[0] - head[0])
            pose = (int(age * 7) + index) % 4
            self.e.fly(frame, head, heading, pose, 22, reveal * fade * self.c["opacity"])


class RemoteAction(SpecialEffect):
    """Shared timing and drawing for equipment actions, anchored to the click."""

    @property
    def progress(self):
        return clamp((self.e.now - self.event.time) / self.lifetime)

    @property
    def origin(self):
        return self.e.local(self.event.pos)

    @property
    def envelope(self):
        return clamp(self.progress / 0.08) * clamp((1 - self.progress) / 0.12)

    @property
    def reach(self):
        p = self.progress
        return clamp(p / 0.28) * clamp((1 - p) / 0.22)

    def beam(self, draw, start, end, strength=1, width=2):
        draw.line([start, end], fill=self.ink(self.envelope * strength * 0.22), width=width + 3)
        draw.line([start, end], fill=self.ink(self.envelope * strength), width=width)

    def equipment(self, frame, pos, heading, index=0, size=24):
        self.e.fly(frame, pos, heading, (int(self.e.now * 7) + index) % 4,
                   size, self.c["opacity"] * self.envelope)


class RemoteVolley(RemoteAction):
    """Launch, aim at an offset virtual target, fire, then recover."""
    COUNT = 6

    @property
    def count(self):
        return self.COUNT

    def stations(self):
        return [point(0, 0, self.c["radius"], -math.pi / 2 + i * TAU / self.count)
                for i in range(self.count)]

    def draw(self, frame, draw):
        ox, oy = self.origin
        target = (ox + 64, oy - 46)
        for i, (dx, dy) in enumerate(self.stations()):
            pos = (ox + dx * self.reach, oy + dy * self.reach)
            heading = math.atan2(target[1] - pos[1], target[0] - pos[0])
            # Brief staggered pulses occur only once the equipment is deployed.
            pulse = (self.progress - 0.34 - (i % 3) * 0.035) % 0.19
            if 0.34 <= self.progress < 0.76 and pulse < 0.09:
                self.beam(draw, pos, target, 1 - pulse / 0.12)
            self.equipment(frame, pos, heading, i)


class SazabiLaunch(RemoteVolley):
    """Launch, fan out, pause off-screen, then attack a small distant area."""
    LAUNCH_SPEED = 2.0
    STAGGER = 0.025
    OPEN_AT = 0.13
    TURN_AT = 0.20
    DEPART_AT = 0.88
    SIZE = 32
    BEAT = 0.40
    ENTRY_TIME = 0.34
    AIM_TIME = 0.10
    FIRE_TIME = 0.40
    AFTER_TIME = 0.22
    FADE_TIME = 0.24
    BRANCHES = ((-118, (-0.90, -0.45)), (-26, (-1, 0)), (82, (-0.85, 0.52)),
                (-118, (0.90, -0.45)), (-18, (1, 0.07)), (85, (0.85, 0.52)))

    def __init__(self, config, engine):
        super().__init__(config, engine)
        self.launch_end = (config["duration"] + (self.count - 1) * self.STAGGER) / self.LAUNCH_SPEED
        self.entry_at = self.launch_end + self.BEAT
        self.fire_at = self.entry_at + self.ENTRY_TIME + self.AIM_TIME
        self.fire_end = self.fire_at + self.FIRE_TIME
        self.after_end = self.fire_end + self.AFTER_TIME
        self.lifetime = self.after_end + self.FADE_TIME

    def launch_progress(self, elapsed, index=0):
        return (elapsed * self.LAUNCH_SPEED - index * self.STAGGER) / self.c["duration"]

    def firing_target(self, index):
        # Each ray stops at the near edge of the same small target area.
        # Preserving the angular order prevents crossing before the target.
        ox, oy = self.origin
        center = ox + 5, oy - 55
        station = self.firing_station(index)
        heading = math.atan2(station[1] - center[1], station[0] - center[0])
        return point(*center, 9 * self.c["radius"] / 64, heading)

    def firing_station(self, index):
        ox, oy = self.origin
        dx, dy = ((-98, -24), (98, -26), (-96, 35), (96, 38), (-54, 100), (54, 98))[index]
        return ox + dx, oy + dy

    def attack_position(self, index, elapsed):
        station, target = self.firing_station(index), self.firing_target(index)
        u = clamp((elapsed - self.entry_at) / self.ENTRY_TIME)
        approach = (1 - u) ** 3
        return tuple(station[k] + (station[k] - target[k]) * 2.8 * approach for k in (0, 1))

    def shot_segment(self, index, elapsed):
        if not self.fire_at <= elapsed < self.after_end:
            return None
        station, target = self.firing_station(index), self.firing_target(index)
        heading = math.atan2(target[1] - station[1], target[0] - station[0])
        start = point(*station, 40 / 96 * 38, heading)
        travel = clamp((elapsed - self.fire_at) / 0.065)
        return start, tuple(start[k] + (target[k] - start[k]) * travel for k in (0, 1))

    def draw_attack(self, frame, elapsed):
        layer = Image.new("RGBA", frame.size)
        light = ImageDraw.Draw(layer)
        color = (140, 255, 100) if self.c["color"] == "機体色" else self.color
        strength = 1 if elapsed < self.fire_end else clamp((self.after_end - elapsed) / self.AFTER_TIME) * 0.45
        for index in range(self.count):
            segment = self.shot_segment(index, elapsed)
            if segment:
                start, end = segment
                heading = math.atan2(end[1] - start[1], end[0] - start[0])
                nx, ny = -math.sin(heading), math.cos(heading)
                for width, tip, alpha, ink in ((4, 1.0, 0.17, color), (1.8, 0.45, 0.8, color),
                                               (0.65, 0.2, 0.95, (234, 255, 220))):
                    tip *= min(1, self.c["radius"] / 64)
                    polygon = ((start[0] + nx * width, start[1] + ny * width),
                               (end[0] + nx * tip, end[1] + ny * tip),
                               (end[0] - nx * tip, end[1] - ny * tip),
                               (start[0] - nx * width, start[1] - ny * width))
                    light.polygon(polygon, fill=tint(ink, strength * alpha * self.c["opacity"]))
        frame.alpha_composite(layer)
        for index in range(self.count):
            pos, target = self.attack_position(index, elapsed), self.firing_target(index)
            heading = math.atan2(target[1] - pos[1], target[0] - pos[0])
            entry = clamp((elapsed - self.entry_at) / self.ENTRY_TIME)
            fade = clamp((elapsed - self.after_end) / self.FADE_TIME)
            size = round(50 - 12 * entry)
            image = self.e.art.rear_frame(heading, size)
            self.e.stamp(frame, image, (pos[0] - size / 2, pos[1] - size / 2),
                         self.c["opacity"] * (1 - fade))

    def opening(self, progress):
        return clamp((progress - self.OPEN_AT) / (self.TURN_AT - self.OPEN_AT))

    def location(self, index, progress):
        ox, oy = self.origin
        depth = index % 3
        x = ox + (-23 if index < 3 else 23) + (depth - 1) * 3
        y = oy + 30 + depth * 6
        rise = self.c["radius"] * (1.35 - depth * 0.2) + 26
        t = clamp(progress / self.TURN_AT)
        # A stronger initial burst completes the same climb in 0.18s by
        # default, easing into the turn without stopping.
        travel = 1.4 * t - 0.4 * t * t
        if progress <= self.TURN_AT:
            return x, y - rise * travel
        a = (x, y - rise)
        span = self.DEPART_AT - self.TURN_AT
        b = (x, a[1] - rise * span * 0.6 / (3 * self.TURN_AT))
        dy, direction = self.BRANCHES[index]
        length = math.hypot(*direction)
        nx, ny = direction[0] / length, direction[1] / length
        end = (-48 if index < 3 else OVERLAY_SIZE + 48, oy + dy * self.c["radius"] / 64)
        c = (end[0] - nx * 45, end[1] - ny * 45)
        u = (progress - self.TURN_AT) / span
        if u > 1:
            return end[0] + nx * (u - 1) * 80, end[1] + ny * (u - 1) * 80
        return tuple((1 - u) ** 3 * a[k] + 3 * (1 - u) ** 2 * u * b[k] +
                     3 * (1 - u) * u * u * c[k] + u ** 3 * end[k] for k in (0, 1))

    def heading(self, index, progress):
        if progress <= self.TURN_AT:
            return -math.pi / 2
        a, b = self.location(index, progress - 0.001), self.location(index, progress + 0.001)
        return math.atan2(b[1] - a[1], b[0] - a[0])

    def draw(self, frame, draw):
        elapsed = self.e.now - self.event.time
        if elapsed >= self.launch_end:
            if elapsed >= self.entry_at:
                self.draw_attack(frame, elapsed)
            return
        units = []
        color = (255, 232, 55) if self.c["color"] == "機体色" else self.color
        core = tuple(round(channel * 0.45 + 255 * 0.55) for channel in color)
        for index in range(self.count):
            p = self.launch_progress(elapsed, index)
            if p >= 1:
                continue
            fade = clamp((1 - p) / 0.18)
            if p > 0:
                steps = max(3, math.ceil(p * 110))
                path = [self.location(index, p * j / steps) for j in range(steps + 1)]
                layer = Image.new("RGBA", frame.size)
                light = ImageDraw.Draw(layer)
                opacity = self.c["opacity"] * fade
                light.line(path, fill=tint(color, opacity * 0.12), width=9, joint="curve")
                light.line(path, fill=tint(color, opacity * 0.7), width=5, joint="curve")
                light.line(path, fill=tint(core, opacity * 0.85), width=3, joint="curve")
                if p > 0.025:
                    pos, heading = self.location(index, p), self.heading(index, p)
                    rear = heading + math.pi
                    root = point(*pos, -self.SIZE * 0.25, heading)
                    length = 18 + 6 * self.opening(p)
                    nx, ny = -math.sin(rear), math.cos(rear)
                    polygon = []
                    for side in (-1, 1):
                        sections = ((0, 2), (0.30, 7), (0.48, 4), (0.68, 5), (1, 0))
                        if side == 1:
                            sections = reversed(sections)
                        for t, width in sections:
                            x, y = point(*root, length * t, rear)
                            polygon.append((x + nx * width * side, y + ny * width * side))
                    light.polygon(polygon, fill=tint(color, opacity * 0.65))
                frame.alpha_composite(layer)
            units.append((self.location(index, max(0, p)), self.heading(index, p),
                          round(self.opening(p) * 3), self.c["opacity"]))
        for pos, heading, pose, opacity in units:
            self.e.fly(frame, pos, heading, pose, self.SIZE, opacity)


class DragoonVolley(RemoteVolley):
    HOLD_END = 0.075
    EXIT_END = 0.25
    FIRE_AT = 0.79
    FIRE_END = 1.19
    AFTERGLOW_END = 1.35
    SUPER_SIZE = 40
    START_SPREAD = 0.55
    # Crossfire from distinct off-screen positions, spread across the scene.
    # These lines intersect in several places rather than sharing one target.
    SHOT_PATHS = (
        ((-180, -24), (180, 32)),
        ((-150, 175), (105, -170)),
        ((-170, -170), (170, 80)),
        ((-110, 180), (-55, -180)),
        ((170, -145), (-150, 160)),
        ((175, 170), (-155, -20)),
        ((-175, 110), (175, 45)),
        ((55, -175), (105, 175)),
    )
    SHOT_WIDTHS = (6.0, 2.1, 2.4, 1.8, 2.0, 2.8, 2.5, 1.9)

    def __init__(self, config, engine):
        super().__init__(config, engine)
        if self.is_super:
            self.lifetime = config["duration"] * (self.AFTERGLOW_END + 0.05)

    def progress_at(self, elapsed):
        return elapsed / self.c["duration"]

    @property
    def progress(self):
        if not self.is_super:
            return super().progress
        return self.progress_at(self.e.now - self.event.time)

    @property
    def is_super(self):
        return self.e.art.sheet.stem == "ストライクフリーダム"

    @property
    def count(self):
        return 10 if self.e.art.sheet.stem == "レジェンドガンダム" else 8

    def stations(self):
        r = self.c["radius"]
        if self.is_super:
            # Four blades on each side, matching the reference backpack spread.
            return [(side * x * r * self.START_SPREAD, y * r * self.START_SPREAD) for side in (-1, 1)
                    for x, y in ((0.32, -0.9), (0.88, -0.5), (0.88, 0.5), (0.32, 0.9))]
        return [((-1 if i % 2 == 0 else 1) * r * (0.55 + 0.12 * (i // 2)),
                 -r + (i // 2) * 2 * r / (self.count // 2 - 1)) for i in range(self.count)]

    def launch_layout(self, progress=None):
        p = self.progress if progress is None else progress
        if p >= self.EXIT_END:
            return []
        travel = clamp((p - self.HOLD_END) / (self.EXIT_END - self.HOLD_END))
        ox, oy = self.origin
        layout = []
        for dx, dy in self.stations():
            radius = math.hypot(dx, dy)
            nx, ny = dx / radius, dy / radius
            # Exit through the actual viewport edge, with enough clearance for
            # the entire sprite, including a moved pointer's camera offset.
            edges = [((OVERLAY_SIZE + 48 if nx > 0 else -48) - ox) / nx,
                     ((OVERLAY_SIZE + 48 if ny > 0 else -48) - oy) / ny]
            end = max(radius, min(edges))
            distance = radius + (end - radius) * travel
            layout.append(((ox + nx * distance, oy + ny * distance), math.atan2(ny, nx)))
        return layout

    def shot_rays(self, progress=None):
        p = self.progress if progress is None else progress
        if not self.FIRE_AT <= p < self.FIRE_END:
            return []
        ox, oy = self.origin
        return [((ox + a[0], oy + a[1]), (ox + b[0], oy + b[1])) for a, b in self.SHOT_PATHS]

    def draw_super_volley(self, frame):
        phase = (self.progress - self.FIRE_AT) / (self.FIRE_END - self.FIRE_AT)
        head = clamp(phase / 0.08)
        tail = clamp((phase - 0.9) / 0.1)
        strength = clamp(phase / 0.025) * clamp((1 - phase) / 0.1) * self.c["opacity"]
        color = (130, 255, 140) if self.c["color"] == "機体色" else self.color
        rays = self.shot_rays()
        # Composite separate beams so a faint halo cannot erase a bright beam
        # where they cross. Draw the dominant foreground beam last.
        for index in sorted(range(len(rays)), key=lambda i: self.SHOT_WIDTHS[i]):
            start, end = rays[index]
            layer = Image.new("RGBA", frame.size)
            draw = ImageDraw.Draw(layer)
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)
            nx, ny = -dy / length, dx / length
            width = self.SHOT_WIDTHS[index]
            for scale, ink, alpha in ((2.0, color, 0.07), (1.5, color, 0.12),
                                      (1, color, 0.85), (0.23, (238, 255, 235), 0.95)):
                for section in range(12):
                    a = tail + (head - tail) * section / 12
                    b = tail + (head - tail) * (section + 1) / 12
                    if b <= a:
                        continue
                    x, y = start[0] + dx * a, start[1] + dy * a
                    xx, yy = start[0] + dx * b, start[1] + dy * b
                    wa, wb = width * (1 - a) + 0.5, width * (1 - b) + 0.5
                    polygon = [(x + nx * wa * scale, y + ny * wa * scale),
                               (xx + nx * wb * scale, yy + ny * wb * scale),
                               (xx - nx * wb * scale, yy - ny * wb * scale),
                               (x - nx * wa * scale, y - ny * wa * scale)]
                    draw.polygon(polygon, fill=tint(ink, strength * alpha * (1 - a * 0.5)))
            frame.alpha_composite(layer)

    def draw_afterglow(self, frame):
        p = self.progress
        strength = (clamp((p - (self.FIRE_END - 0.10)) / 0.10) *
                    clamp((self.AFTERGLOW_END - p) / (self.AFTERGLOW_END - self.FIRE_END)) ** 2)
        if strength <= 0:
            return
        color = (130, 255, 140) if self.c["color"] == "機体色" else self.color
        for i, ray in enumerate(self.shot_rays(self.FIRE_END - 0.001)):
            layer = Image.new("RGBA", frame.size)
            light = ImageDraw.Draw(layer)
            width = max(1, round(self.SHOT_WIDTHS[i] / 2))
            light.line(ray, fill=tint(color, self.c["opacity"] * strength * 0.06), width=width + 3)
            light.line(ray, fill=tint(color, self.c["opacity"] * strength * 0.23), width=width)
            frame.alpha_composite(layer)

    def draw(self, frame, draw):
        if not self.is_super:
            return super().draw(frame, draw)
        if self.progress < self.EXIT_END:
            for i, (pos, heading) in enumerate(self.launch_layout()):
                self.equipment(frame, pos, heading, i, self.SUPER_SIZE)
        else:
            self.draw_afterglow(frame)
            if self.FIRE_AT <= self.progress < self.FIRE_END:
                self.draw_super_volley(frame)


class PodVolley(RemoteVolley):
    COUNT = 2

    def stations(self):
        return [(-self.c["radius"], -24), (self.c["radius"], 24)]


class RifleVolley(RemoteVolley):
    def stations(self):
        r = self.c["radius"]
        return [((-1 if i % 2 == 0 else 1) * r * 0.65,
                 -r + (i // 2) * r) for i in range(self.count)]


class ShieldFunnels(RemoteAction):
    SIZE = 104
    HUB_RADIUS = 26
    TRAIL_SECONDS = 0.08
    JOIN_AT = 0.42
    SPIN_END = 0.90
    TOTAL_TURNS = 1.15

    def rotation(self, progress=None):
        # Start at peak speed and decelerate continuously through docking.
        p = self.progress if progress is None else progress
        t = min(p / self.SPIN_END, 1)
        joined = 1 - (1 - self.JOIN_AT / self.SPIN_END) ** 3
        return TAU * self.TOTAL_TURNS * (1 - (1 - t) ** 3 - joined)

    def formation(self, progress=None):
        # Three separate spiral paths close on one rigid three-shield assembly.
        # After docking the central disks keep their spacing throughout the spin.
        p = self.progress if progress is None else progress
        approach = min(p / self.JOIN_AT, 1)
        joined_radius = self.HUB_RADIUS
        outer_radius = min(108, self.c["radius"] + 32)
        closing = 1 - (1 - approach) ** 3
        radius = joined_radius + (outer_radius - joined_radius) * (1 - closing)
        turn = self.rotation(p)
        bank = (1 - approach) ** 2 * 0.6
        # The three central disks occupy the corners of an open triangle.
        # Each shield is skewed 30 degrees to let its SHORT end meet its neighbour.
        return [(point(*self.origin, radius, angle + turn), angle + turn - math.pi / 6 + bank)
                for angle in (-5 * math.pi / 6, -math.pi / 6, math.pi / 2)]

    def trail_paths(self):
        p = self.progress
        paths = [[] for _ in range(6)]
        for step in range(9):
            previous = p - self.TRAIL_SECONDS / self.lifetime * step / 8
            for index, (pos, heading) in enumerate(self.formation(previous)):
                for side in (-1, 1):
                    x, y = 18 * self.SIZE / 96, side * 20 * self.SIZE / 96
                    paths[index * 2 + (side == 1)].append((
                        pos[0] + x * math.cos(heading) - y * math.sin(heading),
                        pos[1] + x * math.sin(heading) + y * math.cos(heading)))
        return paths

    def draw(self, frame, draw):
        for path in self.trail_paths():
            for step, (a, b) in enumerate(zip(path, path[1:])):
                if math.dist(a, b) < 0.05:
                    continue
                strength = self.c["opacity"] * clamp((1 - self.progress) / 0.1) * (1 - step / 8)
                draw.line([a, b], fill=tint((70, 220, 160), strength * 0.3), width=5)
                draw.line([a, b], fill=tint((100, 245, 185), strength * 0.9), width=2)
        for pos, angle in self.formation():
            image = self.e.art.shield_frame(angle, self.SIZE)
            self.e.stamp(frame, image, (pos[0] - self.SIZE / 2, pos[1] - self.SIZE / 2),
                         self.c["opacity"] * self.envelope)


class GundBits(RemoteVolley):
    @property
    def count(self):
        return 7 if self.e.art.sheet.stem == "ガンダム・ルブリス" else 11

    def stations(self):
        # Initially scatter; after firing, regroup into a compact shield formation.
        merge = clamp((self.progress - 0.68) / 0.18)
        radius = self.c["radius"] * (1 - merge) + 18 * merge
        return [point(0, 0, radius, -math.pi / 2 + TAU * i / self.count)
                for i in range(self.count)]


class BitOn(RemoteAction):
    """Calibarn receives the bits; do not invent an offensive finisher."""
    def draw(self, frame, draw):
        p = self.progress
        gather = clamp(p / 0.68)
        radius = self.c["radius"] * (1 - gather) + 12 * gather
        for i in range(11):
            angle = -math.pi / 2 + TAU * i / 11 + (1 - gather) * 0.5
            pos = point(*self.origin, radius, angle)
            self.equipment(frame, pos, angle + math.pi, i, 18)


class StunBits(RemoteAction):
    def pairs(self):
        ox, oy = self.origin
        r = self.c["radius"] * self.reach
        # Four pairs of Corax form a non-destructive beam net between bits.
        return [((ox - r, oy + r * level), (ox + r, oy + r * level)) for level in (-0.45, 0.45)] + [
            ((ox + r * level, oy - r), (ox + r * level, oy + r)) for level in (-0.45, 0.45)]

    def draw(self, frame, draw):
        for i, (a, b) in enumerate(self.pairs()):
            if 0.3 <= self.progress < 0.78:
                self.beam(draw, a, b, 0.8, 1)
            heading = math.atan2(b[1] - a[1], b[0] - a[0])
            self.equipment(frame, a, heading, i, 18)
            self.equipment(frame, b, heading + math.pi, i, 18)


class WiredIncom(RemoteAction):
    def cable(self):
        ox, oy = self.origin
        r = self.c["radius"] * self.reach
        return [(ox, oy), (ox - r * 0.65, oy + r * 0.4),
                (ox - r, oy - r * 0.45), (ox + r * 0.15, oy - r)]

    def draw(self, frame, draw):
        cable = self.cable()
        draw.line(cable, fill=self.ink(self.envelope * 0.7), width=1)
        for relay in cable[1:-1]:
            dot(draw, relay, 1.5, self.ink(self.envelope))
        target = (self.origin[0] + 68, self.origin[1] - 20)
        head = cable[-1]
        heading = math.atan2(target[1] - head[1], target[0] - head[0])
        if 0.36 < self.progress < 0.72 and int(self.progress * 24) % 3 != 0:
            self.beam(draw, head, target)
        self.equipment(frame, head, heading)


class FunnelMissiles(RemoteAction):
    def location(self, index, progress):
        ox, oy = self.origin
        # Distinct curved, one-way paths: missiles are expended, never recalled.
        return (ox + 105 * progress,
                oy - 68 * progress + (index - 2.5) * 24 * math.sin(math.pi * progress))

    def draw(self, frame, draw):
        for i in range(6):
            p = (self.progress - i * 0.045) / 0.7
            if not 0 <= p < 1:
                continue
            head = self.location(i, p)
            trail = [self.location(i, max(0, p - j * 0.022)) for j in range(12)]
            draw.line(trail, fill=self.ink(self.envelope * 0.5), width=2)
            ahead = self.location(i, min(1, p + 0.002))
            self.equipment(frame, head, math.atan2(ahead[1] - head[1], ahead[0] - head[0]), i, 20)


class LongRangeCannon(RemoteAction):
    SIZE = 112
    LAUNCH_HEADING = math.radians(-100)
    HOLD_END = 0.06
    EXIT_END = 0.20
    ENTRY_AT = 0.34
    ENTRY_END = 0.51
    OPEN_AT = 0.56
    OPEN_END = 0.68
    FIRE_AT = 0.70
    FIRE_END = 0.92
    CHARGE_TIME = 0.35

    def __init__(self, config, engine):
        super().__init__(config, engine)
        self.lifetime += self.CHARGE_TIME

    def progress_at(self, elapsed):
        start = self.c["duration"] * self.OPEN_END
        local = min(elapsed, start) + max(0, elapsed - start - self.CHARGE_TIME)
        return clamp(local / self.c["duration"])

    @property
    def progress(self):
        return self.progress_at(self.e.now - self.event.time)

    def charge_at(self, elapsed):
        start = self.c["duration"] * self.OPEN_END
        end = self.c["duration"] * self.FIRE_AT + self.CHARGE_TIME
        if not start <= elapsed < end:
            return 0
        return clamp((elapsed - start) / (end - start))

    def emitter_position(self):
        return point(*self.station(), -self.SIZE * 4 / 96, math.pi)

    def station(self):
        ox, oy = self.origin
        return ox + self.c["radius"] * 0.5, oy - 16

    def launch_position(self, progress):
        ox, oy = self.origin
        travel = clamp((progress - self.HOLD_END) / (self.EXIT_END - self.HOLD_END)) ** 2
        start_y = oy + 20
        return ox + self.c["radius"] * 0.5, start_y + (-self.SIZE / 2 - 40 - start_y) * travel

    def entry_position(self, progress):
        end_x, end_y = self.station()
        travel = clamp((progress - self.ENTRY_AT) / (self.ENTRY_END - self.ENTRY_AT))
        travel = 1 - (1 - travel) ** 3
        return (OVERLAY_SIZE + self.SIZE) * (1 - travel) + end_x * travel, end_y

    def opening(self, progress):
        value = clamp((progress - self.OPEN_AT) / (self.OPEN_END - self.OPEN_AT))
        value *= clamp((1 - progress) / (1 - self.FIRE_END))
        return value * value * (3 - 2 * value)

    def shot_segment(self, progress):
        if not self.FIRE_AT <= progress < self.FIRE_END:
            return None
        # The emitter sits at the rear of the open channel, not at its tips.
        start = self.emitter_position()
        phase = (progress - self.FIRE_AT) / (self.FIRE_END - self.FIRE_AT)
        travel = clamp(phase / 0.08)
        return start, (start[0] + (-64 - start[0]) * travel, start[1])

    def draw(self, frame, draw):
        p = self.progress
        opacity = self.c["opacity"] * clamp((1 - p) / 0.08)
        if p < self.EXIT_END:
            pos = self.launch_position(p)
            speed = clamp((p - self.HOLD_END) / (self.EXIT_END - self.HOLD_END))
            if speed > 0:
                rear = point(*pos, -self.SIZE * 0.42, self.LAUNCH_HEADING)
                tail = (rear[0], rear[1] + 18 * speed)
                draw.line([rear, tail], fill=tint((100, 195, 255), opacity * speed * 0.65), width=3)
                draw.line([rear, tail], fill=tint((225, 245, 255), opacity * speed), width=1)
            self.e.fly(frame, pos, self.LAUNCH_HEADING, 0, self.SIZE, opacity)
            return
        if p < self.ENTRY_AT:
            return
        pos = self.entry_position(p) if p < self.ENTRY_END else self.station()
        opening = self.opening(p)
        segment = self.shot_segment(p)
        if segment:
            phase = (p - self.FIRE_AT) / (self.FIRE_END - self.FIRE_AT)
            strength = clamp(phase / 0.08) * clamp((1 - phase) / 0.2) * opacity
            color = (255, 115, 185) if self.c["color"] == "機体色" else self.color
            for width, ink, alpha in ((22, color, 0.10), (15, color, 0.3),
                                       (9, color, 0.95), (3, (255, 235, 245), 1)):
                draw.line(segment, fill=tint(ink, strength * alpha), width=width)
        self.e.fly(frame, pos, math.pi, round(opening * 3), self.SIZE, opacity, deploying=opening > 0)
        charge = self.charge_at(self.e.now - self.event.time)
        if charge > 0:
            # Focus the charge at the emitter after the rails are fully open.
            root = self.emitter_position()
            strength = charge * charge * opacity
            color = (255, 115, 185) if self.c["color"] == "機体色" else self.color
            light = Image.new("RGBA", frame.size)
            glow = ImageDraw.Draw(light)
            dot(glow, root, 3 + 6 * charge, tint(color, strength * 0.10))
            dot(glow, root, 2 + 3 * charge, tint(color, strength * 0.45))
            dot(glow, root, 1 + 1.5 * charge, tint((255, 235, 245), strength))
            frame.alpha_composite(light)


class DeltaField(SpecialEffect):
    """Three fin funnels unfold a triangular barrier around the current pointer."""

    RACK_HOLD = 0.16
    RACK_STAGGER = 0.065
    RACK_FLIGHT = 0.22
    RACK_EXIT_END = 0.74
    RACK_BEAT = 0.30
    RACK_END = RACK_EXIT_END + RACK_BEAT
    RACK_SIZE = 132
    RACK_ANGLES = (4, 4, 8, 8, 12, 12)
    RACK_FOLDED = (2, 3)
    # First contact between the rotated outlines; avoid covering another face.
    RACK_PAIR_OFFSETS = (0, 18, 34)
    OPEN_END = 0.56
    HINGE_BEAT = 0.30

    @property
    def has_rack(self):
        return self.e.art.sheet.stem in ("フィンファンネル", "νガンダムHWS")

    def __init__(self, config, engine):
        super().__init__(config, engine)
        if self.has_rack:
            self.lifetime += self.RACK_END + self.HINGE_BEAT

    def field_progress(self, elapsed):
        local = elapsed - (self.RACK_END if self.has_rack else 0)
        if self.has_rack:
            opened_at = self.c["duration"] * self.OPEN_END
            local = min(local, opened_at) + max(0, local - opened_at - self.HINGE_BEAT)
        return local / self.c["duration"]

    def rack_layout(self, elapsed):
        layout = []
        for index in range(6):
            age = elapsed - self.RACK_HOLD - (5 - index) * self.RACK_STAGGER
            # The left-backpack bank appears on the viewer's right in front
            # view: six connected plates, rising toward the outermost one.
            pair = index // 2
            x, y = CENTER + 20 + self.RACK_PAIR_OFFSETS[pair], CENTER + 22 - pair * 24
            if age > 0:
                y -= 240 * (age / self.RACK_FLIGHT) ** 2
            if y > -self.RACK_SIZE / 2 - 24:
                layout.append((index, (x, y), age > 0))
        return layout

    def draw(self, frame, draw):
        elapsed = self.e.now - self.event.time
        if self.has_rack and elapsed < self.RACK_END:
            layout = self.rack_layout(elapsed)
            entries = {index: (pos, launched) for index, pos, launched in layout}
            joined = set()
            half = self.RACK_SIZE / 2
            # Render each stored pair as a single joined image. Splitting into
            # independent halves happens only as its right-hand unit launches.
            for index in (0, 2, 4):
                if all(i in entries and not entries[i][1] for i in (index, index + 1)):
                    joined.update((index, index + 1))
                    pos = entries[index][0]
                    image = self.e.art.rack_frame(self.RACK_SIZE, self.RACK_ANGLES[index],
                                                  index in self.RACK_FOLDED)
                    self.e.stamp(frame, image, (pos[0] - half, pos[1] - half), self.c["opacity"])
            for index, pos, launched in layout:
                if index in joined:
                    continue
                bank = self.RACK_ANGLES[index]
                folded = index in self.RACK_FOLDED
                image = self.e.art.rack_frame(self.RACK_SIZE, bank, folded, index % 2)
                if launched:
                    age = elapsed - self.RACK_HOLD - (5 - index) * self.RACK_STAGGER
                    speed = clamp(age / self.RACK_FLIGHT)
                    nozzle = self.RACK_SIZE * (0.04 if folded else 0.44)
                    side = (index % 2 - 0.5) * round(self.RACK_SIZE * 0.92 * 0.075)
                    x = pos[0] + side * math.cos(math.radians(bank)) + nozzle * math.sin(math.radians(bank))
                    y = pos[1] - side * math.sin(math.radians(bank)) + nozzle * math.cos(math.radians(bank))
                    draw.line([(x, y), (x, y + 6 + 24 * speed)],
                              fill=tint((115, 195, 255), self.c["opacity"] * speed * 0.65), width=3)
                    draw.line([(x, y), (x, y + 4 + 15 * speed)],
                              fill=tint((230, 250, 255), self.c["opacity"] * speed), width=1)
                self.e.stamp(frame, image, (pos[0] - half, pos[1] - half), self.c["opacity"])
            return
        progress = self.field_progress(elapsed)
        # Travel folded, pivot to face the center, open both rails, then energize the field.
        travel = clamp(progress / 0.28)
        travel = travel * travel * (3 - 2 * travel)
        opening = clamp((progress - 0.28) / 0.28)
        strength = clamp((progress - self.OPEN_END) / 0.1) * clamp((1 - progress) / 0.21)
        radius = 8 + self.c["radius"] * travel
        center = (CENTER, CENTER)
        outward = [-math.pi / 2 + i * TAU / 3 for i in range(3)]
        vertices = [point(*center, radius, angle) for angle in outward]
        if self.has_rack:
            # Three of the six return from above into the existing field
            # formation; the other three continue flying outside the viewport.
            vertices = [((CENTER + 20 + self.RACK_PAIR_OFFSETS[(5 - i) // 2]) * (1 - travel) + x * travel,
                         -72 * (1 - travel) + y * travel)
                        for i, (x, y) in enumerate(vertices)]
        if strength > 0:
            apex = (CENTER + radius * 0.10, CENTER + radius * 0.17)
            for i, a in enumerate(vertices):
                b = vertices[(i + 1) % 3]
                draw.polygon([apex, a, b], fill=self.ink(strength * (0.07 + i * 0.035)))
            for vertex in vertices:
                draw.line([vertex, apex], fill=self.ink(strength * 0.42), width=1)
            draw.line(vertices + vertices[:1], fill=self.ink(strength * 0.23), width=5)
            draw.line(vertices + vertices[:1], fill=self.ink(strength), width=2)
        turn = clamp((progress - 0.10) / 0.24)
        turn = turn * turn * (3 - 2 * turn)
        opacity = clamp(progress / 0.06) * clamp((1 - progress) / 0.16) * self.c["opacity"]
        for vertex, angle in zip(vertices, outward):
            heading = angle + math.pi * turn
            if self.has_rack:
                heading = -math.pi / 2 * (1 - turn) + (angle + math.pi) * turn
            self.e.fly(frame, vertex, heading, round(opening * 3), 44, opacity, deploying=True)


LAYERS = {
    "trail": Trail,
    "particles": Particles,
    "rare": Rare,
    "deploy": Deploy,
    "followers": Followers,
    "spiral": SpiralBits,
    "barrier": DeltaField,
    "volley": RemoteVolley,
    "dragoon": DragoonVolley,
    "pods": PodVolley,
    "rifle": RifleVolley,
    "shield": ShieldFunnels,
    "gund": GundBits,
    "biton": BitOn,
    "stun": StunBits,
    "incom": WiredIncom,
    "missile": FunnelMissiles,
    "cannon": LongRangeCannon,
    "idle": Idle,
    "boost": Boost,
    "click": Click,
}


class EffectEngine:
    def __init__(self, sprite, appearance, config, path=None, seed=None):
        self.sprite, self.config = sprite, config
        self.special = special_group(f"{path.parent.name}/{path.name}") if path else None
        self.hot, back = anchors(sprite, path)
        self.rear = CENTER + back[0] - self.hot[0], CENTER + back[1] - self.hot[1]
        dx, dy = back[0] - self.hot[0], back[1] - self.hot[1]
        length = math.hypot(dx, dy)
        self.axis = (dx / length, dy / length) if length else (0.707, 0.707)
        self.art = FlightArt(path, sprite, self.axis)
        self.idle_sheet = idle_sheet(path)
        self.nozzle, colors = appearance
        self.colors = [ImageColor.getrgb(color) for color in colors]
        self.rng = random.Random(seed)
        self.budget = 1.0
        self.reset()

    def reset(self):
        self.pos = self.last_time = None
        self.has_moved = False
        self.idle_turn_step = None
        self.heading = -3 * math.pi / 4
        self.deploy = self.rare_formation = self.speed = 0
        self.layers = [
            (SazabiLaunch if k == "volley" and self.art.sheet and self.art.sheet.stem == "サザビー"
             else cls)(self.config[k], self)
            for k, cls in LAYERS.items()
            if self.config[k]["enabled"] and (k not in SPECIAL or k == self.special)
        ]

    def local(self, pos):
        return CENTER + pos[0] - self.pos[0], CENTER + pos[1] - self.pos[1]

    @property
    def pointer_image(self):
        if self.idle_turn_step is not None:
            return turn_frame(self.idle_sheet, self.idle_turn_step, self.sprite.width)
        return self.sprite

    def fly(self, frame, pos, heading, pose, size, opacity, deploying=False):
        image = self.art.frame(heading, pose, size, deploying)
        self.stamp(frame, image, (pos[0] - image.width / 2, pos[1] - image.height / 2), opacity)

    @staticmethod
    def stamp(frame, sprite, pos, opacity):
        if opacity <= 0:
            return
        x, y = map(round, pos)
        if x + sprite.width <= 0 or y + sprite.height <= 0 or x >= frame.width or y >= frame.height:
            return
        copy = sprite.copy()
        copy.putalpha(sprite.getchannel("A").point([round(n * opacity) for n in range(256)]))
        frame.alpha_composite(copy, (x, y))

    def step(self, pos, now, clicks=()):
        if pos is None:
            if self.pos is not None:
                self.reset()
            return None
        if self.pos is not None and (math.dist(pos, self.pos) > 400 or now - self.last_time > 2):
            self.reset()
        first = self.pos is None
        elapsed = 1 / 60 if first else max(0.0001, now - self.last_time)
        self.dt = min(0.12, elapsed)
        self.now = self.last_time = now
        self.inputs = clicks
        self.clicks = [event for event in clicks if event.kind in ("left", "right", "double")]
        previous = pos if first else self.pos
        self.pos = pos
        self.delta = pos[0] - previous[0], pos[1] - previous[1]
        distance = math.hypot(*self.delta)
        self.moved = distance > 0
        if first:
            self.last_motion = now
        old_still = now - self.last_motion
        self.started = self.moved and (old_still >= 0.14 or not self.has_moved)
        self.stopped = not self.moved and self.has_moved and self.still < 0.14 <= old_still
        if self.moved:
            self.has_moved = True
            self.last_motion = now
            self.heading = math.atan2(pos[1] - previous[1], pos[0] - previous[0])
        self.still = now - self.last_motion
        self.speed = min(10000, distance / elapsed)
        self.idle_turn_step = None
        visible = [layer for layer in self.layers if layer.update()]
        if not visible:
            return None
        frame = Image.new("RGBA", (OVERLAY_SIZE, OVERLAY_SIZE))
        draw = ImageDraw.Draw(frame)
        for layer in visible:
            layer.draw(frame, draw)
        draw.ellipse(box(CENTER, CENTER, 2), fill=(0, 0, 0, 0))
        return frame
