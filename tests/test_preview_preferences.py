import copy
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from catalog_studio import preview_preferences as prefs
from catalog_studio.integrated import IntegratedStudio


class PreferenceStorageTests(unittest.TestCase):
    def test_roundtrip_bad_file_and_failed_replace_preserve_previous_defaults(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(prefs,'settings_path',return_value=Path(directory)/'prefs.json'):
            value=copy.deepcopy(prefs.FACTORY);value['geometry']['transparency']=42;prefs.save(value)
            self.assertEqual(prefs.load()[0],value)
            previous=prefs.settings_path().read_bytes()
            with patch.object(prefs.os,'replace',side_effect=OSError('unavailable')):
                with self.assertRaises(OSError):prefs.save(prefs.FACTORY)
            self.assertEqual(prefs.settings_path().read_bytes(),previous)
            prefs.settings_path().write_text('{bad',encoding='utf-8')
            loaded,error=prefs.load();self.assertEqual(loaded,prefs.FACTORY);self.assertTrue(error)
            with self.assertRaises(ValueError):prefs.normalize(dict(version=1,shared={'show_grid':'false'}))
            with self.assertRaises(ValueError):prefs.normalize(dict(version=1,geometry={'transparency':float('nan')}))


class PreferenceGuiTests(unittest.TestCase):
    def test_button_applies_to_all_sets_and_restart_without_project_changes(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(prefs,'settings_path',return_value=Path(directory)/'prefs.json'):
            apps=[]
            try:
                try:app=IntegratedStudio();apps.append(app)
                except tk.TclError as exc:self.skipTest(str(exc))
                app.update();before=copy.deepcopy(app.data);dirty=app.dirty
                point=app.geometry_editor.point_canvas
                point.show_grid.set(False);point.show_labels.set(False);point.show_relations.set(False)
                point.defaults_button.invoke();app.update()
                app.switch('gmset');app.update();g=app.geometry_editor.geometry_view
                self.assertFalse(g.show_grid.get());self.assertFalse(g.show_labels.get())
                g.render_mode.set('面＋線');g.transparency.set(44);g.show_negative.set(False)
                g.rep_options.update(tube=False,cl=True,level=3);g.representation_mode.set('属性確認')
                g.defaults_button.invoke();app.update()
                app.definition_id=next(d['id'] for d in app.data['definitions'] if d.get('sample')=='manual-valve' and d['kind']=='GMSET')
                app.render_page();app.update();g=app.geometry_editor.geometry_view
                self.assertEqual(g.transparency.get(),44);self.assertFalse(g.show_negative.get())
                self.assertEqual(g.rep_options['level'],3)
                self.assertEqual(app.data,before);self.assertEqual(app.dirty,dirty)
                app.destroy();apps.remove(app)
                app=IntegratedStudio();apps.append(app);app.update()
                self.assertFalse(app.geometry_editor.point_canvas.show_relations.get())
                app.switch('gmset');app.update();g=app.geometry_editor.geometry_view
                self.assertEqual(g.render_mode.get(),'面＋線');self.assertEqual(g.transparency.get(),44)
                self.assertFalse(g.show_grid.get());self.assertFalse(g.show_labels.get())
                g.transparency.set(12);g.display_changed(immediate=True)
                app.switch('ptset');app.update();app.geometry_editor.point_canvas.defaults_button.invoke();app.update()
                app.switch('gmset');app.update();g=app.geometry_editor.geometry_view
                self.assertEqual(g.transparency.get(),44)
                previous=copy.deepcopy(app._preview_defaults);g.show_grid.set(True)
                with patch.object(prefs,'save',side_effect=OSError('denied')):
                    g.defaults_button.invoke();app.update()
                self.assertEqual(app._preview_defaults,previous)
                self.assertIn('保存できません',g.defaults_notice['text'])
            finally:
                for app in apps:app.destroy()
