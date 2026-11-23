import tkinter as tk
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase
from unittest.mock import Mock, patch

from effect_editor import Editor
from effect_settings import Settings


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
        ui.preview.press(Mock(x=50, y=60), "right")
        self.assertEqual(ui.preview.events[-1].kind, "right")
