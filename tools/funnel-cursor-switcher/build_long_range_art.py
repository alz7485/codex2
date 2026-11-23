"""Frame the two illustrated RX-93ff states and preserve Windows hotspots."""

import math
from pathlib import Path
import struct

from PIL import Image

from build_qubeley_art import dib, pointing_image, visible_bounds


ROOT = Path(__file__).resolve().parent
NAME = "ロングレンジ・フィン・ファンネル（RX-93ff）"
FOLDER = ROOT / "飛行アニメ" / "ファンネル"
CELL = 96


def read_source(opened=False):
    suffix = ".開放原画.png" if opened else ".原画.png"
    with Image.open(FOLDER / (NAME + suffix)) as image:
        return image.convert("RGBA")


def framed_source(opened=False):
    source = read_source(opened)
    # Both authored views use the same canvas and a common firing-axis pivot.
    angle = math.radians(8)
    c, s = math.cos(angle), math.sin(angle)
    rotated = source.rotate(8, Image.Resampling.BICUBIC, expand=True)
    bounds = visible_bounds(rotated)
    scale = 86 / (bounds[2] - bounds[0])
    px, py = source.width * 0.5, source.height * 0.554
    return source.transform((CELL, CELL), Image.Transform.AFFINE,
                            (c / scale, -s / scale, px - 48 * (c - s) / scale,
                             s / scale, c / scale, py - 48 * (s + c) / scale),
                            Image.Resampling.BICUBIC)


def opening_pose(closed, opened, pose):
    if pose == 0:
        return closed.copy()
    if pose == 3:
        return opened.copy()
    # Articulated front rails, rather than a crossfade of two silhouettes.
    pivot = (39, 48)
    result = Image.new("RGBA", opened.size)
    result.paste(opened.crop((0, 0, 39, CELL)), (0, 0))
    for region, sign in (((39, 0, CELL, 48), -1), ((39, 48, CELL, CELL), 1)):
        rail = Image.new("RGBA", opened.size)
        rail.paste(opened.crop(region), region[:2])
        result.alpha_composite(rail.rotate(sign * 6 * (1 - pose / 3),
                                          Image.Resampling.BICUBIC, center=pivot))
    return result


def build():
    closed, opened = framed_source(), framed_source(True)
    flight, firing = (Image.new("RGBA", (CELL * 4, CELL)) for _ in range(2))
    for pose, bank in enumerate((0, -2, -1, 2)):
        flight.alpha_composite(closed.rotate(bank, Image.Resampling.BICUBIC), (pose * CELL, 0))
        firing.alpha_composite(opening_pose(closed, opened, pose), (pose * CELL, 0))
    flight.save(FOLDER / (NAME + ".png"))
    firing.save(FOLDER / (NAME + ".展開.png"))

    path = ROOT / "カーソル" / "ファンネル" / (NAME + ".cur")
    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 2)
    # Normal pointer uses the closed artwork, aligned nose-first upper left.
    source = read_source().rotate(8, Image.Resampling.BICUBIC, expand=True)
    source = source.crop(visible_bounds(source))
    entries, bodies = [], []
    offset = 6 + count * 16
    for i in range(count):
        w, h, colors, unused, hx, hy, _, _ = struct.unpack_from("<BBBBHHII", data, 6 + i * 16)
        assert w == h
        # The existing Y hotspot inset is larger than X; a slightly flatter
        # upper-left angle fills the frame without changing the click point.
        frame = pointing_image(source, w or 256, (hx, hy), angle=142)
        payload = dib(frame)
        entries.append(struct.pack("<BBBBHHII", w, h, colors, unused, hx, hy, len(payload), offset))
        bodies.append(payload)
        offset += len(payload)
        if w == 32:
            frame.save(path.with_suffix(".png"))
    path.write_bytes(struct.pack("<HHH", 0, 2, count) + b"".join(entries) + b"".join(bodies))


if __name__ == "__main__":
    build()
