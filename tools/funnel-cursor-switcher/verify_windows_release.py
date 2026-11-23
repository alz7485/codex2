import ctypes
import os
import struct
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from effect_engine import ClickEvent
from effect_settings import SAMPLES, SPECIAL, resolve, special_group
from equipment_catalog import ACTIVE_EQUIPMENT, equipment_key, is_frozen
from funnel_effect import (
    APPEARANCES,
    EffectEngine,
    LayeredOverlay,
    bind,
    enable_monitor_dpi,
    load_sprite,
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
        alpha = data[offset + 43 : offset + 40 + 32 * 32 * 4 : 4]
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
    overlay = LayeredOverlay(observe=True)
    window = overlay.window
    try:
        assert get_style(window, -20) & overlay.EXTENDED_STYLE == overlay.EXTENDED_STYLE
        for name in ("フィンファンネル", "サザビー", "ユニコーン"):
            sprite = load_sprite(assets / f"{name}.cur", assets / "フィンファンネル.png")
            effect = EffectEngine(sprite, APPEARANCES[name], resolve("ファンネル", {}, {})[0])
            assert effect.step((185, 195), 0.0) is None
            frame = effect.step(position, 0.03)
            assert frame is not None and frame.getbbox()
            overlay.render(frame, position)
            assert is_visible(window)
            assert effect.step(position, 0.125) is not None
            assert effect.step(position, 0.45) is None
            overlay.render(None, position)
            assert not is_visible(window)
        for paths in SPECIAL.values():
            for key in sorted(paths):
                if is_frozen(key):
                    continue
                path = cursors / key
                group = special_group(key)
                config = resolve(path.parent.name, {}, {group: {"enabled": True}})[0]
                effect = EffectEngine(load_sprite(path), APPEARANCES[path.stem], config, path)
                assert effect.step(position, 0.0, [ClickEvent("left", position, 0.0)]) is None
                effect.step(position, 0.1, [ClickEvent("left", position, 0.1, 3)])
                frame = effect.step(position, 0.6)
                assert frame is not None and frame.getbbox()
                overlay.render(frame, position)
                assert is_visible(window)
        # Force a high-DPI DIB reallocation and draw across a negative desktop origin.
        config = resolve("ファンネル", SAMPLES["戦闘モード"], {})[0]
        effect = EffectEngine(sprite, APPEARANCES[name], config)
        overlay.resize(1.5)
        scale_frame = effect.step((-120, -40), 1, [ClickEvent("right", (-120, -40), 1)])
        overlay.render(scale_frame, (-180, -60))
        assert is_visible(window) and overlay.side == 384
        overlay.resize(1)
    finally:
        overlay.close()
    assert not is_window(window)
    print("Windows rendered the click-through effect and hid the overlay when movement ended.")


def verify_hit_test():
    import tkinter as tk

    from PIL import Image

    root = tk.Tk()
    root.geometry("180x130+80+80")
    root.update()
    try:
        point = (root.winfo_rootx() + 50, root.winfo_rooty() + 50)
        user = ctypes.WinDLL("user32")
        hit = bind(user, "WindowFromPoint", wintypes.HWND, wintypes.POINT)
        before = hit(wintypes.POINT(*point))
        assert before and (
            before == root.winfo_id()
            or bind(user, "IsChild", wintypes.BOOL, wintypes.HWND, wintypes.HWND)(root.winfo_id(), before)
            or bind(user, "IsChild", wintypes.BOOL, wintypes.HWND, wintypes.HWND)(before, root.winfo_id())
        )
        overlay = LayeredOverlay(observe=True)
        try:
            overlay.render(Image.new("RGBA", (256, 256), (255, 120, 30, 220)), point)
            root.update()
            assert hit(wintypes.POINT(*point)) == before
        finally:
            overlay.close()
    finally:
        root.destroy()


def verify_restore(system, cursor):
    # Opt-in on the disposable CI account. Restore the exact prior value even on failure.
    reg = system.registry
    with reg.OpenKey(
        reg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0, reg.KEY_READ | reg.KEY_SET_VALUE
    ) as key:
        previous = system.read_arrow(key)
        try:
            system.apply(cursor)
            assert system.is_installed_cursor(system.read_arrow(key))
            system.apply(None)
            assert system.read_arrow(key) == previous
        finally:
            if system.read_arrow(key) != previous:
                system.write_arrow(key, previous)
                system.reload()


def verify_animated(source, root, system, cursor):
    category = root / "自作"
    category.mkdir()

    def chunk(kind, payload):
        return kind + struct.pack("<I", len(payload)) + payload + bytes(len(payload) % 2)

    # The Windows ANI format wraps icon frames in RIFF ACON.
    data = cursor.read_bytes()
    width, height, colors, reserved, hx, hy, size, offset = struct.unpack_from("<BBBBHHII", data, 6)
    assert width == height == 32
    frame = (
        struct.pack("<HHHBBBBHHII", 0, 2, 1, width, height, colors, reserved, hx, hy, size, 22)
        + data[offset : offset + size]
    )
    header = struct.pack("<9I", 36, 2, 2, 0, 0, 0, 0, 6, 1)
    ani = category / "追加.ani"
    ani.write_bytes(
        chunk(b"RIFF", b"ACON" + chunk(b"anih", header) + chunk(b"LIST", b"fram" + chunk(b"icon", frame) * 2))
    )
    windows_sample = next((Path(os.environ["WINDIR"]) / "Cursors").glob("*.ani"), None)
    if windows_sample:
        ani.write_bytes(windows_sample.read_bytes())
    assert ani in source["discover_cursors"](root)["自作"]
    system.install_file(ani)


def main(archive, check_restore=False):
    enable_monitor_dpi()
    source = run_path(str(Path(__file__).with_name("FunnelCursorSwitcher.pyw")))
    with TemporaryDirectory(prefix="Cursor Switcher ") as folder:
        root = Path(folder)
        with ZipFile(archive) as package:
            package.extractall(root)
        bundle = root / "FunnelCursorSwitcher"
        assert (bundle / "_internal" / "_tk_data" / "tk.tcl").is_file()
        cursors = bundle / "カーソル"
        for stem in ("フィンファンネル", "サザビー", "クィン・マンサ", "ナイチンゲール", "キュベレイ", "キュベレイMk-II（プル機）", "キュベレイMk-II（プルツー機）"):
            verify_base_frame(cursors / "ファンネル" / f"{stem}.cur")
        verify_base_frame(cursors / "ドラグーン" / "ストライクフリーダム.cur")

        system = source["WindowsCursor"]()
        system.store = root / "Installed Cursors"
        system.store.mkdir()
        system.backup = system.store / "arrow-original.json"
        active = source["discover_cursors"](cursors)
        assert {equipment_key(p) for paths in active.values() for p in paths} == ACTIVE_EQUIPMENT
        # Check that frozen library artifacts still ship and remain loadable.
        entries = source["discover_cursors"](cursors, include_frozen=True)
        files = [cursor for category in entries.values() for cursor in category]
        assert len(files) >= 25
        assert APPEARANCES.keys() <= {cursor.stem for cursor in files}
        for cursor in files:
            system.install_file(cursor)
            sheet = bundle / "飛行アニメ" / cursor.parent.name / (cursor.stem + ".png")
            assert sheet.read_bytes() == (Path(__file__).parent / sheet.relative_to(bundle)).read_bytes()
        for name in ("フィンファンネル", "νガンダムHWS", "Hi-νガンダム"):
            sheet = bundle / "飛行アニメ" / "ファンネル" / (name + ".展開.png")
            assert sheet.read_bytes() == (Path(__file__).parent / sheet.relative_to(bundle)).read_bytes()
        shield = bundle / "飛行アニメ" / "ファンネル" / "ユニコーン.正面.png"
        assert shield.read_bytes() == (Path(__file__).parent / shield.relative_to(bundle)).read_bytes()
        verify_animated(source, root, system, files[0])
        if check_restore:
            verify_restore(system, files[0])
        verify_effect(cursors)
        verify_hit_test()
        verify_startup(bundle, source["APP_NAME"])
        print(f"Windows loaded {len(files)} cursors and opened the extracted onedir app.")


if __name__ == "__main__":
    main(Path(sys.argv[1]), "--check-system-restore" in sys.argv[2:])
