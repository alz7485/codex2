"""Convert the illustrated three-row atlas into flight cels and Windows CURs.

The atlas supplies the actual design; this builder only frames, rotates and
encodes it. Existing cursor resolutions and hotspot coordinates are preserved.
"""

from pathlib import Path
import struct

from PIL import Image


ROOT = Path(__file__).resolve().parent
NAMES = ("キュベレイ", "キュベレイMk-II（プル機）", "キュベレイMk-II（プルツー機）")


def visible_bounds(image):
    return image.getchannel("A").point(lambda a: 255 if a >= 32 else 0).getbbox()


def source_rows():
    with Image.open(ROOT / "飛行アニメ" / "キュベレイ系.原画.png") as atlas:
        atlas = atlas.convert("RGBA")
    for index in range(3):
        band = atlas.crop((0, round(atlas.height * index / 3),
                           atlas.width, round(atlas.height * (index + 1) / 3)))
        yield band.crop(visible_bounds(band))


def pointing_image(source, side, hotspot, angle=135):
    pointing = source.rotate(angle, Image.Resampling.BICUBIC, expand=True)
    pointing = pointing.crop(visible_bounds(pointing))
    pointing.thumbnail((side - hotspot[0], side - hotspot[1]), Image.Resampling.LANCZOS)
    alpha = pointing.getchannel("A")
    front = min(((x, y) for y in range(pointing.height) for x in range(pointing.width)
                 if alpha.getpixel((x, y)) >= 144), key=lambda p: (sum(p), p[1]))
    canvas = Image.new("RGBA", (side, side))
    canvas.alpha_composite(pointing, (hotspot[0] - front[0], hotspot[1] - front[1]))
    assert canvas.getpixel(hotspot)[3] >= 144
    return canvas


def dib(image):
    width, height = image.size
    stride = ((width + 31) // 32) * 4
    mask = bytearray(stride * height)
    alpha = image.getchannel("A")
    for row in range(height):
        for x in range(width):
            if alpha.getpixel((x, height - 1 - row)) == 0:
                mask[row * stride + x // 8] |= 128 >> (x % 8)
    header = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32, 0,
                         width * height * 4, 0, 0, 0, 0)
    return header + image.tobytes("raw", "BGRA", 0, -1) + mask


def build():
    for name, source in zip(NAMES, source_rows()):
        # Four subtle banks share the same CLOSED, round-backed geometry.
        sheet = Image.new("RGBA", (384, 96))
        for index, (height, bank) in enumerate(((34, 0), (32, -2), (30, 0), (33, 2))):
            body = source.resize((86, height), Image.Resampling.LANCZOS)
            cell = Image.new("RGBA", (96, 96))
            cell.alpha_composite(body, (5, (96 - height) // 2))
            cell = cell.rotate(bank, Image.Resampling.BICUBIC)
            sheet.alpha_composite(cell, (index * 96, 0))
        sheet.save(ROOT / "飛行アニメ" / "ファンネル" / (name + ".png"))

        path = ROOT / "カーソル" / "ファンネル" / (name + ".cur")
        previous = path.read_bytes()
        reserved, kind, count = struct.unpack_from("<HHH", previous)
        assert (reserved, kind) == (0, 2)
        directory, bodies = [], []
        offset = 6 + count * 16
        for index in range(count):
            w, h, colors, unused, hx, hy, _, _ = struct.unpack_from("<BBBBHHII", previous, 6 + index * 16)
            assert w == h
            side = w or 256
            image = pointing_image(source, side, (hx, hy))
            payload = dib(image)
            directory.append(struct.pack("<BBBBHHII", w, h, colors, unused, hx, hy, len(payload), offset))
            bodies.append(payload)
            offset += len(payload)
            if side == 32:
                image.save(path.with_suffix(".png"))
        path.write_bytes(struct.pack("<HHH", 0, 2, count) + b"".join(directory) + b"".join(bodies))


if __name__ == "__main__":
    build()
