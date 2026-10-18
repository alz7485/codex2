import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from catalog_studio import macro_import
from catalog_studio.integrated import IntegratedStudio
from catalog_studio.macro_export_ui import open_export


class MacroExportGuiTests(unittest.TestCase):
    def setUp(self):
        try: self.app = IntegratedStudio()
        except tk.TclError as exc: self.skipTest(str(exc))
        self.errors = []
        self.app.report_callback_exception = lambda k, v, t: self.errors.append(str(v))
        self.app.update()

    def tearDown(self):
        if hasattr(self, 'app'): self.app.destroy()

    def editor(self, page):
        source = 'NEW PTSET /EXPORT-PTS\nNEW PTAXI\nNUMB 1\nPDIS (PARA[3] / 2)\nEND\nEND' if page == 'ptset' else 'NEW GMSET /EXPORT-GMS\nNEW SCYL\nPHEI (-PARA[3])\nPDIA (PARA[2])\nEND\nEND'
        record = macro_import.parse(source).definitions[0]
        record['elements'][0]['attrs']['DESC'] = '日本語の説明①'
        record['preset_id'] = self.app.data['definitions'][0].get('preset_id')
        self.app.data['definitions'].append(record)
        self.app.definition_id = record['id']; self.app.switch(page); self.app.update()
        return self.app.geometry_editor

    def test_buttons_save_current_set_and_preserve_project(self):
        for page in ('ptset', 'gmset'):
            editor = self.editor(page)
            before = copy.deepcopy(self.app.data); dirty = self.app.dirty
            self.assertTrue(editor.export_macro_button.winfo_ismapped())
            window = open_export(editor); self.app.update()
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'export.mac'
                with patch('catalog_studio.macro_export_ui.filedialog.asksaveasfilename', return_value=str(path)):
                    window.save_button.invoke(); self.app.update()
                definitions = macro_import.parse(path.read_text(encoding='cp932')).definitions
                self.assertEqual(len(definitions), 1)
                self.assertEqual(definitions[0]['name'], editor.definition()['name'])
                self.assertEqual(definitions[0]['elements'][0]['attrs'], editor.definition()['elements'][0]['attrs'])
            self.assertEqual(self.app.data, before); self.assertEqual(self.app.dirty, dirty)
        self.assertEqual(self.errors, [])

    def test_cancel_file_picker_and_window_do_not_save(self):
        editor = self.editor('ptset'); before = copy.deepcopy(self.app.data)
        window = open_export(editor); self.app.update()
        with patch('catalog_studio.macro_export_ui.filedialog.asksaveasfilename', return_value=''), patch('catalog_studio.macro_export.save') as save:
            window.save_button.invoke()
        save.assert_not_called(); self.assertTrue(window.winfo_exists())
        window.destroy(); self.assertEqual(self.app.data, before)

    def test_invalid_pending_edits_block_export(self):
        editor = self.editor('ptset')
        with patch.object(editor, 'commit_inline', return_value=False):
            self.assertIsNone(open_export(editor))
        editor.def_name.set('')
        self.assertIsNone(open_export(editor))

    def test_unsupported_type_reports_error_before_save_dialog(self):
        editor = self.editor('gmset')
        editor.definition()['elements'][0]['type'] = 'legacy-cylinder'
        with patch('catalog_studio.macro_export_ui.messagebox.showerror') as error, patch('catalog_studio.macro_export_ui.filedialog.asksaveasfilename') as picker:
            self.assertIsNone(open_export(editor))
        error.assert_called_once(); picker.assert_not_called()

    def test_unencodable_text_shows_error_and_retains_preview_and_file(self):
        editor = self.editor('ptset')
        editor.definition()['attrs']['DESC'] = '説明😀'
        window = open_export(editor); self.app.update()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'export.mac'; path.write_bytes(b'original')
            with patch('catalog_studio.macro_export_ui.filedialog.asksaveasfilename', return_value=str(path)), patch('catalog_studio.macro_export_ui.messagebox.showerror') as error:
                window.save_button.invoke(); self.app.update()
            error.assert_called_once()
            self.assertIn('CP932', error.call_args.args[1])
            self.assertEqual(path.read_bytes(), b'original')
            self.assertTrue(window.winfo_exists())
        window.destroy()
        self.assertEqual(self.errors, [])
