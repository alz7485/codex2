import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from catalog_studio import preview_colors as colors,preview_preferences as prefs

class ColorTests(unittest.TestCase):
    def test_old_defaults_and_bad_color(self):
        old=copy.deepcopy(prefs.FACTORY);old.pop('colors')
        self.assertEqual(prefs.normalize(old)['colors'],colors.DEFAULTS)
        for value in ('red','#fff','wrong',None):
            with self.assertRaises(ValueError):colors.normalize({'model':value})

    def test_picker_render_defaults_and_restart(self):
        from catalog_studio.integrated import IntegratedStudio
        with tempfile.TemporaryDirectory() as directory,patch.object(prefs,'settings_path',return_value=Path(directory)/'prefs.json'):
            try:app=IntegratedStudio()
            except tk.TclError as exc:self.skipTest(str(exc))
            try:
                app.update();before=copy.deepcopy(app.data)
                point=app.geometry_editor.point_canvas
                with patch.object(colors.colorchooser,'askcolor',return_value=(None,None)):
                    colors.choose(point,'background')
                self.assertEqual(point.colors['background'].get(),colors.DEFAULTS['background'])
                with patch.object(colors.colorchooser,'askcolor',return_value=((255,255,255),'#ffffff')):
                    colors.choose(point,'background')
                self.assertEqual(point.canvas.cget('background'),'#ffffff')
                app.switch('gmset');app.update();view=app.geometry_editor.geometry_view
                self.assertEqual(view.canvas.cget('background'),'#ffffff')
                selected=copy.deepcopy(colors.DEFAULTS)
                selected.update(model='#ff9900',grid='#abcdef',points='#123456',dimension='#aabbcc',background='#ffffff')
                colors.apply(view,selected);view.redraw();app.update()
                self.assertEqual(view.color_swatches['model'].cget('background'),'#ff9900')
                self.assertTrue(prefs.save_current(view))
                self.assertEqual(prefs.load()[0]['colors'],selected)
                self.assertEqual(app.data,before)
                app.switch('catalog');app.update()
                self.assertEqual(app.preview.colors['model'].get(),'#ff9900')
            finally:app.destroy()
            app=IntegratedStudio()
            try:
                app.update();self.assertEqual(app.geometry_editor.point_canvas.canvas.cget('background'),'#ffffff')
                app.switch('gmset');app.update();self.assertEqual(app.geometry_editor.geometry_view.colors['model'].get(),'#ff9900')
            finally:app.destroy()
