"""Visual-only size and parallel firing for the existing sprite controllers."""

import math
from collections import deque


class EscortOptions:
    def __init__(self, config, fire_factory):
        self.ratio = config["size_percent"] / 100
        self.enabled = config["fire_enabled"]
        self.fires = [fire_factory() for _ in range(3)]
        self.reset()

    def reset(self):
        for f in self.fires:
            f.reset()
        self.pending = deque()
        self.trails = [deque(maxlen=128) for _ in range(3)]
        self.locked = False
        self.last_heading = None
        self.release = None

    def input(self, kind, t):
        if not self.enabled:
            return
        if kind == "left":
            self.locked = True
            self.release = None
        if kind in ("left", "left_up"):
            method = "down" if kind == "left" else "up"
            for i in range(3):
                self.pending.append((t + 0.1 * (i + 1), i, method))
            self.pending = deque(sorted(self.pending))

    def transform(self, items, primary, now, fin=False):
        while self.pending and self.pending[0][0] <= now:
            due, i, method = self.pending.popleft()
            getattr(self.fires[i], method)(due)
        output, effects = [], []
        center_key, angle_key = (
            ("xy", "heading") if fin else ("draw_position", "draw_heading")
        )
        primary_angle = primary[angle_key]
        active = self.locked or self.pending
        if active:
            self.last_heading = primary_angle
        for index, source in enumerate(items):
            item = dict(source)
            center = source[center_key]
            correction = primary.get("beam_heading", primary_angle) - source.get(
                "beam_heading", source[angle_key]
            )
            angle = source[angle_key] + correction if active else source[angle_key]
            if self.release is not None and self.last_heading is not None:
                u = min(1, (now - self.release) / 0.24)
                angle = (
                    self.last_heading
                    + (
                        (source[angle_key] - self.last_heading + math.pi) % math.tau
                        - math.pi
                    )
                    * u
                )
            delta = angle - source[angle_key]
            c, s = math.cos(delta), math.sin(delta)

            def point(p):
                x, y = (p[0] - center[0]) * self.ratio, (p[1] - center[1]) * self.ratio
                return (center[0] + c * x - s * y, center[1] + s * x + c * y)

            item[angle_key] = angle
            item["scale"] *= self.ratio
            for key in ("muzzle", "nozzle", "front", "grid"):
                if key in item:
                    item[key] = point(item[key])
            for key in ("nozzles", "holes", "channel"):
                if key in item:
                    item[key] = [point(p) for p in item[key]]
            if "rear" in item:
                x, y = item["rear"]
                item["rear"] = (c * x - s * y, s * x + c * y)
            item["beam_heading"] = (
                primary.get("beam_heading", primary_angle) if active else angle
            )
            target = dict(item, muzzle=item.get("muzzle", item.get("front")))
            shots = self.fires[index].sample(now, target) if self.enabled else []
            for shot in shots:
                shot["owner"] = item["id"]
            effects.extend(shots)
            if fin:
                track = self.trails[index]
                nozzles = item["nozzles"]
                midpoint = tuple(sum(p[j] for p in nozzles)/len(nozzles) for j in (0,1))
                speed = math.hypot(*item.get("velocity",(0,0)))
                if speed > 8 and item["power"] > .1:
                    track.append((now, midpoint, item["power"]))
                while track and now-track[0][0] > .4:
                    track.popleft()
                item["trail"] = list(track)
            item["shots"] = shots
            item["charge"] = max(
                (e["power"] for e in shots if e["stage"] == "charge"), default=0.0
            )
            output.append(item)
        for fire in self.fires[len(items) :]:
            fire.sample(now, dict(muzzle=(0, 0), beam_heading=primary_angle, scale=1))
        if (
            self.locked
            and not self.pending
            and all(f.held is None and not f.shots for f in self.fires)
        ):
            self.locked = False
            self.release = now
        return output, effects


def draw_fin_shots(image, states):
    from PIL import ImageDraw

    out = image.copy()
    pen = ImageDraw.Draw(out)
    for state in states:
        for shot in state.get("shots", ()):
            power = shot["power"]
            if shot["stage"] == "charge":
                pen.line(
                    state["channel"],
                    fill=(155, 132, 255, round(190 * power)),
                    width=max(1, round(3 * state["scale"])),
                )
            else:
                x, y = shot["origin"]
                h = shot["heading"]
                length = 1200 * min(1, shot["age"] / 0.06)
                end = (x + math.cos(h) * length, y + math.sin(h) * length)
                pen.line(
                    ((x, y), end),
                    fill=(151, 126, 255, round(220 * power)),
                    width=max(2, round(8 * shot["scale"])),
                )
                pen.line(
                    ((x, y), end),
                    fill=(241, 238, 255, round(255 * power)),
                    width=max(1, round(3 * shot["scale"])),
                )
    return out
