import ctypes
import logging
import time
from collections import deque
from ctypes import wintypes
from pathlib import Path
from tempfile import gettempdir

from PIL import Image

from cursor_art import APPEARANCES, DEFAULT_APPEARANCE, OVERLAY_SIZE, load_sprite
import trial_runtime
from effect_settings import atomic_write
from effect_engine import ClickEvent, ClickTracker, EffectEngine
from idle_motion import MOTION, NativeIdleCursor, WindowsArrow, cursor_bytes

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
                    if flags & 0x17:
                        pos = self.overlay.cursor_position()
                        if pos is not None:
                            modifiers = sum(
                                bit
                                for vk, bit in ((0x10, 1), (0x11, 2), (0x12, 4))
                                if self.key_state(vk) & 0x8000
                            )
                            for mask, name in ((1, "left"), (2, "left_up"), (4, "right"), (0x10, "middle")):
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
        class MonitorInfo(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("rect", wintypes.RECT),
                        ("work", wintypes.RECT), ("flags", wintypes.DWORD)]
        self.monitor_info = MonitorInfo()
        self.monitor_info.size = ctypes.sizeof(MonitorInfo)
        self.get_monitor_info = bind(user, "GetMonitorInfoW", wintypes.BOOL, handle, ctypes.POINTER(MonitorInfo))
        class CursorInfo(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("flags", wintypes.DWORD),
                        ("cursor", handle), ("point", wintypes.POINT)]
        self.cursor_info = CursorInfo()
        self.cursor_info.size = ctypes.sizeof(CursorInfo)
        self.read_cursor_info = bind(user, "GetCursorInfo", boolean, ctypes.POINTER(CursorInfo))
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

    def resize(self, scale, dimensions=None):
        side, height = dimensions or (round(OVERLAY_SIZE * scale),) * 2
        if (side, height) == (self.side, getattr(self, "height", 0)):
            return
        header = BitmapHeader(ctypes.sizeof(BitmapHeader), side, -height, 1, 32)
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
        self.bitmap, self.bits, self.side, self.height, self.scale = bitmap, bits, side, height, scale

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
            scale = max(1, min(5, x.value / 96))
            if changed or scale != previous_scale:
                self.resize(scale)
        if not self.get_monitor_info(monitor, ctypes.byref(self.monitor_info)):
            raise ctypes.WinError(ctypes.get_last_error())
        rect = self.monitor_info.rect
        self.viewport = (rect.left, rect.top, rect.right, rect.bottom)
        self.monitor = monitor
        return changed or self.scale != previous_scale

    def cursor_position(self):
        point = wintypes.POINT()
        if self.get_cursor_pos(ctypes.byref(point)):
            return point.x, point.y
        return None

    def render(self, frame, position, origin=None):
        if frame is None:
            if self.visible:
                self.show_window(self.window, 0)
                self.visible = False
            return

        if origin is not None:
            self.resize(self.scale, frame.size)
        half = self.side // 2
        top_left = wintypes.POINT(*(origin or (position[0] - half, position[1] - half)))
        size = wintypes.SIZE(self.side, self.height)
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
    def __init__(self, root, on_error, cache_dir=None):
        from cursor_guard import start
        start()
        self.root = root
        self.on_error = on_error
        self.overlay = self.timer = self.animation = None
        self.cursor_motion = self.trial_arrow = None
        self.arrow_hidden = False
        self.cache_dir = cache_dir or Path(gettempdir()) / "FunnelCursorSwitcher-idle"

    def start(self, cursor, config):
        self.stop()
        if trial_runtime.enabled(cursor, config):
            try:
                self.animation = trial_runtime.create_display(cursor,config)
                logging.getLogger("funnel.display").info("Desktop effect %s", cursor.stem)
                self.overlay = LayeredOverlay(True)
                self.trial_arrow = WindowsArrow()
                self.blank_path = self.cache_dir / f"trial58-transparent-{self.animation.hot[0]}-{self.animation.hot[1]}.cur"
                if not self.blank_path.is_file():
                    atomic_write(self.blank_path,cursor_bytes(Image.new("RGBA",(32,32)), self.animation.hot))
                self.tick()
            except Exception:
                self.stop()
                raise
            return
        if not any(fields["enabled"] for fields in config.values()):
            return
        self.animation = EffectEngine(
            load_sprite(cursor), APPEARANCES.get(cursor.stem, DEFAULT_APPEARANCE), config, cursor
        )
        if not self.animation.layers:
            if self.animation and hasattr(self.animation, "close"):
                self.animation.close()
            self.animation = None
            return
        observe = any(config[k]["enabled"] for k in ("click", "followers", "deploy", "particles"))
        if self.animation.special:
            observe |= config[self.animation.special]["enabled"]
        try:
            idle = config["idle"]
            if self.animation.idle_sheet and idle["enabled"] and idle["motion"] == MOTION:
                self.cursor_motion = NativeIdleCursor(self.animation.idle_sheet, idle,
                                                       self.animation.hot, self.cache_dir)
                observe = True
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
            trial = self.trial_arrow is not None
            if trial and overlay.read_cursor_info(ctypes.byref(overlay.cursor_info)) and overlay.cursor_info.flags & 2:
                position = None
            events = []
            if position is not None and overlay.update_monitor(position):
                self.animation.reset()
                overlay.tracker.previous = None
                if trial and overlay.observer:
                    overlay.observer.queue.clear()
            if overlay.observer:
                if overlay.observer.error:
                    raise OSError("マウスの状態を読み取れませんでした。")
                queue = overlay.observer.queue
                if trial and len(queue) == queue.maxlen:
                    self.animation.cancel_fire()
                    queue.clear()
                while queue:
                    button, pos, stamp, modifiers = queue.popleft()
                    if trial and start - stamp >= 0.35:
                        self.animation.cancel_fire()
                        continue
                    if position is not None and start - stamp < 0.35:
                        if trial:
                            events.append(ClickEvent(button,pos,stamp,modifiers))
                        elif button != "left_up":
                            events.append(overlay.tracker.press(button,tuple(n / overlay.scale for n in pos),stamp,modifiers))
            if trial:
                frame = self.animation.step(position,start,events,getattr(overlay,"viewport",None),overlay.scale)
                overlay.render(frame,position,self.animation.frame_origin)
                if frame is not None and not self.arrow_hidden:
                    self.trial_arrow.install(self.blank_path)
                    self.arrow_hidden = True
                    logging.getLogger("funnel.display").info("Desktop frame displayed")
                elif frame is None and self.arrow_hidden:
                    self.trial_arrow.restore()
                    self.arrow_hidden = False
                self.timer = self.root.after(max(4, 16-round((time.monotonic()-start)*1000)),self.tick)
                return
            logical = tuple(n / overlay.scale for n in position) if position is not None else None
            frame = self.animation.step(logical, start, events)
            if self.cursor_motion:
                self.cursor_motion.update(self.animation.idle_turn_step is not None)
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
        except Exception as error:
            self.stop()
            self.on_error(error)

    def stop(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        try:
            if self.arrow_hidden:
                self.trial_arrow.restore()
                self.arrow_hidden = False
            self.trial_arrow = None
            if self.cursor_motion is not None:
                self.cursor_motion.close()
                self.cursor_motion = None
        finally:
            if self.overlay is not None:
                self.overlay.close()
                self.overlay = None
            if self.animation and hasattr(self.animation, "close"):
                self.animation.close()
            self.animation = None
