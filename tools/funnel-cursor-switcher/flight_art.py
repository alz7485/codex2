"""Direction-aware, four-pose artwork for flying equipment. Frame centers are pivots."""

from functools import lru_cache
import math
from pathlib import Path
import sys

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


@lru_cache(maxsize=120)
def hinged_pose(path, pose):
    """Open the two folded rails to a 60-degree V, about the shared hinge.

    The authored strips use the cell center as pivot and +X as forward.
    Reuse their folded artwork so the equipment's colours and rail details
    survive, but do not use the old, straightened final deployment cel.
    """
    folded = read_poses(path)[0]
    result = Image.new("RGBA", folded.size)
    for side, region in ((1, (0, 0, CELL, CELL // 2)), (-1, (0, CELL // 2, CELL, CELL))):
        rail = Image.new("RGBA", folded.size)
        rail.paste(folded.crop(region), region[:2])
        result.alpha_composite(rail.rotate(side * pose * 10, Image.Resampling.BICUBIC))
    return result


@lru_cache(maxsize=2048)
def turned_pose(path, pose, direction, size, deploying=False):
    source = hinged_pose(path, pose) if deploying else read_poses(path)[pose]
    turned = source.rotate(-360 * direction / HEADINGS, Image.Resampling.BICUBIC)
    return turned.resize((size, size), Image.Resampling.LANCZOS)


@lru_cache(maxsize=1)
def shield_source():
    """Align the illustrated shield's CENTRAL disk to the rotation pivot.

    The photograph-based artwork has a long forked end and a shorter opposite
    armour panel, with four teal X fins around its hub at image pixel (500, 615).
    Keep both ends: a rear-pivot spear silhouette loses the shield's structure.
    """
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    path = root / "飛行アニメ" / "ファンネル" / "ユニコーン.正面.png"
    with Image.open(path) as image:
        source = image.convert("RGBA")
    side = CELL * 4
    factor = side * 0.82 / source.width
    inverse = 1 / factor
    return source.transform((side, side), Image.Transform.AFFINE,
                            (inverse, 0, 500 - side / 2 * inverse,
                             0, inverse, 615 - side / 2 * inverse),
                            Image.Resampling.BICUBIC)


@lru_cache(maxsize=256)
def long_range_pose(path, pose, direction, size):
    source = read_poses(path)[pose]
    heading = direction * math.tau / HEADINGS
    base = 0
    if math.cos(heading) < 0:
        # Facing left keeps the blue upper rail above the white lower rail.
        source = source.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        base = math.pi
    turned = source.rotate(math.degrees(base - heading), Image.Resampling.BICUBIC)
    return turned.resize((size, size), Image.Resampling.LANCZOS)


@lru_cache(maxsize=720)
def shield_face(direction, size):
    turned = shield_source().rotate(-direction, Image.Resampling.BICUBIC)
    return turned.resize((size, size), Image.Resampling.LANCZOS)


@lru_cache(maxsize=32)
def front_rack_pose(path, size, bank, fold_lower, part):
    with Image.open(path) as image:
        source = image.convert("RGBA")
    bounds = source.getchannel("A").point(lambda a: 255 if a >= 144 else 0).getbbox()
    source = source.crop(bounds)
    full_height = round(size * 0.92)
    height = round(full_height * (0.56 if fold_lower else 1))
    # An even-width joined pair supplies two exact, gap-free halves for launch.
    width = 2 * round(full_height * 0.075)
    if path.name.startswith("フィンファンネル.3D"):
        # Tapered units overlap slightly in the front view. Draw an entire
        # unit both in the rack and on release, including its wider shoulder.
        unit = source.crop((0, 0, source.width // 2, source.height))
        unit_width = round(width * .62)
        unit = unit.resize((unit_width, height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (size, size))
        for index in ((0, 1) if part is None else (part,)):
            x = (size - width) // 2 + index * (width - unit_width)
            canvas.alpha_composite(unit, (x, (size-full_height)//2))
        return canvas.rotate(bank, Image.Resampling.BICUBIC)
    source = source.resize((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size))
    x = (size - width) // 2
    if part is not None:
        half = width // 2
        source = source.crop((part * half, 0, (part + 1) * half, height))
        x += part * half
    canvas.alpha_composite(source, (x, (size - full_height) // 2))
    return canvas.rotate(bank, Image.Resampling.BICUBIC)


@lru_cache(maxsize=1)
def field_photos(path):
    with Image.open(path) as atlas:
        if atlas.size != (4*192, 5*192):
            raise ValueError("フィンファンネルのバリア画像のサイズが不正です。")
        return tuple(atlas.crop((p*192,s*192,(p+1)*192,(s+1)*192)).convert("RGBA")
                     for s in range(5) for p in range(4))


@lru_cache(maxsize=512)
def field_photo(path, station, pose, offset, size):
    photo = field_photos(path)[4*station+pose]
    if offset:
        photo = photo.rotate(-offset*360/HEADINGS,Image.Resampling.BICUBIC)
    return photo.resize((size,size),Image.Resampling.LANCZOS)


class FlightArt:
    def rear_frame(self, heading, size):
        """Use separately authored rear artwork when a funnel flies into depth."""
        path = self.sheet.with_name(self.sheet.stem + ".後方.png") if self.sheet else None
        if path and read_poses(path):
            direction = round(heading * HEADINGS / math.tau) % HEADINGS
            return turned_pose(path, 0, direction, size)
        return self.frame(heading, 3, size)

    def rack_frame(self, size, bank=8, fold_lower=False, part=None):
        if self.sheet and self.sheet.stem in ("フィンファンネル", "νガンダムHWS"):
            prefix = "フィンファンネル.3D" if self.sheet.stem == "フィンファンネル" else "フィンファンネル."
            front = self.sheet.parent / (prefix + ("収納中央.png" if fold_lower else "収納正面.png"))
            if front.is_file():
                return front_rack_pose(front, size, bank, fold_lower, part)
        poses = read_poses(self.deployment) if self.deployment else ()
        if poses:
            return poses[3].resize((size, size), Image.Resampling.LANCZOS)
        return self.frame(-math.pi / 2, 0, size)

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
            if self.sheet.stem == "ロングレンジ・フィン・ファンネル（RX-93ff）":
                return long_range_pose(path, pose, direction, size)
            return turned_pose(path, pose, direction, size, deploying and self.sheet.stem != "フィンファンネル")
        # User-added cursors can fly without supplying an animation strip.
        angle = math.degrees(self.forward) - direction * 360 / HEADINGS
        image = self.sprite.rotate(angle, Image.Resampling.BICUBIC, expand=True)
        ratio = size / max(self.sprite.size)
        return image.resize(tuple(max(1, round(n * ratio)) for n in image.size), Image.Resampling.LANCZOS)

    @staticmethod
    def shield_frame(heading, size):
        direction = round(math.degrees(heading)) % 360
        return shield_face(direction, size)
