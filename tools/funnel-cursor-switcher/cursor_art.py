import struct

from PIL import Image, ImageDraw

OVERLAY_SIZE = 256


# Each nozzle is (base offset, tip offset, length multiplier, half-width).
NOZZLES = {
    "needle": ((0, 0, 1.14, 2.3),),
    "flare": ((0, 0, 0.86, 3.9),),
    "twin": ((-1.8, -3.8, 1.0, 1.9), (1.8, 3.6, 0.82, 1.8)),
    "fan": ((-2.8, -5.5, 0.65, 1.5), (0, 0, 0.9, 2.2), (2.8, 5.2, 0.7, 1.5)),
    "ribbons": ((-2, -2.8, 1.03, 1.7), (0, 0, 1.12, 1.7), (2, 3.6, 1.05, 1.7)),
}

# Artwork treatments chosen for the supplied reference and each unit's palette.
APPEARANCES = {
    "フィンファンネル": ("twin", ("#d6fb43", "#a3d722")),
    "サザビー": ("fan", ("#ff7128", "#ffc33d", "#ff4551")),
    "Hi-νガンダムHWS": ("twin", ("#bca8ff", "#e3d7ff")),
    "Hi-νガンダム": ("twin", ("#8c91ff", "#bd7fff")),
    "キュベレイ": ("needle", ("#62d4ff",)),
    "ヤクト・ドーガ": ("fan", ("#ffbe3a", "#ffe86a", "#f89f2c")),
    "ナイチンゲール": ("flare", ("#ff8d37",)),
    "クシャトリヤ": ("flare", ("#90e195",)),
    "ユニコーン": ("ribbons", ("#39edb8", "#b9ffd8", "#54e59b")),
    "ガンダム・エアリアル": ("twin", ("#6fe8ff", "#6398ff")),
    "ガンダム・キャリバーン": ("ribbons", ("#ff70bb", "#82edff", "#d4ff59")),
    "ガンダム・ファラクト": ("needle", ("#bb71f9",)),
    "ガンダム・ルブリス": ("flare", ("#ff77cc",)),
    "ストライクフリーダム": ("needle", ("#61a8ff",)),
    "レジェンドガンダム": ("twin", ("#7ddfff", "#50c8ea")),
    "カオスガンダム": ("flare", ("#ffaf57",)),
    "ガンダムサバーニャ": ("twin", ("#7bfa87", "#c1ffc3")),
    "Ξガンダム": ("needle", ("#ffca51",)),
    "Sガンダム": ("flare", ("#83e2ff",)),
    "ロングレンジ・フィン・ファンネル（RX-93ff）": ("ribbons", ("#6bd8ff", "#b6e8ff", "#ffc85c")),
    "νガンダムHWS": ("twin", ("#c9ef64", "#86d754")),
    "クィン・マンサ": ("fan", ("#7de9a2", "#c6ffd3", "#56cf98")),
    "キュベレイMk-II（プル機）": ("needle", ("#bd8bff",)),
    "キュベレイMk-II（プルツー機）": ("needle", ("#ff7199",)),
    "エルメス": ("flare", ("#69e9ce",)),
    "α・アジール": ("fan", ("#ffb24e", "#ffe5a1", "#ff783a")),
}
DEFAULT_APPEARANCE = ("needle", ("#72dfff",))


def load_sprite(path, fallback=None):
    for candidate in (path.with_suffix(".png"), path):
        try:
            with Image.open(candidate) as source:
                if max(source.size) > 4096:
                    continue
                sprite = source.convert("RGBA")
                sprite.thumbnail((32, 32), Image.Resampling.LANCZOS)
                if sprite.getbbox():
                    return sprite
        except (ValueError, OSError, Image.DecompressionBombError):
            continue
    sprite = Image.new("RGBA", (32, 32))
    ImageDraw.Draw(sprite).polygon([(2, 2), (20, 11), (24, 24), (11, 20)], fill="#97d5e9")
    return sprite


def anchors(sprite, path=None):
    alpha = sprite.getchannel("A")
    points = [
        (x, y) for y in range(sprite.height) for x in range(sprite.width) if alpha.getpixel((x, y)) >= 144
    ]
    front = min(points, key=lambda p: (sum(p), -alpha.getpixel(p), p[1]), default=(0, 0))
    back = max(points, key=lambda p: (sum(p), alpha.getpixel(p), -p[1]), default=(20, 20))
    if path and path.suffix.lower() == ".cur":
        try:
            with path.open("rb") as file:
                reserved, kind, count = struct.unpack("<HHH", file.read(6))
                if (reserved, kind) == (0, 2):
                    for _ in range(min(count, 256)):
                        w, h, _, _, x, y, _, _ = struct.unpack("<BBBBHHII", file.read(16))
                        if (w, h) == (32, 32) and x < w and y < h:
                            front = (x, y)
                            break
        except (OSError, struct.error):
            pass
    return front, back
