import ctypes
from ctypes import wintypes
from pathlib import Path
from runpy import run_path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from zipfile import ZipFile

from funnel_effect import (
    APPEARANCES, LAUNCH, THRUST, LayeredOverlay, MotionAnimation, bind, load_sprite,
)


def verify_base_frame(cursor):
    data = cursor.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 2)
    for entry in range(count):
        width, height, _, _, hot_x, hot_y, length, offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + entry * 16
        )
        if (width, height) != (32, 32):
            continue
        header = struct.unpack_from("<IiiHHIIiiII", data, offset)
        assert header[:6] == (40, 32, 64, 1, 32, 0)
        alpha = data[offset + 43:offset + 40 + 32 * 32 * 4:4]
        assert length == 40 + 32 * 32 * 4 + 32 * 4
        points = [(index % 32, index // 32) for index, value in enumerate(alpha) if value >= 64]
        x, y = zip(*points)
        assert max(max(x) - min(x), max(y) - min(y)) + 1 >= 30
        preview = cursor.with_suffix(".png").read_bytes()
        assert struct.unpack_from(">II", preview, 16) == (32, 32)
        assert alpha[(31 - hot_y) * 32 + hot_x] >= 144
        return
    raise AssertionError(f"Missing 32-pixel frame in {cursor.name}")


def verify_startup(bundle, window_title):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    user32.FindWindowW.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, wintypes.LPDWORD)
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    with subprocess.Popen([str(bundle / "FunnelCursorSwitcher.exe")], cwd=bundle.parent) as app:
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline and app.poll() is None:
                window = user32.FindWindowW(None, window_title)
                if window:
                    owner = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(window, ctypes.byref(owner))
                    if owner.value == app.pid:
                        return
                time.sleep(0.25)
            raise RuntimeError("The extracted onedir app did not open its main window.")
        finally:
            if app.poll() is None:
                app.terminate()
                app.wait(timeout=5)


def verify_effect(cursors):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    is_visible = bind(user32, "IsWindowVisible", wintypes.BOOL, wintypes.HWND)
    is_window = bind(user32, "IsWindow", wintypes.BOOL, wintypes.HWND)
    get_style = bind(user32, "GetWindowLongW", wintypes.LONG, wintypes.HWND, ctypes.c_int)
    position = (200, 200)

    assets = cursors / "ファンネル"
    overlay = LayeredOverlay()
    window = overlay.window
    try:
        assert get_style(window, -20) & overlay.EXTENDED_STYLE == overlay.EXTENDED_STYLE
        for name, mode in (("フィンファンネル", THRUST), ("サザビー", THRUST), ("フィンファンネル", LAUNCH)):
            sprite = load_sprite(assets / f"{name}.cur", assets / "フィンファンネル.png")
            effect = MotionAnimation(mode, sprite, APPEARANCES[name])
            assert effect.step((185, 195), 0.0) is None
            frame = effect.step(position, 0.03)
            assert frame is not None and frame.getbbox()
            overlay.render(frame, position)
            assert is_visible(window)
            assert effect.step(position, 0.125) is not None
            assert effect.step(position, 0.45) is None
            overlay.render(None, position)
            assert not is_visible(window)
    finally:
        overlay.close()
    assert not is_window(window)
    print("Windows rendered both click-through effects and hid the overlay when movement ended.")


def main(archive):
    source = run_path(str(Path(__file__).with_name("FunnelCursorSwitcher.pyw")))
    with TemporaryDirectory(prefix="Cursor Switcher ") as folder:
        root = Path(folder)
        with ZipFile(archive) as package:
            package.extractall(root)
        bundle = root / "FunnelCursorSwitcher"
        assert (bundle / "_internal" / "_tk_data" / "tk.tcl").is_file()
        cursors = bundle / "カーソル"
        for stem in ("フィンファンネル", "サザビー"):
            verify_base_frame(cursors / "ファンネル" / f"{stem}.cur")

        system = source["WindowsCursor"]()
        system.store = root / "Installed Cursors"
        system.store.mkdir()
        entries = source["discover_cursors"](cursors)
        files = [cursor for category in entries.values() for cursor in category]
        assert len(files) >= 16
        for cursor in files:
            system.install_file(cursor)
        verify_effect(cursors)
        verify_startup(bundle, source["APP_NAME"])
        print(f"Windows loaded {len(files)} cursors and opened the extracted onedir app.")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
