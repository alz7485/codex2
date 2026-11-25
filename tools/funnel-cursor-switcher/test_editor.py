import tkinter as tk
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase
from unittest.mock import Mock, patch
from runpy import run_path

from effect_editor import Editor
from effect_settings import Settings, special_group


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def button(win, text):
    return next(w for w in descendants(win) if w.winfo_class() == "TButton" and w.cget("text") == text)


class EditorFlow(TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            raise SkipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.system = Mock(store=Path(self.temp.name))
        self.system.apply.return_value = "適用しました。"
        folder = Path(__file__).with_name("カーソル")
        self.entries = {
            "ファンネル": [folder / "ファンネル" / "キュベレイ.cur"],
            "自作": [Path(self.temp.name) / "自作" / "光.ani"],
        }
        self.ui = Editor(self.root, self.entries, self.system, "テスト")
        self.fx = self.ui.effect = Mock()
        self.root.update()
        self.addCleanup(self.ui.preview.close)
        self.addCleanup(self.cancel_update)
        self.errors = []
        self.root.report_callback_exception = lambda typ, val, tb: self.errors.append(str(val))
        self.addCleanup(lambda: self.assertEqual(self.errors, []))

    def cancel_update(self):
        if self.ui.preview_job:
            self.root.after_cancel(self.ui.preview_job)

    def test_fin_idle_motion_controls_and_saved_settings(self):
        path = Path(__file__).with_name("カーソル") / "ファンネル" / "フィンファンネル.cur"
        self.entries["ファンネル"].append(path)
        self.ui.category.set("ファンネル")
        self.ui.choose_category(path)
        self.root.update()
        self.assertEqual(self.ui.idle_motion_controls.winfo_manager(), "pack")
        self.ui.idle_motion.set("横回転")
        self.ui.choose_idle_motion()
        self.assertTrue(self.ui.values()[0]["idle"]["enabled"])
        self.assertEqual(self.ui.values()[0]["idle"]["motion"], "横回転")
        self.assertEqual(self.ui.preview.mode.get(), "停止")
        self.assertEqual(self.ui.row_checks["idle"].cget("text"), "待機横回転")
        self.ui.main_slider("idle", "turn_period", "3.2")
        self.ui.refresh()
        self.ui.apply()
        self.assertEqual(self.fx.start.call_args.args[1]["idle"]["motion"], "横回転")
        saved = Settings(self.system.store / "effects.json")
        self.assertEqual(saved.binding("ファンネル/フィンファンネル.cur")["overrides"]["idle"]["motion"], "横回転")
        self.assertEqual(saved.binding("ファンネル/フィンファンネル.cur")["overrides"]["idle"]["turn_period"], 3.2)
        self.ui.choose_category(self.entries["ファンネル"][0])
        self.root.update()
        self.assertEqual(self.ui.idle_motion_controls.winfo_manager(), "pack")

    def test_image_cards_select_across_categories_after_apply(self):
        ui=self.ui
        self.root.update()
        self.assertFalse(ui.category.winfo_ismapped())
        self.assertFalse(ui.cursor.winfo_ismapped())
        self.assertEqual(set(ui.equipment_buttons),{p for paths in self.entries.values() for p in paths})
        ui.apply()
        other=self.entries["自作"][0]
        ui.equipment_buttons[other].invoke()
        self.root.update()
        self.assertEqual(ui.path,other)
        self.assertEqual(ui.category.get(),"自作")
        self.assertIn("selected",ui.equipment_buttons[other].state())
        self.assertTrue(ui.preview.paused)
        self.assertEqual(self.system.apply.call_count,1)
        ui.restore_button.invoke()
        self.system.apply.assert_called_with(None)

    def test_dark_theme_and_settings_dialog_remain_usable(self):
        from tkinter import ttk
        self.assertEqual(ttk.Style(self.root).lookup("TLabel","foreground"),"#f1f5f9")
        self.ui.apply()
        self.ui.idle_settings_button.invoke()
        self.root.update()
        dialog=next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel))
        self.assertEqual(dialog.cget("background"),"#090c11")
        dialog.destroy()

    def test_preview_buttons_are_centered_once_and_do_not_apply(self):
        from copy import deepcopy
        ui=self.ui
        ui.apply()
        original=deepcopy(ui.preview.base_config)
        ui.preview.action_buttons["fire"].invoke()
        self.assertEqual(ui.preview.sequence.kind,"fire")
        self.assertEqual(ui.preview.mode.get(),"停止")
        self.assertEqual(ui.preview.manual,(ui.preview.canvas.winfo_width()/2,ui.preview.canvas.winfo_height()/2))
        self.assertTrue(ui.preview.paused)
        self.assertEqual(ui.preview.base_config,original)
        self.assertEqual(self.system.apply.call_count,1)
        for age in (0.,.15,.21,2.6):
            ui.preview.sequence.time=age
            ui.preview.canvas.after_cancel(ui.preview.timer)
            ui.preview.tick()
        self.assertIsNone(ui.preview.sequence)
        self.assertTrue(ui.preview.completed)
        ui.preview.canvas.after_cancel(ui.preview.timer)
        ui.preview.tick()
        stamp=ui.preview.engine.control.last
        ui.preview.canvas.after_cancel(ui.preview.timer)
        ui.preview.tick()
        self.assertEqual(ui.preview.engine.control.last,stamp)
        self.assertEqual(ui.preview.base_config,original)

    def select(self, category):
        self.ui.category.set(category)
        self.ui.choose_category()

    def test_apply_draft_restore_and_minimize(self):
        ui = self.ui
        ui.all_enabled(True)
        self.assertFalse(self.system.apply.called)
        self.select("自作")
        self.assertFalse(ui.values()[0]["click"]["enabled"])
        self.select("ファンネル")
        self.assertTrue(ui.values()[0]["click"]["enabled"])
        ui.apply()
        self.fx.start.assert_called_once()
        self.assertTrue(Settings(ui.store.path).binding(ui.key)["overrides"]["click"]["enabled"])
        self.root.iconify()
        self.fx.stop.assert_not_called()
        self.root.deiconify()
        self.select(ui.restore)
        ui.apply()
        self.system.apply.assert_called_with(None)
        self.fx.stop.assert_called_once()

    def test_special_command_preview_and_save(self):
        ui = self.ui
        self.assertTrue(ui.special_widgets["spiral"][0].winfo_ismapped())
        self.assertFalse(ui.special_widgets["barrier"][0].winfo_ismapped())
        ui.edit("spiral", "modifiers", "Ctrl＋Alt")
        ui.edit("spiral", "button", "中クリック")
        ui.update_preview()
        ui.preview.try_special()
        ui.preview.sequence.time=.16
        _,events=ui.preview.sequence.sample((100,100),(200,200))
        event = events[0]
        self.assertEqual((event.kind, event.modifiers), ("middle", 6))
        ui.apply()
        self.assertEqual(
            Settings(ui.store.path).binding(ui.key)["overrides"]["spiral"]["button"], "中クリック"
        )
        self.select("自作")
        self.root.update()
        self.assertFalse(ui.special_title.winfo_ismapped())

    def test_all_equipment_special_controls_and_preview(self):
        ui = self.ui
        folder = Path(__file__).with_name("カーソル")
        discover = run_path(str(folder.parent / "FunnelCursorSwitcher.pyw"))["discover_cursors"]
        ui.entries.update(discover(folder))
        for category, paths in ui.entries.items():
            if category == "自作":
                continue
            for path in paths:
                ui.category.set(category)
                ui.choose_category(path)
                ui.update_preview()
                self.root.update()
                group = special_group(ui.key)
                self.assertEqual(ui.preview.engine.special, group)
                for key, widgets in ui.special_widgets.items():
                    self.assertEqual(bool(widgets[0].winfo_ismapped()), key == group)
                self.assertTrue(ui.preview.engine.config[group]["enabled"])
                ui.preview.try_special()
                self.assertEqual(ui.preview.sequence.kind,"special")
                ui.apply()
                self.assertTrue(Settings(ui.store.path).binding(ui.key)["overrides"][group]["enabled"])

    def test_frozen_previous_selection_falls_back_and_preserves_settings(self):
        key = "ファンネル/ナイチンゲール.cur"
        store = Settings(self.ui.store.path)
        store.active = key
        store.cursors[key] = {"preset": "標準", "overrides": {"volley": {"enabled": True, "radius": 73}}}
        original = store.cursors[key]
        store.write()
        child = tk.Toplevel(self.root)
        self.addCleanup(child.destroy)
        other = Editor(child, self.entries, self.system, "凍結した装備")
        other.effect = Mock()
        self.addCleanup(other.preview.close)
        self.addCleanup(lambda: child.after_cancel(other.preview_job) if other.preview_job else None)
        self.assertEqual(other.key, "ファンネル/キュベレイ.cur")
        self.assertIn("凍結", other.status.get())
        other.apply()
        self.assertEqual(Settings(store.path).cursors[key], original)

    def test_named_presets_and_delete_preserves_look(self):
        ui = self.ui
        ui.edit("boost", "width", 1.6)
        ui.manage()
        win = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        with patch(
            "effect_editor.simpledialog.askstring", side_effect=["紫の光", "複製した光", "新しい名前"]
        ):
            for action in ("編集中の値を新規保存", "複製", "名前を変更"):
                button(win, action).invoke()
        self.assertIn("新しい名前", ui.store.presets)
        self.assertNotIn("複製した光", ui.store.presets)
        win.destroy()
        ui.reset()
        ui.preset.set("新しい名前")
        ui.choose_preset()
        ui.apply()
        before = ui.values()[0]
        ui.manage()
        win = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        with patch("effect_editor.messagebox.askyesno", return_value=True):
            button(win, "削除").invoke()
        win.destroy()
        self.assertEqual(ui.values()[0], before)
        self.assertNotIn("新しい名前", Settings(ui.store.path).presets)
        ui.details("followers")
        self.root.update()
        win = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        button(win, "閉じる").invoke()
        ui.update_preview()
        ui.preview.press(Mock(x=50, y=60, state=0), "right")
        self.assertEqual(ui.preview.events[-1].kind, "right")

    def test_shared_escort_options_visible_and_bound_on_main_screen(self):
        self.assertEqual(self.ui.follower_options.winfo_manager(), "grid")
        self.ui.follower_size.set("120")
        self.ui.change_follower_size()
        self.assertEqual(self.ui.values()[0]["followers"]["size_percent"],120)
        check = next(w for w in self.ui.follower_options.winfo_children()
                     if w.winfo_class()=="TCheckbutton")
        check.invoke()
        self.assertFalse(self.ui.values()[0]["followers"]["fire_enabled"])

    def test_restore_button_does_not_require_dropdown(self):
        self.ui.restore_button.invoke()
        self.fx.stop.assert_called()
        self.system.apply.assert_called_with(None)
        self.assertIsNone(self.ui.path)
        self.assertFalse(self.ui.store.active)
