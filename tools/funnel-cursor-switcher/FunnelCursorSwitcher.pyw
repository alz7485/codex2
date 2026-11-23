import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import tkinter as tk
from ctypes import wintypes
from tkinter import messagebox

from effect_editor import Editor
from effect_settings import atomic_write
from funnel_effect import enable_monitor_dpi


APP_NAME = "ファンネル・カーソル切替"
ROOT = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
CURSORS = ROOT / "カーソル"
EXTENSIONS = {".cur", ".ani"}
RESTORE = "元に戻す"
REGISTRY_PATH = r"Control Panel\Cursors"


def discover_cursors(folder):
    if not folder.is_dir():
        return {}

    categories = {}
    for category in sorted(folder.iterdir(), key=lambda path: (path.name != "ファンネル", path.name.casefold())):
        if not category.is_dir():
            continue
        cursors = sorted(
            (path for path in category.iterdir() if path.is_file() and path.suffix.lower() in EXTENSIONS),
            key=lambda path: (path.stem != "フィンファンネル", path.stem.casefold(), path.suffix.lower()),
        )
        if cursors:
            categories[category.name] = cursors
    return categories


class WindowsCursor:
    def __init__(self):
        import msvcrt
        import winreg

        self.msvcrt = msvcrt
        self.registry = winreg
        self.store = Path(os.environ["LOCALAPPDATA"]) / "FunnelCursorSwitcher"
        self.backup = self.store / "arrow-original.json"
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.SystemParametersInfoW.argtypes = (wintypes.UINT, wintypes.UINT, wintypes.LPVOID, wintypes.UINT)
        self.user32.SystemParametersInfoW.restype = wintypes.BOOL
        self.user32.LoadImageW.argtypes = (
            wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT
        )
        self.user32.LoadImageW.restype = wintypes.HANDLE
        self.user32.DestroyCursor.argtypes = (wintypes.HANDLE,)
        self.user32.DestroyCursor.restype = wintypes.BOOL

    def read_arrow(self, key):
        try:
            value, kind = self.registry.QueryValueEx(key, "Arrow")
        except FileNotFoundError:
            return None
        if kind not in (self.registry.REG_SZ, self.registry.REG_EXPAND_SZ):
            raise ValueError("Windowsの「通常の選択」の設定形式を読み取れませんでした。")
        return value, kind

    def write_arrow(self, key, setting):
        if setting is None:
            try:
                self.registry.DeleteValue(key, "Arrow")
            except FileNotFoundError:
                pass
        else:
            value, kind = setting
            self.registry.SetValueEx(key, "Arrow", 0, kind, value)

    def reload(self):
        spi_setcursors = 0x0057
        if not self.user32.SystemParametersInfoW(spi_setcursors, 0, None, 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def is_installed_cursor(self, setting):
        if setting is None:
            return False
        candidate = Path(os.path.expandvars(setting[0]))
        return (
            candidate.is_absolute()
            and candidate.parent == self.store
            and candidate.name.startswith("cursor-")
            and candidate.suffix.lower() in EXTENSIONS
        )

    def install_file(self, source):
        data = source.read_bytes()
        name = f"cursor-{hashlib.sha256(data).hexdigest()}{source.suffix.lower()}"
        installed = self.store / name
        if not installed.is_file():
            atomic_write(installed, data)
        image_cursor, lr_loadfromfile = 2, 0x0010
        handle = self.user32.LoadImageW(None, str(installed), image_cursor, 0, 0, lr_loadfromfile)
        if not handle:
            raise ValueError(f"Windowsが「{source.name}」をカーソルとして読み込めませんでした。")
        self.user32.DestroyCursor(handle)
        return installed

    def restore_setting(self):
        try:
            setting = json.loads(self.backup.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ValueError("変更前のカーソル設定を読み取れませんでした。") from error
        if setting is None:
            return None
        if (
            isinstance(setting, list) and len(setting) == 2 and isinstance(setting[0], str)
            and setting[1] in (self.registry.REG_SZ, self.registry.REG_EXPAND_SZ)
        ):
            return tuple(setting)
        raise ValueError("変更前のカーソル設定を読み取れませんでした。")

    def apply(self, source):
        self.store.mkdir(parents=True, exist_ok=True)
        with (self.store / "settings.lock").open("a+b") as lock:
            lock.seek(0)
            try:
                self.msvcrt.locking(lock.fileno(), self.msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise OSError("別のウィンドウでカーソルを変更中です。少し待って再試行してください。") from error

            access = self.registry.KEY_QUERY_VALUE | self.registry.KEY_SET_VALUE
            with self.registry.OpenKey(self.registry.HKEY_CURRENT_USER, REGISTRY_PATH, 0, access) as key:
                previous = self.read_arrow(key)
                installed_by_tool = self.is_installed_cursor(previous)
                if source is None:
                    if not installed_by_tool:
                        return "現在はWindowsで選択したカーソルを使用中です。"
                    target = self.restore_setting()
                    status = "変更前のカーソルに戻しました。"
                else:
                    installed = self.install_file(source)
                    if installed_by_tool:
                        self.restore_setting()
                    else:
                        backup_data = json.dumps(previous, ensure_ascii=False).encode("utf-8")
                        atomic_write(self.backup, backup_data)
                    target = str(installed), self.registry.REG_SZ
                    status = f"「{source.stem}」を適用しました。"

                if target != previous:
                    self.write_arrow(key, target)
                    try:
                        self.reload()
                    except OSError as error:
                        try:
                            self.write_arrow(key, previous)
                            self.reload()
                        except OSError as rollback_error:
                            raise OSError(f"カーソルの再読み込みに失敗しました。復元エラー: {rollback_error}") from error
                        raise
                return status


def main():
    if sys.platform != "win32":
        print("このツールはWindows用です。", file=sys.stderr)
        return 1

    enable_monitor_dpi()
    root = tk.Tk()
    try:
        system_cursor = WindowsCursor()
        entries = discover_cursors(CURSORS)
    except (OSError, KeyError) as error:
        messagebox.showerror(APP_NAME, str(error), parent=root)
        root.destroy()
        return 1
    Editor(root, entries, system_cursor, APP_NAME)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
