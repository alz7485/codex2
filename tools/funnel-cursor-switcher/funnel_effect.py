from collections import deque
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import math
from pathlib import Path
import time

from PIL import Image, ImageColor, ImageDraw, ImageFilter


OVERLAY_SIZE = 256
THRUST = "噴射光と軌跡"
LAUNCH = "ファンネル射出"
OFF = "オフ"
WINDOW_TITLE = "Funnel Cursor Effect"

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
}
DEFAULT_APPEARANCE = ("needle", ("#72dfff",))


@dataclass(frozen=True)
class Flight:
    x: float
    y: float
    vx: float
    vy: float
    born: float
    image: Image.Image


def load_sprite(path, fallback):
    try:
        with Image.open(path.with_suffix(".png")) as source:
            if max(source.size) <= 4096:
                sprite = source.convert("RGBA")
                sprite.thumbnail((32, 32), Image.Resampling.LANCZOS)
                if sprite.getbbox():
                    return sprite
    except OSError:
        pass
    with Image.open(fallback) as source:
        return source.convert("RGBA")


def sprite_axis(sprite):
    alpha = sprite.getchannel("A")
    points = [(x, y) for y in range(sprite.height) for x in range(sprite.width) if alpha.getpixel((x, y)) >= 144]
    if not points:
        return 20, 20
    front = min(points, key=lambda p: (sum(p), -alpha.getpixel(p), p[1]))
    back = max(points, key=lambda p: (sum(p), alpha.getpixel(p), -p[1]))
    delta = back[0] - front[0], back[1] - front[1]
    return delta if delta != (0, 0) else (20, 20)


class MotionAnimation:
    def __init__(self, mode, sprite, appearance):
        nozzle, colors = appearance
        self.mode = mode
        self.nozzles = NOZZLES[nozzle]
        self.colors = [ImageColor.getrgb(color) for color in colors]
        self.rear_x, self.rear_y = sprite_axis(sprite)
        axis_length = math.hypot(self.rear_x, self.rear_y)
        self.axis = self.rear_x / axis_length, self.rear_y / axis_length
        self.miniature = sprite.crop(sprite.getbbox())
        self.miniature.thumbnail((17, 17), Image.Resampling.LANCZOS)
        self.previous = None
        self.last_motion = -math.inf
        self.last_launch = -math.inf
        self.distance = 0.0
        self.trace = deque()
        self.flights = []
        self.plume_length = 13.0

    def step(self, position, now):
        previous, self.previous = self.previous, position
        if position is None:
            self.trace.clear()
            self.flights.clear()
            self.last_motion = -math.inf
            self.distance = 0.0
            return None

        if previous is not None and previous != position:
            dx, dy = position[0] - previous[0], position[1] - previous[1]
            distance = math.hypot(dx, dy)
            self.last_motion = now
            if self.mode == THRUST:
                self.plume_length = 11 + min(12, distance * 0.55)
                ax, ay = self.axis
                self.trace.append((
                    now,
                    position[0] + self.rear_x + ax * self.plume_length * 0.95,
                    position[1] + self.rear_y + ay * self.plume_length * 0.95,
                ))
            else:
                self.distance += distance
                if self.distance >= 8 and now - self.last_launch >= 0.065:
                    self.launch(position, (dx / distance, dy / distance), now)
                    self.last_launch = now
                    self.distance = 0.0

        if self.mode == THRUST:
            return self.draw_thrust(position, now)
        return self.draw_flights(position, now)

    def draw_thrust(self, position, now):
        lifetime = 0.18
        while self.trace and now - self.trace[0][0] >= lifetime:
            self.trace.popleft()
        flame = max(0.0, 1 - (now - self.last_motion) / 0.075)
        if not self.trace and flame == 0:
            return None

        frame = Image.new("RGBA", (OVERLAY_SIZE, OVERLAY_SIZE))
        draw = ImageDraw.Draw(frame)
        half = OVERLAY_SIZE // 2
        ax, ay = self.axis
        trace = []
        for born, x, y in self.trace:
            drift = 48 * (now - born)
            trace.append((born, x - position[0] + half + ax * drift, y - position[1] + half + ay * drift))
        for before, after in zip(trace, trace[1:]):
            age = (now - after[0]) / lifetime
            if math.dist(before[1:], after[1:]) <= 64:
                draw.line((*before[1:], *after[1:]), fill=(*self.colors[0], round(100 * (1 - age))), width=2)
        for born, x, y in trace:
            opacity = round(110 * (1 - (now - born) / lifetime))
            draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=(*self.colors[0], opacity))

        if flame:
            nx, ny = -ay, ax
            x0, y0 = half + self.rear_x, half + self.rear_y
            for i, (base, tip, length, width) in enumerate(self.nozzles):
                x, y = x0 + nx * base, y0 + ny * base
                reach = self.plume_length * length * (0.65 + 0.35 * flame)
                tx, ty = x0 + ax * reach + nx * tip, y0 + ay * reach + ny * tip
                color = self.colors[i % len(self.colors)]
                draw.polygon(
                    ((x - nx * width, y - ny * width), (tx, ty), (x + nx * width, y + ny * width)),
                    fill=(*color, round(216 * flame)),
                )
                draw.line(
                    (x, y, x + (tx - x) * 0.62, y + (ty - y) * 0.62),
                    fill=(250, 255, 235, round(225 * flame)),
                    width=1,
                )
        if not frame.getbbox():
            return None
        glow = Image.new("RGBA", frame.size, self.colors[0])
        glow.putalpha(frame.getchannel("A").filter(ImageFilter.GaussianBlur(1.5)).point(lambda a: a // 2))
        return Image.alpha_composite(glow, frame)

    def launch(self, position, direction, now):
        dx, dy = direction
        for side in (-1, 1):
            vx, vy = -52 * dx - side * 120 * dy, -52 * dy + side * 120 * dx
            heading = math.degrees(math.atan2(-vy, vx))
            image = self.miniature.rotate(heading - 135, resample=Image.Resampling.BICUBIC, expand=True)
            self.flights.append(Flight(
                position[0] + self.rear_x * 0.43, position[1] + self.rear_y * 0.43,
                vx, vy, now, image,
            ))

    def draw_flights(self, position, now):
        lifetime = 0.32
        self.flights = [flight for flight in self.flights if now - flight.born < lifetime]
        if not self.flights:
            return None

        frame = Image.new("RGBA", (OVERLAY_SIZE, OVERLAY_SIZE))
        draw = ImageDraw.Draw(frame)
        half = OVERLAY_SIZE // 2
        visible = []
        for flight in self.flights:
            elapsed = now - flight.born
            x = flight.x + flight.vx * elapsed - position[0] + half
            y = flight.y + flight.vy * elapsed - position[1] + half
            if not (-24 <= x <= OVERLAY_SIZE + 24 and -24 <= y <= OVERLAY_SIZE + 24):
                continue
            opacity = 1 - elapsed / lifetime
            draw.line(
                (x, y, x - flight.vx * 0.10, y - flight.vy * 0.10),
                fill=(*self.colors[0], round(155 * opacity)), width=2,
            )
            visible.append((flight, x, y, opacity))
        for flight, x, y, opacity in visible:
            sprite = flight.image.copy()
            sprite.putalpha(sprite.getchannel("A").point(lambda value: round(value * opacity)))
            frame.alpha_composite(sprite, (round(x - sprite.width / 2), round(y - sprite.height / 2)))
        return frame if frame.getbbox() else None


class BitmapHeader(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD), ("width", wintypes.LONG), ("height", wintypes.LONG),
        ("planes", wintypes.WORD), ("bits", wintypes.WORD), ("compression", wintypes.DWORD),
        ("image_size", wintypes.DWORD), ("x_pixels_per_meter", wintypes.LONG),
        ("y_pixels_per_meter", wintypes.LONG), ("colors_used", wintypes.DWORD),
        ("important_colors", wintypes.DWORD),
    ]


class BitmapInfo(ctypes.Structure):
    _fields_ = [("header", BitmapHeader), ("color", wintypes.DWORD)]


class BlendFunction(ctypes.Structure):
    _fields_ = [
        ("operation", wintypes.BYTE), ("flags", wintypes.BYTE),
        ("opacity", wintypes.BYTE), ("alpha_format", wintypes.BYTE),
    ]


def bind(library, name, result, *arguments):
    function = getattr(library, name)
    function.restype = result
    function.argtypes = arguments
    return function


class LayeredOverlay:
    # Layered and transparent makes the entire overlay click-through.
    EXTENDED_STYLE = 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000

    def __init__(self):
        user = ctypes.WinDLL("user32", use_last_error=True)
        gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        module = bind(kernel, "GetModuleHandleW", wintypes.HINSTANCE, wintypes.LPCWSTR)(None)
        hwnd, hdc, handle = wintypes.HWND, wintypes.HDC, wintypes.HANDLE
        boolean, integer, word = wintypes.BOOL, ctypes.c_int, wintypes.DWORD
        pointer = ctypes.c_void_p
        self.get_cursor_pos = bind(user, "GetCursorPos", boolean, ctypes.POINTER(wintypes.POINT))
        self.show_window = bind(user, "ShowWindow", boolean, hwnd, integer)
        self.destroy_window = bind(user, "DestroyWindow", boolean, hwnd)
        self.update = bind(
            user, "UpdateLayeredWindow", boolean, hwnd, hdc, ctypes.POINTER(wintypes.POINT),
            ctypes.POINTER(wintypes.SIZE), hdc, ctypes.POINTER(wintypes.POINT), word,
            ctypes.POINTER(BlendFunction), word,
        )
        create_window = bind(
            user, "CreateWindowExW", hwnd, word, wintypes.LPCWSTR, wintypes.LPCWSTR, word,
            integer, integer, integer, integer, hwnd, wintypes.HMENU, wintypes.HINSTANCE, pointer,
        )
        set_pos = bind(user, "SetWindowPos", boolean, hwnd, hwnd, integer, integer, integer, integer, word)
        create_dc = bind(gdi, "CreateCompatibleDC", hdc, hdc)
        create_bitmap = bind(
            gdi, "CreateDIBSection", handle, hdc, ctypes.POINTER(BitmapInfo), wintypes.UINT,
            ctypes.POINTER(pointer), handle, word,
        )
        self.select_object = bind(gdi, "SelectObject", handle, hdc, handle)
        self.delete_object = bind(gdi, "DeleteObject", boolean, handle)
        self.delete_dc = bind(gdi, "DeleteDC", boolean, hdc)
        self.window = self.dc = self.bitmap = self.before_bitmap = None
        self.bits = pointer()
        self.visible = False

        try:
            side = OVERLAY_SIZE
            self.window = create_window(
                self.EXTENDED_STYLE, "STATIC", WINDOW_TITLE, 0x80000000,
                0, 0, side, side, None, None, module, None,
            )
            if not self.window or not set_pos(self.window, -1, 0, 0, 0, 0, 0x0013):
                raise ctypes.WinError(ctypes.get_last_error())
            self.dc = create_dc(None)
            if not self.dc:
                raise ctypes.WinError(ctypes.get_last_error())
            header = BitmapHeader(ctypes.sizeof(BitmapHeader), side, -side, 1, 32)
            self.bitmap = create_bitmap(self.dc, ctypes.byref(BitmapInfo(header, 0)), 0, ctypes.byref(self.bits), None, 0)
            if not self.bitmap or not self.bits:
                raise ctypes.WinError(ctypes.get_last_error())
            result = self.select_object(self.dc, self.bitmap)
            if not result or result == pointer(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            self.before_bitmap = result
        except OSError:
            self.close()
            raise

    def cursor_position(self):
        point = wintypes.POINT()
        if self.get_cursor_pos(ctypes.byref(point)):
            return point.x, point.y
        return None

    def render(self, frame, position):
        if frame is None:
            if self.visible:
                self.show_window(self.window, 0)
                self.visible = False
            return

        half = OVERLAY_SIZE // 2
        top_left = wintypes.POINT(position[0] - half, position[1] - half)
        size = wintypes.SIZE(OVERLAY_SIZE, OVERLAY_SIZE)
        origin = wintypes.POINT(0, 0)
        blend = BlendFunction(0, 0, 255, 1)
        pixels = frame.convert("RGBa").tobytes("raw", "BGRa")
        ctypes.memmove(self.bits, pixels, len(pixels))
        if not self.update(
            self.window, None, ctypes.byref(top_left), ctypes.byref(size), self.dc,
            ctypes.byref(origin), 0, ctypes.byref(blend), 2,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.visible:
            self.show_window(self.window, 8)
            self.visible = True

    def close(self):
        if self.window:
            self.destroy_window(self.window)
            self.window = None
        if self.before_bitmap:
            self.select_object(self.dc, self.before_bitmap)
            self.before_bitmap = None
        if self.bitmap:
            self.delete_object(self.bitmap)
            self.bitmap = None
        if self.dc:
            self.delete_dc(self.dc)
            self.dc = None


class FunnelEffect:
    def __init__(self, root, fallback, on_error):
        self.root = root
        self.fallback = Path(fallback)
        self.on_error = on_error
        self.overlay = None
        self.timer = None
        self.animation = None

    def start(self, cursor, mode):
        self.stop()
        sprite = load_sprite(cursor, self.fallback)
        appearance = APPEARANCES.get(cursor.stem, DEFAULT_APPEARANCE)
        self.animation = MotionAnimation(mode, sprite, appearance)
        self.overlay = LayeredOverlay()
        self.tick()

    def tick(self):
        self.timer = None
        try:
            position = self.overlay.cursor_position()
            frame = self.animation.step(position, time.monotonic())
            self.overlay.render(frame, position)
        except OSError as error:
            self.stop()
            self.on_error(error)
            return
        self.timer = self.root.after(16 if frame is not None else 28, self.tick)

    def stop(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if self.overlay is not None:
            self.overlay.close()
            self.overlay = None
        self.animation = None
