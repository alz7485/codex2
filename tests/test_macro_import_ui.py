import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from catalog_studio import presets, project
from catalog_studio.integrated import IntegratedStudio

SAMPLE = Path(__file__).resolve().parents[1]/'examples'/'creation-import-sample.mac'


class MacroImportGuiTests(unittest.TestCase):
    def test_alp_file_import_then_export_keeps_formulas_points_and_locks(self):
        from catalog_studio import macro_import
        from catalog_studio.macro_export_ui import open_export
        window = self.dialog(SAMPLE.with_name('alp-creation-sample.mac').read_text())
        self.assertIn('出力時のロック：あり', window.details.get('1.0', 'end'))
        window.apply_button.invoke(); self.app.update()
        editor = self.app.geometry_editor
        self.assertEqual(editor.definition()['kind'], 'GMSET')
        preview = open_export(editor); self.app.update()
        self.assertNotIn('INPUT BEGIN', preview.source.get('1.0', 'end'))
        preview.lock_button.invoke(); self.app.update()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'alp.mac'
            with patch('catalog_studio.macro_export_ui.filedialog.asksaveasfilename', return_value=str(path)):
                preview.save_button.invoke(); self.app.update()
            text, _ = macro_import.read_text(path)
            record = macro_import.parse(text).definitions[0]
        self.assertEqual(record['elements'][2]['attrs']['PTS'], 'P1 P3')
        self.assertEqual(record['elements'][0]['attrs']['PDIA'], 'SUM PARAM 2 IPARAM 1')
        self.assertTrue(all(e['macro_locked'] for e in record['elements']))
        self.assertEqual(self.errors, [])

    def setUp(self):
        try: self.app = IntegratedStudio()
        except tk.TclError as exc: self.skipTest('GUI display unavailable: ' + str(exc))
        self.errors = []
        self.app.report_callback_exception = lambda k, v, t: self.errors.append(str(v))
        self.app.update()

    def tearDown(self):
        if hasattr(self, 'app'): self.app.destroy()

    def dialog(self, text=None):
        window = self.app.import_creation_macro()
        self.app.update()
        if text is not None:
            window.source.insert('1.0', text)
            self.app.update(); window.analyze(); self.app.update()
        return window

    def test_visible_button_preview_and_cancel_do_not_modify_data(self):
        app = self.app
        self.assertTrue(app.geometry_editor.import_macro_button.winfo_ismapped())
        before = copy.deepcopy(app.data); dirty = app.dirty
        window = self.dialog(SAMPLE.read_text())
        self.assertEqual(len(window.records.get_children()), 2)
        self.assertEqual(len(window.records.selection()), 2)
        self.assertIn('(-PARA[3])', window.details.get('1.0','end'))
        self.assertEqual(app.data, before); self.assertEqual(app.dirty, dirty)
        window.destroy(); app.update()
        self.assertEqual(app.data, before)
        self.assertEqual(self.errors, [])

    def test_confirm_button_and_preview_remain_visible_at_minimum_size(self):
        window = self.dialog(SAMPLE.read_text())
        for geometry in ('920x760', '680x640'):
            window.geometry(geometry); self.app.update()
            bottom = window.apply_button.winfo_rooty() + window.apply_button.winfo_height()
            self.assertLessEqual(bottom, window.winfo_rooty() + window.winfo_height())
            self.assertTrue(window.apply_button.winfo_viewable())
            self.assertGreater(window.details.winfo_height(), 40)
            self.assertGreater(window.source.winfo_height(), 40)
        window.destroy()
        self.assertEqual(self.errors, [])

    def test_file_import_subset_and_save_reload(self):
        app = self.app; app.switch('gmset'); app.update()
        before = copy.deepcopy(app.data)
        with tempfile.TemporaryDirectory() as folder:
            saved = Path(folder)/'project.json'; app.path = str(saved)
            window = self.dialog()
            with patch('catalog_studio.macro_import_ui.filedialog.askopenfilename', return_value=str(SAMPLE)):
                window.file_button.invoke()
            app.update()
            gm = next(record for record in window.parsed.definitions if record['kind'] == 'GMSET')
            window.records.selection_set(gm['id']); app.update()
            window.apply_button.invoke(); app.update()
            self.assertFalse(window.winfo_exists())
            self.assertEqual(app.page, 'gmset')
            imported = app.geometry_editor.definition()
            self.assertEqual(imported['name'], '/DEMO-READ-SHAPES')
            self.assertEqual(imported['elements'][0]['attrs']['PHEI'], '(-PARA[3])')
            self.assertEqual(presets.rules(app.data, imported), [])
            self.assertEqual(app.data['definitions'][:-1], before['definitions'])
            self.assertEqual(app.data['scoms'], before['scoms'])
            self.assertEqual(app.path, str(saved)); self.assertTrue(app.dirty)
            self.assertTrue(app.save_project())
            self.assertEqual(project.load(saved), app.data)
        self.assertEqual(self.errors, [])

    def test_changed_source_cannot_import_old_preview(self):
        app = self.app; before = copy.deepcopy(app.data)
        window = self.dialog(SAMPLE.read_text())
        window.source.insert('end', '\nDELETE ALL\n')
        window.apply()
        self.assertEqual(app.data, before)
        app.update()
        self.assertIsNone(window.parsed)
        self.assertEqual(str(window.apply_button['state']), 'disabled')
        window.analyze(); app.update()
        self.assertIn('解析できません', window.notice.cget('text'))
        self.assertEqual(window.records.get_children(), ())
        self.assertEqual(app.data, before)
        window.destroy()
        self.assertEqual(self.errors, [])

    def test_empty_selection_and_duplicate_names(self):
        app = self.app; before = copy.deepcopy(app.data)
        text = 'NEW PTSET /REDUCER-GEOM\nNEW PTAX\nNUMB 1\n'
        window = self.dialog(text)
        window.records.selection_remove(*window.records.selection()); app.update()
        window.apply()
        self.assertEqual(app.data, before)
        self.assertEqual(str(window.apply_button['state']), 'disabled')
        window.records.selection_set(*window.records.get_children()); app.update()
        window.apply(); app.update()
        self.assertEqual(app.geometry_editor.definition()['name'], '/REDUCER-GEOM-IMPORT-2')
        self.assertEqual(app.data['definitions'][:-1], before['definitions'])
        self.assertIn('同名の1件', app.status.cget('text'))
        self.assertEqual(self.errors, [])

    def test_decode_failure_keeps_current_text_and_project(self):
        app = self.app; window = self.dialog(SAMPLE.read_text())
        before = copy.deepcopy(app.data); text = window.text()
        with patch('catalog_studio.macro_import_ui.filedialog.askopenfilename', return_value='bad.mac'), patch('catalog_studio.macro_import_ui.macro_import.read_text', side_effect=ValueError('文字コード不正')):
            window.open_file()
        self.assertEqual(window.text(), text)
        self.assertEqual(app.data, before)
        self.assertIn('ファイルを開けません', window.notice.cget('text'))
        window.destroy()
