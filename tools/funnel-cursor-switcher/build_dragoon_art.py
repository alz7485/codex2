"""Frame the reference-based Strike Freedom Super DRAGOON illustration.

The other DRAGOON design and frozen equipment are not rebuilt by this script.
Preserve the existing Windows frame sizes and all hotspot coordinates.
"""

from pathlib import Path
import struct

from PIL import Image

from build_qubeley_art import dib, pointing_image, visible_bounds


ROOT = Path(__file__).resolve().parent
NAME = "ストライクフリーダム"


def read_source():
    path = ROOT / "飛行アニメ" / "ドラグーン" / (NAME + ".原画.png")
    with Image.open(path) as image:
        source = image.convert("RGBA")
    return source.crop(visible_bounds(source))


def build():
    source = read_source()
    # Keep the long, thin blade's proportions. Tiny banks provide four poses.
    height = max(8, round(86 * source.height / source.width))
    sheet = Image.new("RGBA", (384, 96))
    for i, (scale, bank) in enumerate(((1, 0), (0.94, -2), (0.86, 0), (0.98, 2))):
        body = source.resize((86, max(8, round(height * scale))), Image.Resampling.LANCZOS)
        cell = Image.new("RGBA", (96, 96))
        cell.alpha_composite(body, (5, (96 - body.height) // 2))
        sheet.alpha_composite(cell.rotate(bank, Image.Resampling.BICUBIC), (i * 96, 0))
    sheet.save(ROOT / "飛行アニメ" / "ドラグーン" / (NAME + ".png"))

    path = ROOT / "カーソル" / "ドラグーン" / (NAME + ".cur")
    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 2)
    entries, bodies = [], []
    offset = 6 + count * 16
    for i in range(count):
        w, h, colors, unused, hx, hy, _, _ = struct.unpack_from("<BBBBHHII", data, 6 + i * 16)
        assert w == h
        # A slightly flatter upper-left angle fits the very slender blade at
        # full size while preserving the existing inset hotspot.
        frame = pointing_image(source, w or 256, (hx, hy), angle=138)
        payload = dib(frame)
        entries.append(struct.pack("<BBBBHHII", w, h, colors, unused, hx, hy, len(payload), offset))
        bodies.append(payload)
        offset += len(payload)
        if w == 32:
            frame.save(path.with_suffix(".png"))
    path.write_bytes(struct.pack("<HHH", 0, 2, count) + b"".join(entries) + b"".join(bodies))


if __name__ == "__main__":
    build()
