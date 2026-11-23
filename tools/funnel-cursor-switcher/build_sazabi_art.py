"""Frame the reference-based Sazabi atlas without changing cursor hotspots."""

from pathlib import Path
import struct

from PIL import Image

from build_qubeley_art import dib, pointing_image, visible_bounds


ROOT = Path(__file__).resolve().parent
NAME = "サザビー"
FOLDER = ROOT / "飛行アニメ" / "ファンネル"


def source_poses():
    with Image.open(FOLDER / (NAME + ".原画.png")) as image:
        atlas = image.convert("RGBA")
    for index in range(4):
        source = atlas.crop((round(atlas.width * index / 4), 0,
                             round(atlas.width * (index + 1) / 4), atlas.height))
        yield source.crop(visible_bounds(source))


def frame_source(source, scale=None):
    """Register on the front muzzle rather than an opening cover's bounds."""
    ys = [y for y in range(source.height) for x in range(round(source.width * 0.92), source.width)
          if source.getpixel((x, y))[3] >= 144]
    muzzle_y = (min(ys) + max(ys)) / 2
    scale = scale if scale is not None else min(84 / source.width, 88 / source.height)
    body = source.resize((round(source.width * scale), round(source.height * scale)),
                         Image.Resampling.LANCZOS)
    cell = Image.new("RGBA", (96, 96))
    cell.alpha_composite(body, (90 - body.width, round(48 - muzzle_y * scale)))
    return cell


def build():
    sources = list(source_poses())
    sheet = Image.new("RGBA", (384, 96))
    # Opening the covers must not resize the unchanged red front head.
    scale = min(min(84 / source.width, 88 / source.height) for source in sources)
    for index, source in enumerate(sources):
        sheet.alpha_composite(frame_source(source, scale), (index * 96, 0))
    sheet.save(FOLDER / (NAME + ".png"))

    rear_path = FOLDER / (NAME + ".後方原画.png")
    if rear_path.is_file():
        with Image.open(rear_path) as image:
            rear = image.convert("RGBA")
        cell = frame_source(rear.crop(visible_bounds(rear)))
        sheet = Image.new("RGBA", (384, 96))
        for index in range(4):
            sheet.alpha_composite(cell, (index * 96, 0))
        sheet.save(FOLDER / (NAME + ".後方.png"))

    path = ROOT / "カーソル" / "ファンネル" / (NAME + ".cur")
    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 2)
    directory, bodies = [], []
    offset = 6 + count * 16
    for i in range(count):
        w, h, colors, unused, hx, hy, _, _ = struct.unpack_from("<BBBBHHII", data, 6 + i * 16)
        assert w == h
        frame = pointing_image(sources[0], w or 256, (hx, hy))
        payload = dib(frame)
        directory.append(struct.pack("<BBBBHHII", w, h, colors, unused, hx, hy, len(payload), offset))
        bodies.append(payload)
        offset += len(payload)
        if w == 32:
            frame.save(path.with_suffix(".png"))
    path.write_bytes(struct.pack("<HHH", 0, 2, count) + b"".join(directory) + b"".join(bodies))


if __name__ == "__main__":
    build()
