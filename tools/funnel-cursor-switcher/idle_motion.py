"""Projected idle rotation frames and temporary Windows animated arrows."""

import ctypes
import hashlib
import struct
from ctypes import wintypes
from functools import lru_cache
from pathlib import Path

from PIL import Image

from effect_settings import atomic_write


CELL = 96
STEPS = 48
MOTION = "横回転"


def idle_sheet(cursor):
    if cursor and cursor.parent.name == "ファンネル" and cursor.stem == "フィンファンネル":
        path = cursor.parent.parent.parent / "飛行アニメ" / cursor.parent.name / "フィンファンネル.待機回転.png"
        if path.is_file():
            return path
    return None


@lru_cache(maxsize=4)
def read_turntable(path):
    with Image.open(path) as image:
        if image.size != (CELL * STEPS, CELL):
            raise ValueError("待機回転の画像サイズを確認してください。")
        image = image.convert("RGBA")
    return tuple(image.crop((i * CELL, 0, (i + 1) * CELL, CELL)) for i in range(image.width // CELL))


@lru_cache(maxsize=384)
def turn_frame(path, step, size=32):
    poses = read_turntable(path)
    return poses[step % STEPS].resize((size, size), Image.Resampling.LANCZOS)


def cursor_bytes(image, hotspot):
    """Encode one 32-bit CUR image, with a fixed click hotspot."""
    width, height = image.size
    stride = ((width + 31) // 32) * 4
    mask = bytearray(stride * height)
    alpha = image.getchannel("A")
    for row in range(height):
        for x in range(width):
            if alpha.getpixel((x, height - row - 1)) == 0:
                mask[row * stride + x // 8] |= 128 >> (x % 8)
    dib = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32, 0,
                      width * height * 4, 0, 0, 0, 0)
    dib += image.tobytes("raw", "BGRA", 0, -1) + mask
    return (struct.pack("<HHH", 0, 2, 1)
            + struct.pack("<BBBBHHII", width, height, 0, 0, *hotspot, len(dib), 22) + dib)


def chunk(name, data):
    return name + struct.pack("<I", len(data)) + data + b"\0" * (len(data) % 2)


def animation_bytes(sheet, period, direction, hotspot):
    total_ticks = max(STEPS, round(period * 60))
    rates = [round((i + 1) * total_ticks / STEPS) - round(i * total_ticks / STEPS)
             for i in range(STEPS)]
    sign = -1 if direction == "逆回転" else 1
    frames = []
    for step in range(STEPS):
        image = turn_frame(sheet, sign * step, 32)
        frames.append(chunk(b"icon", cursor_bytes(image, hotspot)))
    header = struct.pack("<9I", 36, STEPS, STEPS, 32, 32, 32, 1,
                         max(1, round(total_ticks / STEPS)), 1)
    payload = b"ACON" + chunk(b"anih", header)
    payload += chunk(b"rate", struct.pack("<" + "I" * STEPS, *rates))
    payload += chunk(b"LIST", b"fram" + b"".join(frames))
    return chunk(b"RIFF", payload)


class WindowsArrow:
    """Change only the system normal-arrow image, without registry edits."""

    def __init__(self):
        user = ctypes.WinDLL("user32", use_last_error=True)
        self.load = user.LoadImageW
        self.load.argtypes = (wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT)
        self.load.restype = wintypes.HANDLE
        self.replace = user.SetSystemCursor
        self.replace.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self.replace.restype = wintypes.BOOL
        self.reload = user.SystemParametersInfoW
        self.reload.argtypes = (wintypes.UINT, wintypes.UINT, wintypes.LPVOID, wintypes.UINT)
        self.reload.restype = wintypes.BOOL
        self.destroy = user.DestroyCursor
        self.destroy.argtypes = (wintypes.HANDLE,)
        self.destroy.restype = wintypes.BOOL

    def install(self, path):
        # Unlike LoadCursorFromFile, this returns an owned, non-shared handle
        # that SetSystemCursor is allowed to consume (including ANI files).
        handle = self.load(None, str(path), 2, 0, 0, 0x0010 | 0x0040)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.replace(handle, 32512):  # OCR_NORMAL. Windows owns it on success.
            error = ctypes.get_last_error()
            self.destroy(handle)
            raise ctypes.WinError(error)

    def restore(self):
        # Read the currently applied registry setting: Apply/Restore may have
        # just selected another cursor before the previous idle effect stops.
        if not self.reload(0x0057, 0, None, 0):  # SPI_SETCURSORS
            raise ctypes.WinError(ctypes.get_last_error())


class NativeIdleCursor:
    def __init__(self, sheet, config, hotspot, folder, api=None):
        data = animation_bytes(sheet, config["turn_period"], config["turn_direction"], hotspot)
        self.path = Path(folder) / ("idle-" + hashlib.sha256(data).hexdigest() + ".ani")
        if not self.path.is_file():
            atomic_write(self.path, data)
        self.api = api if api is not None else WindowsArrow()
        self.active = False

    def update(self, active):
        if active and not self.active:
            self.api.install(self.path)
            self.active = True
        elif not active and self.active:
            self.api.restore()
            self.active = False

    def close(self):
        self.update(False)
