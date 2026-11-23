"""Direction-aware, four-pose artwork for flying equipment. Frame centers are pivots."""

from functools import lru_cache
import math

from PIL import Image


CELL = 96
HEADINGS = 48


@lru_cache(maxsize=40)
def read_poses(path):
    try:
        with Image.open(path) as sheet:
            if sheet.size != (4 * CELL, CELL):
                return ()
            return tuple(sheet.crop((i * CELL, 0, (i + 1) * CELL, CELL)).convert("RGBA") for i in range(4))
    except (OSError, ValueError):
        return ()


@lru_cache(maxsize=2048)
def turned_pose(path, pose, direction, size):
    source = read_poses(path)[pose]
    turned = source.rotate(-360 * direction / HEADINGS, Image.Resampling.BICUBIC)
    return turned.resize((size, size), Image.Resampling.LANCZOS)


class FlightArt:
    def __init__(self, cursor, sprite, axis):
        self.sprite = sprite
        self.forward = math.atan2(-axis[1], -axis[0])
        self.sheet = self.deployment = None
        if cursor:
            folder = cursor.parent.parent.parent / "飛行アニメ" / cursor.parent.name
            self.sheet = folder / (cursor.stem + ".png")
            self.deployment = folder / (cursor.stem + ".展開.png")

    def frame(self, heading, pose, size, deploying=False):
        path = self.deployment if deploying else self.sheet
        direction = round(heading * HEADINGS / math.tau) % HEADINGS
        if path and read_poses(path):
            return turned_pose(path, pose, direction, size)
        # User-added cursors can fly without supplying an animation strip.
        angle = math.degrees(self.forward) - direction * 360 / HEADINGS
        image = self.sprite.rotate(angle, Image.Resampling.BICUBIC, expand=True)
        ratio = size / max(self.sprite.size)
        return image.resize(tuple(max(1, round(n * ratio)) for n in image.size), Image.Resampling.LANCZOS)
