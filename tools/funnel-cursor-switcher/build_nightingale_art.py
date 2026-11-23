"""Frame and encode the red, conical Nightingale illustration for the app."""

from pathlib import Path
import struct

from PIL import Image

from build_qubeley_art import dib, pointing_image, visible_bounds


ROOT = Path(__file__).resolve().parent


def build():
    folder = ROOT / "飛行アニメ" / "ファンネル"
    with Image.open(folder / "ナイチンゲール.原画.png") as image:
        source = image.convert("RGBA")
    source = source.crop(visible_bounds(source))
    sheet = Image.new("RGBA", (384, 96))
    for i, (height, bank) in enumerate(((34, 0), (32, -2), (30, 0), (33, 2))):
        body = source.resize((86, height), Image.Resampling.LANCZOS)
        cell = Image.new("RGBA", (96, 96))
        cell.alpha_composite(body, (5, (96 - height) // 2))
        sheet.alpha_composite(cell.rotate(bank, Image.Resampling.BICUBIC), (i * 96, 0))
    sheet.save(folder / "ナイチンゲール.png")

    path = ROOT / "カーソル" / "ファンネル" / "ナイチンゲール.cur"
    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 2)
    entries, frames = [], []
    offset = 6 + count * 16
    for i in range(count):
        w, h, colors, unused, hx, hy, _, _ = struct.unpack_from("<BBBBHHII", data, 6 + i * 16)
        assert w == h
        side = w or 256
        # Anchor the new narrow tip at the upper-left margin; the old oval's
        # inset hotspot would unnecessarily shrink the replacement silhouette.
        hx, hy = 0, max(1, round(side / 32))
        frame = pointing_image(source, side, (hx, hy))
        payload = dib(frame)
        entries.append(struct.pack("<BBBBHHII", w, h, colors, unused, hx, hy, len(payload), offset))
        frames.append(payload)
        offset += len(payload)
        if w == 32:
            frame.save(path.with_suffix(".png"))
    path.write_bytes(struct.pack("<HHH", 0, 2, count) + b"".join(entries) + b"".join(frames))


if __name__ == "__main__":
    build()
