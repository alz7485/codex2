"""Tk editor. Drafts belong to cursor IDs and never drive the desktop until Apply."""

import math
import logging
import time
import tkinter as tk
from collections import Counter
from copy import deepcopy
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from PIL import ImageTk

from cursor_art import APPEARANCES, DEFAULT_APPEARANCE, load_sprite
from effect_engine import ClickEvent, ClickTracker, EffectEngine
from effect_settings import (
    BUTTONS,
    MODIFIERS,
    SPECIAL,
    FIELDS,
    NAMES,
    SAMPLES,
    STANDARD,
    Settings,
    atomic_write,
    default_binding,
    difference,
    encode,
    read_preset,
    resolve,
    special_group,
    valid_name,
)
from funnel_effect import FunnelEffect
from equipment_catalog import is_frozen
import trial_runtime
from idle_motion import idle_sheet


class Preview:
    def __init__(self, parent):
        self.canvas = tk.Canvas(parent, width=245, height=175, bg="#182330", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.fx = self.canvas.create_image(0, 0)
        self.pointer = self.canvas.create_image(0, 0, anchor="nw")
        controls = ttk.Frame(parent)
        controls.pack(fill="x", pady=4)
        self.mode = tk.StringVar(value="自動")
        for name in ("自動", "移動", "停止"):
            ttk.Radiobutton(
                controls, text=name, variable=self.mode, value=name, command=self.restart_demo
            ).pack(side="left")
        self.test_button = ttk.Button(controls, text="特殊演出を試す", command=self.try_special)
        self.canvas.bind("<Motion>", self.motion)
        self.canvas.bind("<Leave>", lambda _: setattr(self, "manual", None))
        self.canvas.bind("<ButtonPress-1>", lambda event: self.press(event, "left"))
        self.canvas.bind("<ButtonPress-2>", lambda event: self.press(event, "middle"))
        self.canvas.bind("<ButtonPress-3>", lambda event: self.press(event, "right"))
        self.canvas.bind("<ButtonRelease-1>", lambda event: self.press(event, "left_up") if isinstance(self.engine,trial_runtime.TrialDisplay) else None)
        self.tracker = ClickTracker()
        self.timer = self.engine = self.manual = None
        self.events = []
        self.restart_demo()
        self.tick()

    def restart_demo(self):
        self.start = time.monotonic()
        self.mark = (0, -1)

    def motion(self, event):
        self.manual = event.x, event.y

    def press(self, event, button):
        self.motion(event)
        state = event.state
        modifiers = int(bool(state & 1)) | (2 if state & 4 else 0) | (4 if state & (0x8 | 0x20000) else 0)
        self.events = (self.events + [self.tracker.press(button, self.manual, time.monotonic(), modifiers)])[
            -32:
        ]

    def try_special(self):
        if self.engine and self.engine.special:
            config = self.engine.config[self.engine.special]
            if config["enabled"]:
                pos = self.manual or (self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2)
                self.events.append(
                    self.tracker.press(
                        BUTTONS[config["button"]], pos, time.monotonic(), MODIFIERS[config["modifiers"]]
                    )
                )

    def set(self, path, config):
        self.events.clear()
        self.test_button.pack_forget()
        self.tracker.previous = None
        if path is not None:
            sprite = load_sprite(path)
            self.engine = (trial_runtime.create_display(path,config) if trial_runtime.enabled(path, config)
                           else EffectEngine(sprite, APPEARANCES.get(path.stem, DEFAULT_APPEARANCE), config, path))
            if self.engine.special:
                self.test_button.pack(side="left")
                self.test_button.state(
                    ["!disabled"] if config[self.engine.special]["enabled"] else ["disabled"]
                )
            self.photo = ImageTk.PhotoImage(sprite, master=self.canvas)
            self.canvas.itemconfigure(self.pointer, image=self.photo)
        else:
            self.engine = None
            self.canvas.itemconfigure(self.pointer, image="")
        self.canvas.itemconfigure(self.fx, image="")
        self.restart_demo()

    def tick(self):
        delay = 80
        if self.engine and self.canvas.winfo_viewable():
            now = time.monotonic()
            elapsed = now - self.start
            phase = elapsed % 6
            w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
            mode = self.mode.get()
            travel = elapsed if mode == "移動" else min(phase, 2.6) if mode == "自動" else 0
            x = w * 0.47 + min(70, w * 0.24) * math.sin(travel * 2.4)
            y = h * 0.46 + min(44, h * 0.22) * math.sin(travel * 4.8)
            pos = self.manual or (round(x), round(y))
            if mode == "自動" and not self.manual:
                pulse = sum(phase >= t for t in (2.8, 3.45, 4.15, 4.34))
                mark = int(elapsed // 6), pulse
                if pulse and mark != self.mark:
                    self.events.append(self.tracker.press("right" if pulse == 2 else "left", pos, now))
                    if pulse != 2 and isinstance(self.engine,trial_runtime.TrialDisplay):
                        self.events.append(self.tracker.press("left_up",pos,now))
                self.mark = mark
            if isinstance(self.engine,trial_runtime.TrialDisplay):
                screen_w = max(w, self.canvas.winfo_screenwidth())
                screen_h = max(h, self.canvas.winfo_screenheight())
                offset = ((screen_w-w)//2, (screen_h-h)//2)
                desktop_pos = (pos[0]+offset[0], pos[1]+offset[1])
                desktop_events = [ClickEvent(e.kind, (e.pos[0]+offset[0], e.pos[1]+offset[1]),
                                             e.time, e.modifiers) for e in self.events]
                frame = self.engine.step(desktop_pos, now, desktop_events,
                                         (0,0,screen_w,screen_h))
                self.events.clear()
                self.effect_photo = ImageTk.PhotoImage(frame, master=self.canvas) if frame else None
                self.canvas.itemconfigure(self.pointer,image="")
                self.canvas.itemconfigure(self.fx, image=self.effect_photo or "")
                if frame:
                    x,y = self.engine.frame_origin
                    self.canvas.coords(self.fx,x-offset[0]+frame.width/2,y-offset[1]+frame.height/2)
                self.timer = self.canvas.after(25,self.tick)
                return
            frame = self.engine.step(pos, now, self.events)
            self.events.clear()
            self.effect_photo = ImageTk.PhotoImage(frame, master=self.canvas) if frame else None
            self.canvas.itemconfigure(self.fx, image=self.effect_photo or "")
            self.idle_photo = (ImageTk.PhotoImage(self.engine.pointer_image, master=self.canvas)
                               if self.engine.idle_turn_step is not None else None)
            self.canvas.itemconfigure(self.pointer, image=self.idle_photo or self.photo)
            self.canvas.coords(self.fx, *pos)
            hot = self.engine.pointer_hot
            self.canvas.coords(self.pointer, pos[0] - hot[0], pos[1] - hot[1])
            delay = 32 if self.engine.still < 0.5 else 50
        self.timer = self.canvas.after(delay, self.tick)

    def close(self):
        self.canvas.after_cancel(self.timer)


class Editor:
    def __init__(self, root, entries, system, title):
        self.root, self.entries, self.system = root, entries, system
        self.store = Settings(system.store / "effects.json")
        self.drafts = {}
        self.path = None
        self.applied = ""
        self.preview_job = None
        self.live_values = None
        self.effect = FunnelEffect(root, self.effect_error, system.store / "idle-animations")
        root.title(title)
        self.restore = "元に戻す"
        while self.restore in entries:
            self.restore += "（設定）"
        container = ttk.Frame(root, padding=12)
        container.pack(fill="both", expand=True)
        left = ttk.Frame(container)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        right = ttk.Frame(container)
        right.grid(row=0, column=1, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)
        ttk.Label(left, text="分類").pack(anchor="w")
        self.category = ttk.Combobox(left, state="readonly", values=[*entries, self.restore], width=29)
        self.category.pack(fill="x")
        ttk.Label(left, text="カーソル").pack(anchor="w", pady=(8, 0))
        self.cursor = ttk.Combobox(left, state="readonly", width=29)
        self.cursor.pack(fill="x")
        ttk.Label(left, text="プレビュー").pack(anchor="w", pady=(12, 4))
        pane = ttk.Frame(left)
        pane.pack(fill="both", expand=True)
        self.preview = Preview(pane)
        ttk.Label(left, text="枠内で移動、左・右・ダブルクリックを試せます。", wraplength=245).pack(
            anchor="w"
        )
        preset_bar = ttk.Frame(right)
        preset_bar.pack(fill="x")
        ttk.Label(preset_bar, text="プリセット").pack(side="left")
        self.preset = ttk.Combobox(preset_bar, state="readonly", width=14)
        self.preset.pack(side="left", padx=4, expand=True, fill="x")
        ttk.Button(preset_bar, text="管理", width=5, command=self.manage).pack(side="right")
        self.rows = ttk.Frame(right)
        self.idle_motion_controls = ttk.Frame(right)
        ttk.Label(self.idle_motion_controls, text="待機モーション").pack(side="left")
        self.idle_motion = ttk.Combobox(self.idle_motion_controls, state="readonly",
                                        values=("なし", "横回転"), width=9)
        self.idle_motion.pack(side="left", padx=4)
        self.idle_motion.bind("<<ComboboxSelected>>", self.choose_idle_motion)
        ttk.Button(self.idle_motion_controls, text="設定", width=5,
                   command=lambda: self.details("idle")).pack(side="right")
        self.rows.pack(fill="both", expand=True, pady=(8, 2))
        self.rows.columnconfigure(2, weight=1)
        self.flags, self.sliders, self.numbers = {}, {}, {}
        self.row_checks, self.primary_labels = {}, {}
        self.refreshing = False
        self.special_widgets = {}
        self.special_title = ttk.Label(self.rows)
        self.special_title.grid(row=len(NAMES) - len(SPECIAL), columnspan=5, sticky="w", pady=(7, 2))
        for idx, (group, label) in enumerate(NAMES.items()):
            if group in SPECIAL:
                idx += 1
            var = self.flags[group] = tk.BooleanVar()
            self.row_checks[group] = ttk.Checkbutton(
                self.rows,
                text=label,
                variable=var,
                command=lambda g=group: self.edit(g, "enabled", self.flags[g].get()),
            )
            self.row_checks[group].grid(row=idx, column=0, sticky="w")
            key = next(iter(FIELDS[group]))
            field = FIELDS[group][key]
            slider = self.sliders[group] = ttk.Scale(
                self.rows,
                from_=field.low,
                to=field.high,
                length=68,
                command=lambda val, g=group, k=key: self.main_slider(g, k, val),
            )
            self.primary_labels[group] = ttk.Label(self.rows, text=field.label.split(" ")[0])
            self.primary_labels[group].grid(row=idx, column=1, sticky="e", padx=(6, 0))
            slider.grid(row=idx, column=2, sticky="ew", padx=(5, 0))
            self.numbers[group] = ttk.Label(self.rows, width=5, anchor="e")
            self.numbers[group].grid(row=idx, column=3)
            ttk.Button(self.rows, text="詳細", width=5, command=lambda g=group: self.details(g)).grid(
                row=idx, column=4, pady=2
            )
            if group in SPECIAL:
                self.special_widgets[group] = self.rows.grid_slaves(row=idx)
        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=(4, 0))
        for label, cmd in (
            ("全ON", lambda: self.all_enabled(True)),
            ("全OFF", lambda: self.all_enabled(False)),
            ("初期値に戻す", self.reset),
        ):
            ttk.Button(bar, text=label, command=cmd, width=11 if label.startswith("初期") else 6).pack(
                side="left", padx=(0, 3)
            )
        footer = ttk.Frame(container)
        footer.grid(row=1, columnspan=2, sticky="ew", pady=(12, 0))
        self.state = tk.StringVar()
        self.status = tk.StringVar(
            value=self.store.warning or (
                "前回の装備は凍結中です。現行対象を選んで「適用」を押してください。"
                if is_frozen(self.store.active) else "分類とカーソルを選んで「適用」を押してください。"
            )
        )
        ttk.Label(footer, textvariable=self.state).pack(side="left")
        self.apply_button = ttk.Button(footer, text="適用 (F5)", command=self.apply)
        self.apply_button.pack(side="right")
        ttk.Label(container, textvariable=self.status, wraplength=570).grid(
            row=2, columnspan=2, sticky="w", pady=(5, 0)
        )
        self.category.bind("<<ComboboxSelected>>", lambda _: self.choose_category())
        self.cursor.bind("<<ComboboxSelected>>", lambda _: self.choose())
        self.preset.bind("<<ComboboxSelected>>", self.choose_preset)
        root.bind("<F5>", lambda _: self.apply_button.invoke())
        root.protocol("WM_DELETE_WINDOW", self.close)
        active = self.store.active
        target = next((p for paths in entries.values() for p in paths if self.identity(p) == active), None)
        self.category.set(target.parent.name if target else next(iter(entries), self.restore))
        self.choose_category(target)

    @staticmethod
    def identity(path):
        return f"{path.parent.name}/{path.name}" if path else ""

    @property
    def key(self):
        return self.identity(self.path)

    def binding(self):
        return self.drafts.get(self.key, self.store.binding(self.key))

    def values(self):
        b = self.binding()
        return resolve(self.category.get(), self.store.choices()[b["preset"]], b["overrides"], self.key)

    def choose_category(self, target=None):
        paths = self.entries.get(self.category.get(), [])
        counts = Counter(p.stem.casefold() for p in paths)
        labels = [p.name if counts[p.stem.casefold()] > 1 else p.stem for p in paths]
        self.cursor.configure(values=labels or ["変更前のカーソル"])
        self.cursor.current(paths.index(target) if target in paths else 0)
        self.choose()

    def choose(self):
        paths = self.entries.get(self.category.get(), [])
        self.path = paths[self.cursor.current()] if paths else None
        self.refresh()

    def refresh(self):
        self.refreshing = True
        self.preset.configure(
            values=list(self.store.choices()), state="readonly" if self.path else "disabled"
        )
        self.preset.set(self.binding()["preset"] if self.path else "")
        values, _ = self.values()
        for g in FIELDS:
            rotating = g == "idle" and bool(idle_sheet(self.path)) and values[g]["motion"] == "横回転"
            key = "turn_period" if rotating else next(iter(FIELDS[g]))
            field = FIELDS[g][key]
            self.row_checks[g].configure(text="待機横回転" if rotating else NAMES[g])
            self.primary_labels[g].configure(text="1周（秒）" if rotating else field.label.split(" ")[0])
            self.sliders[g].configure(from_=field.low, to=field.high,
                                       command=lambda val, group=g, name=key: self.main_slider(group, name, val))
            self.flags[g].set(values[g]["enabled"] and bool(self.path))
            self.sliders[g].set(values[g][key])
            self.numbers[g].configure(text=format(values[g][key], ".3g"))
        for w in self.rows.winfo_children():
            w.state(["!disabled"] if self.path else ["disabled"])
        if trial_runtime.supported(self.path):
            group = special_group(self.key)
            fixed_groups = [group] + (["boost", "trail"] if self.path.stem != "フィンファンネル" else [])
            for widget in [w for g in fixed_groups for w in (self.sliders[g], self.numbers[g], self.primary_labels[g])]:
                widget.state(["disabled"])
        self.refreshing = False
        self.feedback()

    def show_special_controls(self):
        for widget in self.rows.winfo_children():
            if "row" in widget.grid_info():
                widget._settings_row = int(widget.grid_info()["row"])
        if idle_sheet(self.path):
            self.idle_motion.set(self.values()[0]["idle"]["motion"])
            self.idle_motion_controls.pack(fill="x", before=self.rows, pady=(6, 0))
        else:
            self.idle_motion_controls.pack_forget()
        group = special_group(self.key)
        for name, widgets in self.special_widgets.items():
            for widget in widgets:
                if name == group:
                    widget.grid()
                else:
                    widget.grid_remove()
        if trial_runtime.supported(self.path):
            fin = self.path.stem == "フィンファンネル"
            supported_groups = {"idle", "followers", group}
            if not fin:
                supported_groups |= {"boost", "trail", "click", "particles", "deploy", "rare"}
            for name in NAMES:
                row = int(self.row_checks[name].grid_info().get("row", -1))
                if row < 0:
                    row = getattr(self.row_checks[name], "_settings_row", -1)
                if row < 0:
                    continue
                for widget in self.rows.winfo_children():
                    info = widget.grid_info()
                    widget_row = int(info.get("row", getattr(widget, "_settings_row", -2)))
                    if widget_row == row:
                        widget._settings_row = row
                        widget.grid() if name in supported_groups else widget.grid_remove()
        if group:
            config = self.values()[0][group]
            self.special_title.configure(text=f"特殊演出　{config['modifiers']}＋{config['button']}")
            self.special_title.grid()
        else:
            self.special_title.grid_remove()

    def choose_idle_motion(self, _=None):
        self.edit("idle", "motion", self.idle_motion.get())
        if self.idle_motion.get() == "横回転":
            self.edit("idle", "enabled", True)
            self.preview.mode.set("停止")
            self.preview.restart_demo()
        self.refresh()

    def feedback(self):
        self.show_special_controls()
        dirty = self.binding() != self.store.binding(self.key)
        self.state.set(
            "編集中（未適用）"
            if dirty
            else "変更前のポインターを復元"
            if not self.path
            else "演出停止中" if self.key == self.applied and self.live_values is None
            else "適用済み"
            if self.key == self.applied and self.values()[0] == self.live_values
            else "保存値を表示中"
        )
        if self.preview_job:
            self.root.after_cancel(self.preview_job)
        self.preview_job = self.root.after(45, self.update_preview)

    def update_preview(self):
        self.preview_job = None
        self.preview.set(self.path, self.values()[0])

    def edit(self, g, k, value):
        if self.refreshing or not self.path:
            return
        b = self.binding()
        self.drafts[self.key] = b
        base, _ = resolve(self.category.get(), self.store.choices()[b["preset"]], {}, self.key)
        overrides = b["overrides"].setdefault(g, {})
        if value == base[g][k]:
            overrides.pop(k, None)
        else:
            overrides[k] = value
        if not overrides:
            b["overrides"].pop(g, None)
        self.feedback()

    @staticmethod
    def number(field, val):
        return round(float(val)) if isinstance(field.default, int) else round(float(val), 2)

    def main_slider(self, g, k, val):
        if not self.refreshing:
            n = self.number(FIELDS[g][k], val)
            self.numbers[g].configure(text=format(n, ".3g"))
            self.edit(g, k, n)

    def choose_preset(self, _=None):
        if self.path:
            b = self.binding()
            b["preset"] = self.preset.get()
            self.drafts[self.key] = b
            self.refresh()

    def all_enabled(self, value):
        if self.path:
            if trial_runtime.supported(self.path):
                self.edit(special_group(self.key), "click_fire_enabled", value)
            for g in FIELDS:
                if g in SPECIAL and g != special_group(self.key):
                    continue
                self.edit(g, "enabled", value)
            self.refresh()

    def reset(self):
        if self.path:
            self.drafts[self.key] = default_binding(self.key)
            self.refresh()

    def subwindow(self, title):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.transient(self.root)
        win.grab_set()
        return win

    def details(self, g):
        if not self.path:
            return
        win = self.subwindow(NAMES[g])
        scroll = tk.Canvas(
            win, width=450, height=min(390, self.root.winfo_screenheight() - 145), highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=scroll.yview)
        scroll.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        scroll.pack(fill="both", expand=True)
        page = ttk.Frame(scroll, padding=10)
        scroll.create_window(0, 0, window=page, anchor="nw")
        page.bind("<Configure>", lambda _: scroll.configure(scrollregion=scroll.bbox("all")))
        win.bind("<MouseWheel>", lambda ev: scroll.yview_scroll(int(-ev.delta / 120), "units"))
        values, origins = self.values()
        for idx, (k, f) in enumerate(FIELDS[g].items()):
            if trial_runtime.supported(self.path):
                allowed = {"followers": {"enabled", "count"},
                           "boost": {"enabled"}, "trail": {"enabled"}}
                if g in allowed and k not in allowed[g]:
                    continue
                if g == "idle" and k not in {"enabled", "delay", "motion", "turn_period", "turn_direction"}:
                    continue
            if k in ("click_fire_enabled","orientation_mode","escort_count") and not trial_runtime.supported(self.path):
                continue
            if trial_runtime.supported(self.path) and g == "followers" and k not in ("enabled","count"):
                continue
            if trial_runtime.supported(self.path) and g != "barrier" and g == special_group(self.key) and k in ("duration","count","radius","turns","color","opacity"):
                continue
            if g == "idle" and k in ("motion", "turn_period", "turn_direction") and not idle_sheet(self.path):
                continue
            if (g == "idle" and idle_sheet(self.path) and values[g]["motion"] == "横回転"
                    and k in ("intensity", "period", "drift", "fade", "color", "opacity")):
                continue
            ttk.Label(page, text=f.label).grid(row=idx, column=0, sticky="w", pady=3)
            origin = ttk.Label(page, text=origins[g][k], width=10)
            origin.grid(row=idx, column=3)
            value = values[g][k]

            def changed(v, key=k, label=origin):
                self.edit(g, key, v)
                label.configure(text=self.values()[1][g][key])
                self.refresh()

            if f.choices:
                labels = {"follow":"移動方向に追従", "fixed_upper_left":"左上固定"} if k == "orientation_mode" else {}
                w = ttk.Combobox(page, state="readonly", values=[labels.get(v,v) for v in f.choices], width=14)
                w.set(labels.get(value,value))
                w.bind("<<ComboboxSelected>>", lambda _, cb=w, fn=changed, choices=f.choices: fn(choices[cb.current()]))
            elif isinstance(value, bool):
                var = tk.BooleanVar(value=value)
                w = ttk.Checkbutton(page, variable=var, command=lambda v=var, fn=changed: fn(v.get()))
                w.variable = var
            elif isinstance(value, str):
                w = ttk.Frame(page)
                label = ttk.Label(w, text=value, width=8)
                label.pack(side="left")

                def set_color(default=False, fn=changed, lab=label):
                    selected = "機体色" if default else colorchooser.askcolor(parent=win)[1]
                    if selected:
                        lab.configure(text=selected)
                        fn(selected)

                ttk.Button(w, text="色", width=3, command=set_color).pack(side="left")
                ttk.Button(w, text="機体色", width=6, command=lambda fn=set_color: fn(True)).pack(side="left")
            else:
                label = ttk.Label(page, text=format(value, ".3g"), width=6)
                label.grid(row=idx, column=2)
                w = ttk.Scale(page, from_=f.low, to=f.high, length=130)
                w.set(value)

                def slide(val, field=f, fn=changed, lab=label):
                    n = self.number(field, val)
                    lab.configure(text=format(n, ".3g"))
                    fn(n)

                w.configure(command=slide)
            w.grid(row=idx, column=1, sticky="w", padx=6)
        ttk.Button(page, text="閉じる", command=win.destroy).grid(
            row=len(FIELDS[g]), column=0, sticky="w", pady=8
        )

    def persist(self, mutation):
        old = deepcopy((self.store.presets, self.store.cursors, self.store.active))
        try:
            mutation()
            self.store.write()
            return True
        except (OSError, ValueError) as error:
            self.store.presets, self.store.cursors, self.store.active = old
            messagebox.showerror("設定を保存できません", str(error), parent=self.root)
            return False

    def manage(self):
        win = self.subwindow("プリセット管理")
        page = ttk.Frame(win, padding=12)
        page.pack(fill="both", expand=True)
        choice = ttk.Combobox(page, state="readonly", width=28)
        choice.grid(row=0, columnspan=2, sticky="ew", pady=6)

        def names(selected):
            choice.configure(values=list(self.store.choices()))
            choice.set(selected)

        names(self.binding()["preset"])

        def new_name(initial):
            n = simpledialog.askstring("プリセット名", "保存する名前", initialvalue=initial, parent=win)
            if n is None:
                return None
            n = n.strip()
            if not valid_name(n) or n in self.store.choices():
                messagebox.showerror(
                    "プリセット名", "重複しない1～100文字の名前を入力してください。", parent=win
                )
                return None
            return n

        def operation(action):
            selected = choice.get()
            if action in ("更新", "改名", "削除") and selected in SAMPLES:
                messagebox.showinfo(
                    "プリセット", "初期サンプルは「複製」で編集用に保存できます。", parent=win
                )
                return
            try:
                pending = deepcopy(self.drafts)
                presets = deepcopy(self.store.presets)
                bindings = deepcopy(self.store.cursors)
                dest = selected
                if action == "書き出す":
                    file = filedialog.asksaveasfilename(
                        parent=win, defaultextension=".json", filetypes=[("JSON", "*.json")]
                    )
                    if file:
                        atomic_write(
                            Path(file),
                            encode(
                                dict(schema_version=1, name=selected, effects=self.store.choices()[selected])
                            ),
                        )
                    return
                if action in ("新規", "複製", "読み込む"):
                    if action == "新規" and not self.path:
                        return
                    imported = None
                    if action == "読み込む":
                        file = filedialog.askopenfilename(parent=win, filetypes=[("JSON", "*.json")])
                        if not file:
                            return
                        suggested, imported = read_preset(Path(file))
                    else:
                        suggested = selected + " のコピー" if action == "複製" else "マイプリセット"
                    dest = new_name(suggested)
                    if not dest:
                        return
                    presets[dest] = (
                        self.values()[0]
                        if action == "新規"
                        else self.store.choices()[selected]
                        if action == "複製"
                        else imported
                    )
                elif action == "更新":
                    if not self.path or not messagebox.askyesno(
                        "上書き保存", f"編集中の値で「{selected}」を更新しますか？", parent=win
                    ):
                        return
                    presets[selected] = self.values()[0]
                elif action in ("改名", "削除"):
                    if action == "改名":
                        dest = new_name(selected)
                        if not dest:
                            return
                        presets[dest] = presets[selected]
                    else:
                        if not messagebox.askyesno(
                            "プリセット削除",
                            f"「{selected}」を削除しますか？ 個別の見た目は保持されます。",
                            parent=win,
                        ):
                            return
                        dest = STANDARD
                    for collection in (bindings, pending):
                        for ident, b in collection.items():
                            if b["preset"] == selected:
                                if action == "削除":
                                    category = ident.split("/", 1)[0]
                                    full, _ = resolve(category, presets[selected], b["overrides"], ident)
                                    base, _ = resolve(category, {}, {}, ident)
                                    b["overrides"] = difference(full, base)
                                b["preset"] = dest
                    del presets[selected]

                def change():
                    self.store.presets, self.store.cursors = presets, bindings

                if self.persist(change):
                    self.drafts = pending
                    names(dest)
                    self.refresh()
                    self.status.set("プリセットを保存しました。デスクトップへの反映は「適用」で行います。")
            except (ValueError, OSError, RecursionError) as error:
                messagebox.showerror("プリセット", str(error), parent=win)

        for i, (label, action) in enumerate(
            (
                ("編集中の値を新規保存", "新規"),
                ("編集中の値で上書き", "更新"),
                ("複製", "複製"),
                ("名前を変更", "改名"),
                ("削除", "削除"),
                ("JSONを読み込む", "読み込む"),
                ("JSONに書き出す", "書き出す"),
            )
        ):
            ttk.Button(page, text=label, command=lambda a=action: operation(a)).grid(
                row=1 + i // 2, column=i % 2, sticky="ew", pady=2
            )
        ttk.Button(page, text="閉じる", command=win.destroy).grid(row=5, columnspan=2, sticky="e", pady=5)

    def effect_error(self, error):
        logging.getLogger("funnel.display").error("Desktop effect stopped: %s", error, exc_info=True)
        self.live_values = None
        self.state.set("演出停止中")
        self.status.set(f"カーソルは適用済みです。演出を停止しました。{error}")

    def start_effects(self, target):
        self.applied = self.key
        self.live_values = self.values()[0] if target else None
        if target:
            try:
                self.effect.start(target, self.values()[0])
            except (OSError, ValueError, RuntimeError, ImportError, MemoryError) as error:
                self.effect_error(error)
        else:
            self.effect.stop()

    def apply(self):
        target = self.path
        logging.getLogger("funnel.display").info("Apply %s", self.key)
        b = deepcopy(self.binding())
        try:
            msg = self.system.apply(target)
        except (OSError, ValueError) as error:
            messagebox.showerror("カーソル切替", str(error), parent=self.root)
            return
        self.status.set(msg)
        self.start_effects(target)

        def change():
            self.store.active = self.key
            if target:
                self.store.cursors[self.key] = b

        if self.persist(change):
            self.drafts.pop(self.key, None)
        self.feedback()

    def close(self):
        dirty = any(b != self.store.binding(k) for k, b in self.drafts.items())
        if dirty and not messagebox.askyesno(
            "未適用の編集", "未適用の編集を破棄して終了しますか？", parent=self.root
        ):
            return
        if self.preview_job:
            self.root.after_cancel(self.preview_job)
        self.preview.close()
        self.effect.stop()
        self.root.destroy()
