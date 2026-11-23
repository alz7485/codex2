"""One input sample and one transparent frame for both Windows and the editor."""

import math
import random
from collections import deque
from dataclasses import dataclass

from PIL import Image, ImageColor, ImageDraw

from cursor_art import NOZZLES, OVERLAY_SIZE, anchors

from effect_settings import BUTTONS, MODIFIERS, SPECIAL, special_group

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
            self.samples.append((e.pos, e.now, life))
            self.last = e.now
        while self.samples and e.now - self.samples[0][1] >= self.samples[0][2]:
            self.samples.popleft()
        return bool(self.samples)

    def draw(self, frame, draw):
        e, c = self.e, self.c
        previous = None
        last_mid = None
        for pos, born, life in list(self.samples)[-max(2, round(len(self.samples) * e.budget)) :]:
            remaining = clamp(1 - (e.now - born) / life)
            x, y = e.local(pos)
            if c["style"] == "残像":
                e.stamp(frame, e.sprite, (x - e.hot[0], y - e.hot[1]), remaining * c["opacity"] * 0.46)
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

    def update(self):
        target = 1 if self.e.still >= self.c["delay"] else 0
        step = self.e.dt * 1000 / self.c["fade"]
        self.level += clamp(target - self.level, -step, step)
        return self.level > 0

    def draw(self, frame, draw):
        c, e = self.c, self.e
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
        size = tuple(max(2, round(n * config["scale"])) for n in engine.sprite.size)
        self.sprite = engine.sprite.resize(size, Image.Resampling.LANCZOS)
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
        return True

    def draw(self, frame, draw):
        c = self.c
        for dx, dy in self.positions:
            x, y = CENTER + dx, CENTER + dy
            if c["style"] == "装備画像":
                w, h = self.sprite.size
                self.e.stamp(frame, self.sprite, (x - w / 2, y - h / 2), c["opacity"])
            else:
                r = self.sprite.width / 2
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
        size = tuple(max(1, round(n * 0.46)) for n in engine.sprite.size)
        self.sprite = engine.sprite.resize(size, Image.Resampling.LANCZOS)

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

    def bit(self, frame, pos, opacity):
        x, y = pos
        self.e.stamp(frame, self.sprite, (x - self.sprite.width / 2, y - self.sprite.height / 2), opacity)


class SpiralBits(SpecialEffect):
    STAGGER = 0.035

    def __init__(self, config, engine):
        super().__init__(config, engine)
        self.lifetime += (config["count"] - 1) * self.STAGGER

    def location(self, origin, index, progress):
        radius = 7 + (self.c["radius"] - 7) * progress
        angle = -3 * math.pi / 4 + TAU * (index / self.c["count"] + self.c["turns"] * progress)
        return point(*origin, radius, angle)

    def draw(self, frame, draw):
        origin = self.e.local(self.event.pos)
        for index in range(self.c["count"]):
            age = self.e.now - self.event.time - index * self.STAGGER
            progress = age / self.c["duration"]
            if not 0 <= progress < 1:
                continue
            fade = min(1, (1 - progress) / 0.25)
            head = self.location(origin, index, progress)
            last = head
            for step in range(1, 7):
                tail = self.location(origin, index, max(0, progress - step * 0.017))
                draw.line([last, tail], fill=self.ink(fade * (7 - step) / 8), width=2 if step < 3 else 1)
                last = tail
            self.bit(frame, head, fade * self.c["opacity"])


class DeltaField(SpecialEffect):
    """Three fin funnels unfold a triangular barrier around the current pointer."""

    def draw(self, frame, draw):
        progress = (self.e.now - self.event.time) / self.lifetime
        unfold = clamp(progress / 0.24)
        unfold = unfold * unfold * (3 - 2 * unfold)
        fade = clamp((1 - progress) / 0.28)
        strength = unfold * fade
        radius = 7 + self.c["radius"] * unfold
        center = (CENTER, CENTER)
        vertices = [point(*center, radius, -math.pi / 2 + i * TAU / 3) for i in range(3)]
        apex = (CENTER + radius * 0.10, CENTER + radius * 0.17)
        for i, a in enumerate(vertices):
            b = vertices[(i + 1) % 3]
            draw.polygon([apex, a, b], fill=self.ink(strength * (0.07 + i * 0.035)))
        for vertex in vertices:
            draw.line([vertex, apex], fill=self.ink(strength * 0.42), width=1)
        draw.line(vertices + vertices[:1], fill=self.ink(strength * 0.23), width=5)
        draw.line(vertices + vertices[:1], fill=self.ink(strength), width=2)
        for vertex in vertices:
            self.bit(frame, vertex, strength * self.c["opacity"])


LAYERS = {
    "trail": Trail,
    "particles": Particles,
    "rare": Rare,
    "deploy": Deploy,
    "followers": Followers,
    "spiral": SpiralBits,
    "barrier": DeltaField,
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
        self.nozzle, colors = appearance
        self.colors = [ImageColor.getrgb(color) for color in colors]
        self.rng = random.Random(seed)
        self.budget = 1.0
        self.reset()

    def reset(self):
        self.pos = self.last_time = None
        self.has_moved = False
        self.heading = -3 * math.pi / 4
        self.deploy = self.rare_formation = self.speed = 0
        self.layers = [
            cls(self.config[k], self)
            for k, cls in LAYERS.items()
            if self.config[k]["enabled"] and (k not in SPECIAL or k == self.special)
        ]

    def local(self, pos):
        return CENTER + pos[0] - self.pos[0], CENTER + pos[1] - self.pos[1]

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
        visible = [layer for layer in self.layers if layer.update()]
        if not visible:
            return None
        frame = Image.new("RGBA", (OVERLAY_SIZE, OVERLAY_SIZE))
        draw = ImageDraw.Draw(frame)
        for layer in visible:
            layer.draw(frame, draw)
        draw.ellipse(box(CENTER, CENTER, 2), fill=(0, 0, 0, 0))
        return frame
