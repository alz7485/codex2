import ctypes
import time
from collections import deque
from ctypes import wintypes

from PIL import Image

from cursor_art import APPEARANCES, DEFAULT_APPEARANCE, OVERLAY_SIZE, load_sprite
from effect_engine import ClickTracker, EffectEngine

WINDOW_TITLE = "Funnel Cursor Effect"


class BitmapHeader(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("width", wintypes.LONG),
        ("height", wintypes.LONG),
        ("planes", wintypes.WORD),
        ("bits", wintypes.WORD),
        ("compression", wintypes.DWORD),
        ("image_size", wintypes.DWORD),
        ("x_pixels_per_meter", wintypes.LONG),
        ("y_pixels_per_meter", wintypes.LONG),
        ("colors_used", wintypes.DWORD),
        ("important_colors", wintypes.DWORD),
    ]


class BitmapInfo(ctypes.Structure):
    _fields_ = [("header", BitmapHeader), ("color", wintypes.DWORD)]


class BlendFunction(ctypes.Structure):
    _fields_ = [
        ("operation", wintypes.BYTE),
        ("flags", wintypes.BYTE),
        ("opacity", wintypes.BYTE),
        ("alpha_format", wintypes.BYTE),
    ]


def bind(library, name, result, *arguments):
    function = getattr(library, name)
    function.restype = result
    function.argtypes = arguments
    return function


class RawInputDevice(ctypes.Structure):
    _fields_ = [
        ("page", wintypes.WORD),
        ("usage", wintypes.WORD),
        ("flags", wintypes.DWORD),
        ("target", wintypes.HWND),
    ]


class RawInputHeader(ctypes.Structure):
    _fields_ = [
        ("kind", wintypes.DWORD),
        ("size", wintypes.DWORD),
        ("device", wintypes.HANDLE),
        ("param", wintypes.WPARAM),
    ]


class RawButtons(ctypes.Structure):
    _fields_ = [("flags", wintypes.WORD), ("data", wintypes.WORD)]


class RawMouse(ctypes.Structure):
    _fields_ = [
        ("flags", wintypes.WORD),
        ("padding", wintypes.WORD),
        ("buttons", RawButtons),
        ("raw_buttons", wintypes.DWORD),
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
        ("extra", wintypes.DWORD),
    ]


class MousePacket(ctypes.Structure):
    _fields_ = [("header", RawInputHeader), ("mouse", RawMouse)]


def enable_monitor_dpi():
    try:
        user = ctypes.WinDLL("user32", use_last_error=True)
        bind(user, "SetProcessDpiAwarenessContext", wintypes.BOOL, wintypes.HANDLE)(-4)
    except AttributeError:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)


class ClickObserver:
    """Receive mouse-button downs at the overlay. Always chain to the window procedure."""

    def __init__(self, user, overlay):
        self.queue = deque(maxlen=32)
        self.overlay = overlay
        self.error = False
        self.key_state = bind(user, "GetAsyncKeyState", ctypes.c_short, ctypes.c_int)
        self.register = bind(
            user,
            "RegisterRawInputDevices",
            wintypes.BOOL,
            ctypes.POINTER(RawInputDevice),
            wintypes.UINT,
            wintypes.UINT,
        )
        self.read = bind(
            user,
            "GetRawInputData",
            wintypes.UINT,
            wintypes.HANDLE,
            wintypes.UINT,
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.UINT),
            wintypes.UINT,
        )
        ptr = ctypes.c_void_p
        self.set_proc = bind(user, "SetWindowLongPtrW", ptr, wintypes.HWND, ctypes.c_int, ptr)
        self.call_proc = bind(
            user,
            "CallWindowProcW",
            ctypes.c_ssize_t,
            ptr,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )
        prototype = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )
        self.callback = prototype(self.message)
        self.previous = self.set_proc(overlay.window, -4, self.callback)
        if not self.previous:
            raise ctypes.WinError(ctypes.get_last_error())
        self.device = RawInputDevice(1, 2, 0x100, overlay.window)
        if not self.register(ctypes.byref(self.device), 1, ctypes.sizeof(self.device)):
            self.set_proc(overlay.window, -4, self.previous)
            raise ctypes.WinError(ctypes.get_last_error())

    def message(self, window, msg, wp, lp):
        try:
            if msg == 0xFF:  # WM_INPUT. No keyboard registration or legacy-input suppression.
                packet = MousePacket()
                size = wintypes.UINT(ctypes.sizeof(packet))
                read = self.read(
                    lp, 0x10000003, ctypes.byref(packet), ctypes.byref(size), ctypes.sizeof(RawInputHeader)
                )
                if read == ctypes.sizeof(packet) and packet.header.kind == 0:
                    flags = packet.mouse.buttons.flags
                    if flags & 0x15:
                        pos = self.overlay.cursor_position()
                        if pos is not None:
                            modifiers = sum(
                                bit
                                for vk, bit in ((0x10, 1), (0x11, 2), (0x12, 4))
                                if self.key_state(vk) & 0x8000
                            )
                            for mask, name in ((1, "left"), (4, "right"), (0x10, "middle")):
                                if flags & mask:
                                    self.queue.append((name, pos, time.monotonic(), modifiers))
            elif msg == 0x7E:  # WM_DISPLAYCHANGE
                self.overlay.monitor = None
        except (OSError, ValueError):
            self.error = True
        return self.call_proc(self.previous, window, msg, wp, lp)

    def close(self):
        remove = RawInputDevice(1, 2, 1, None)
        self.register(ctypes.byref(remove), 1, ctypes.sizeof(remove))
        self.set_proc(self.overlay.window, -4, self.previous)
        self.queue.clear()


class LayeredOverlay:
    # Layered and transparent makes the entire overlay click-through.
    EXTENDED_STYLE = 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000

    def __init__(self, observe=False):
        user = ctypes.WinDLL("user32", use_last_error=True)
        gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        module = bind(kernel, "GetModuleHandleW", wintypes.HINSTANCE, wintypes.LPCWSTR)(None)
        hwnd, hdc, handle = wintypes.HWND, wintypes.HDC, wintypes.HANDLE
        boolean, integer, word = wintypes.BOOL, ctypes.c_int, wintypes.DWORD
        pointer = ctypes.c_void_p
        self.get_cursor_pos = bind(user, "GetCursorPos", boolean, ctypes.POINTER(wintypes.POINT))
        self.monitor = self.observer = None
        self.dpi_checked = -1
        self.scale = 1
        self.monitor_at = bind(user, "MonitorFromPoint", handle, wintypes.POINT, word)
        shcore = ctypes.WinDLL("shcore")
        self.monitor_dpi = bind(
            shcore,
            "GetDpiForMonitor",
            wintypes.LONG,
            handle,
            integer,
            ctypes.POINTER(wintypes.UINT),
            ctypes.POINTER(wintypes.UINT),
        )
        self.tracker = ClickTracker(
            user.GetDoubleClickTime() / 1000, (user.GetSystemMetrics(36), user.GetSystemMetrics(37))
        )
        self.show_window = bind(user, "ShowWindow", boolean, hwnd, integer)
        self.destroy_window = bind(user, "DestroyWindow", boolean, hwnd)
        self.update = bind(
            user,
            "UpdateLayeredWindow",
            boolean,
            hwnd,
            hdc,
            ctypes.POINTER(wintypes.POINT),
            ctypes.POINTER(wintypes.SIZE),
            hdc,
            ctypes.POINTER(wintypes.POINT),
            word,
            ctypes.POINTER(BlendFunction),
            word,
        )
        create_window = bind(
            user,
            "CreateWindowExW",
            hwnd,
            word,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            word,
            integer,
            integer,
            integer,
            integer,
            hwnd,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            pointer,
        )
        set_pos = bind(user, "SetWindowPos", boolean, hwnd, hwnd, integer, integer, integer, integer, word)
        create_dc = bind(gdi, "CreateCompatibleDC", hdc, hdc)
        create_bitmap = bind(
            gdi,
            "CreateDIBSection",
            handle,
            hdc,
            ctypes.POINTER(BitmapInfo),
            wintypes.UINT,
            ctypes.POINTER(pointer),
            handle,
            word,
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
                self.EXTENDED_STYLE,
                "STATIC",
                WINDOW_TITLE,
                0x80000000,
                0,
                0,
                side,
                side,
                None,
                None,
                module,
                None,
            )
            if not self.window or not set_pos(self.window, -1, 0, 0, 0, 0, 0x0013):
                raise ctypes.WinError(ctypes.get_last_error())
            self.dc = create_dc(None)
            if not self.dc:
                raise ctypes.WinError(ctypes.get_last_error())
            self.create_bitmap = create_bitmap
            self.side = 0
            self.resize(1)
            if observe:
                self.observer = ClickObserver(user, self)
        except Exception:
            self.close()
            raise

    def resize(self, scale):
        side = round(OVERLAY_SIZE * scale)
        if side == self.side:
            return
        header = BitmapHeader(ctypes.sizeof(BitmapHeader), side, -side, 1, 32)
        bits = ctypes.c_void_p()
        bitmap = self.create_bitmap(
            self.dc, ctypes.byref(BitmapInfo(header, 0)), 0, ctypes.byref(bits), None, 0
        )
        if not bitmap:
            raise ctypes.WinError(ctypes.get_last_error())
        previous = self.select_object(self.dc, bitmap)
        if not previous or previous == ctypes.c_void_p(-1).value:
            self.delete_object(bitmap)
            raise ctypes.WinError(ctypes.get_last_error())
        if self.bitmap:
            self.delete_object(self.bitmap)
        else:
            self.before_bitmap = previous
        self.bitmap, self.bits, self.side, self.scale = bitmap, bits, side, scale

    def update_monitor(self, position):
        monitor = self.monitor_at(wintypes.POINT(*position), 2)
        now = time.monotonic()
        if monitor == self.monitor and now - self.dpi_checked < 1:
            return False
        changed = monitor != self.monitor
        previous_scale = self.scale
        self.dpi_checked = now
        x, y = wintypes.UINT(96), wintypes.UINT(96)
        if self.monitor_dpi(monitor, 0, ctypes.byref(x), ctypes.byref(y)) == 0:
            self.resize(max(1, min(5, x.value / 96)))
        self.monitor = monitor
        return changed or self.scale != previous_scale

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

        half = self.side // 2
        top_left = wintypes.POINT(position[0] - half, position[1] - half)
        size = wintypes.SIZE(self.side, self.side)
        if frame.width != self.side:
            frame = frame.resize((self.side, self.side), Image.Resampling.BILINEAR)
        origin = wintypes.POINT(0, 0)
        blend = BlendFunction(0, 0, 255, 1)
        pixels = frame.convert("RGBa").tobytes("raw", "BGRa")
        ctypes.memmove(self.bits, pixels, len(pixels))
        if not self.update(
            self.window,
            None,
            ctypes.byref(top_left),
            ctypes.byref(size),
            self.dc,
            ctypes.byref(origin),
            0,
            ctypes.byref(blend),
            2,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.visible:
            self.show_window(self.window, 8)
            self.visible = True

    def close(self):
        if self.observer:
            self.observer.close()
            self.observer = None
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
    def __init__(self, root, on_error):
        self.root = root
        self.on_error = on_error
        self.overlay = self.timer = self.animation = None

    def start(self, cursor, config):
        self.stop()
        if not any(fields["enabled"] for fields in config.values()):
            return
        self.animation = EffectEngine(
            load_sprite(cursor), APPEARANCES.get(cursor.stem, DEFAULT_APPEARANCE), config, cursor
        )
        if not self.animation.layers:
            self.animation = None
            return
        observe = any(config[k]["enabled"] for k in ("click", "followers", "deploy", "particles"))
        if self.animation.special:
            observe |= config[self.animation.special]["enabled"]
        try:
            self.overlay = LayeredOverlay(observe)
            self.tick()
        except Exception:
            self.stop()
            raise

    def tick(self):
        self.timer = None
        start = time.monotonic()
        overlay = self.overlay
        try:
            position = overlay.cursor_position()
            events = []
            if position is not None and overlay.update_monitor(position):
                self.animation.reset()
                overlay.tracker.previous = None
            if overlay.observer:
                if overlay.observer.error:
                    raise OSError("マウスの状態を読み取れませんでした。")
                queue = overlay.observer.queue
                while queue:
                    button, pos, stamp, modifiers = queue.popleft()
                    if position is not None and start - stamp < 0.35:
                        events.append(
                            overlay.tracker.press(
                                button, tuple(n / overlay.scale for n in pos), stamp, modifiers
                            )
                        )
            logical = tuple(n / overlay.scale for n in position) if position is not None else None
            frame = self.animation.step(logical, start, events)
            overlay.render(frame, position)
            cost = time.monotonic() - start
            if cost > 0.014:
                self.animation.budget = max(0.3, self.animation.budget - 0.08)
            else:
                self.animation.budget = min(1, self.animation.budget + 0.005)
            interval = 16 if frame is not None else 32
            if logical is None or self.animation.still > 0.6:
                interval = 42 if frame is not None else 55
            self.timer = self.root.after(max(4, interval - round(cost * 1000)), self.tick)
        except (OSError, ValueError, RuntimeError, MemoryError) as error:
            self.stop()
            self.on_error(error)

    def stop(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if self.overlay is not None:
            self.overlay.close()
            self.overlay = None
        self.animation = None
