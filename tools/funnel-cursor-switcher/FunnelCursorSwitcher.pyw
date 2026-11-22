from collections import Counter
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from ctypes import wintypes
from tkinter import messagebox, ttk

from funnel_effect import LAUNCH, OFF, THRUST, FunnelEffect


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


def atomic_write(path, data):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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


def show_window(root, entries, system_cursor):
    root.title(APP_NAME)
    root.resizable(False, False)
    page = ttk.Frame(root, padding=20)
    page.grid(sticky="nsew")
    page.columnconfigure(1, weight=1)

    style = ttk.Style(root)
    style.configure("Heading.TLabel", font=("Yu Gothic UI", 16, "bold"))
    ttk.Label(page, text="カーソルを選ぶ", style="Heading.TLabel").grid(row=0, columnspan=2, sticky="w", pady=(0, 16))

    restore_label = RESTORE
    while restore_label in entries:
        restore_label += "（設定）"
    category_labels = list(entries) + [restore_label]
    ttk.Label(page, text="1. 分類").grid(row=1, column=0, sticky="w", padx=(0, 18))
    category = ttk.Combobox(page, values=category_labels, state="readonly", width=39)
    category.grid(row=1, column=1, sticky="ew")

    ttk.Label(page, text="2. カーソル").grid(row=2, column=0, sticky="w", padx=(0, 18), pady=10)
    cursor = ttk.Combobox(page, state="readonly", width=39)
    cursor.grid(row=2, column=1, sticky="ew", pady=10)

    preview = ttk.Frame(page)
    preview.grid(row=3, columnspan=2, sticky="ew", pady=(0, 14))
    ttk.Label(preview, text="プレビュー").pack(side="left", padx=(0, 10))
    swatches = tk.Canvas(preview, width=88, height=40, highlightthickness=0, takefocus=False)
    swatches.pack(side="left")
    swatches.create_rectangle(0, 0, 40, 40, fill="#ffffff", outline="#c7cdd5")
    swatches.create_rectangle(48, 0, 88, 40, fill="#253141", outline="#253141")

    ttk.Label(page, text="移動エフェクト").grid(row=4, column=0, sticky="w", padx=(0, 18), pady=(0, 12))
    effect_mode = tk.StringVar(value=THRUST)
    effect_choice = ttk.Combobox(page, textvariable=effect_mode, values=(THRUST, LAUNCH, OFF), state="readonly", width=39)
    effect_choice.grid(row=4, column=1, sticky="ew", pady=(0, 12))

    status = tk.StringVar()
    ttk.Label(page, textvariable=status, wraplength=430).grid(row=5, columnspan=2, sticky="w", pady=(0, 12))
    applied_cursor = None

    def effect_error(error):
        effect_mode.set(OFF)
        status.set(f"エフェクトを停止しました。{error}")

    effect = FunnelEffect(root, CURSORS / "ファンネル" / "フィンファンネル.png", effect_error)

    def update_effect(_event=None):
        try:
            if applied_cursor is None or effect_mode.get() == OFF:
                effect.stop()
            else:
                effect.start(applied_cursor, effect_mode.get())
        except (OSError, ValueError) as error:
            effect.stop()
            effect_error(error)

    def close():
        effect.stop()
        root.destroy()

    def choices():
        selection = category.current()
        return list(entries.values())[selection] if 0 <= selection < len(entries) else [None]

    def selected():
        index = cursor.current()
        return choices()[index] if index >= 0 else None

    def render_preview(_event=None):
        swatches.delete("image")
        swatches.image = None
        path = selected()
        if path is not None:
            try:
                photo = tk.PhotoImage(master=root, file=str(path.with_suffix(".png")))
            except tk.TclError:
                pass
            else:
                factor = max(1, (max(photo.width(), photo.height()) + 31) // 32)
                swatches.image = photo.subsample(factor) if factor > 1 else photo
                for x in (20, 68):
                    swatches.create_image(x, 20, image=swatches.image, tags="image")
        apply_button.state(["!disabled"] if cursor.current() >= 0 else ["disabled"])

    def choose_category(_event=None):
        available = choices()
        if available == [None]:
            labels = ["変更前のカーソル"]
        else:
            name_counts = Counter(path.stem.casefold() for path in available)
            labels = [path.name if name_counts[path.stem.casefold()] > 1 else path.stem for path in available]
        cursor.configure(values=labels)
        cursor.set("")
        if len(labels) == 1:
            cursor.current(0)
        render_preview()

    def apply(_event=None):
        nonlocal applied_cursor
        if cursor.current() < 0:
            return
        target = selected()
        try:
            result = system_cursor.apply(target)
        except (OSError, ValueError) as error:
            messagebox.showerror(APP_NAME, str(error), parent=root)
            return
        applied_cursor = target
        status.set(result)
        update_effect()

    apply_button = ttk.Button(page, text="適用", command=apply)
    apply_button.grid(row=6, column=1, sticky="e")
    category.bind("<<ComboboxSelected>>", choose_category)
    cursor.bind("<<ComboboxSelected>>", render_preview)
    effect_choice.bind("<<ComboboxSelected>>", update_effect)
    root.protocol("WM_DELETE_WINDOW", close)
    root.bind("<Return>", apply)

    if entries:
        category.current(0)
        status.set("分類とカーソルを選んで「適用」。")
    else:
        category.current(0)
        status.set("「カーソル」フォルダに分類フォルダと .cur ファイルを追加してください。")
    choose_category()
    category.focus_set()


def main():
    if sys.platform != "win32":
        print("このツールはWindows用です。", file=sys.stderr)
        return 1

    root = tk.Tk()
    try:
        system_cursor = WindowsCursor()
        entries = discover_cursors(CURSORS)
    except (OSError, KeyError) as error:
        messagebox.showerror(APP_NAME, str(error), parent=root)
        root.destroy()
        return 1
    show_window(root, entries, system_cursor)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
