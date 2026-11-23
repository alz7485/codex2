"""Rebuild Unicorn cursor frames from its detailed shield artwork, retaining hotspots."""

from pathlib import Path
import struct

from PIL import Image

from build_qubeley_art import dib, pointing_image, visible_bounds


ROOT = Path(__file__).resolve().parent
NAME = "ユニコーン"


def read_source():
    path = ROOT / "飛行アニメ" / "ファンネル" / (NAME + ".正面.png")
    with Image.open(path) as image:
        source = image.convert("RGBA")
    return source.crop(visible_bounds(source))


def build():
    source = read_source()
    path = ROOT / "カーソル" / "ファンネル" / (NAME + ".cur")
    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 2)
    entries, bodies = [], []
    offset = 6 + count * 16
    for i in range(count):
        w, h, colors, unused, hx, hy, _, _ = struct.unpack_from("<BBBBHHII", data, 6 + i * 16)
        assert w == h
        frame = pointing_image(source, w or 256, (hx, hy), angle=135)
        payload = dib(frame)
        entries.append(struct.pack("<BBBBHHII", w, h, colors, unused, hx, hy, len(payload), offset))
        bodies.append(payload)
        offset += len(payload)
        if w == 32:
            frame.save(path.with_suffix(".png"))
    path.write_bytes(struct.pack("<HHH", 0, 2, count) + b"".join(entries) + b"".join(bodies))


if __name__ == "__main__":
    build()
