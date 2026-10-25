import copy
import tkinter as tk
import unittest
from catalog_studio.integrated import IntegratedStudio


class PreviewControlsTests(unittest.TestCase):
    def test_focus_panel_zoom_and_fit_preserve_project(self):
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        errors=[];app.report_callback_exception=lambda k,v,t:errors.append(str(v))
        try:
            for kind in ('PTSET','GMSET'):
                app.definition_id=next(d['id'] for d in app.data['definitions'] if d.get('sample')=='manual-valve' and d['kind']==kind)
                app.switch(kind.lower());app.update()
                v=app.geometry_editor.point_canvas if kind=='PTSET' else app.geometry_editor.geometry_view
                before=copy.deepcopy(app.data)
                v.view_buttons['XZ'].invoke();app.update()
                if kind=='PTSET':
                    v.plane.set('YZ');v.plane_changed();self.assertEqual(v.view.get(),'XZ')
                v.zoom(1.4);v.fit_button.invoke();app.update()
                if kind=='GMSET':self.assertEqual(v.zoom_factor,1)
                for point in (v.positions.values() if kind=='PTSET' else v.scene.vertices()):
                    x,y=v.camera.project(point,v.canvas.winfo_width(),v.canvas.winfo_height())
                    self.assertTrue(0<=x<=v.canvas.winfo_width() and 0<=y<=v.canvas.winfo_height())
                v.focus_button.invoke();app.update();self.assertEqual(len(app.geometry_editor.main_split.panes()),1)
                v.focus_button.invoke();app.update();self.assertEqual(len(app.geometry_editor.main_split.panes()),3)
                v.open_details();app.update();self.assertTrue(v.details.winfo_viewable())
                v.close_details();app.update();self.assertFalse(v.details.winfo_viewable())
                self.assertEqual(app.data,before)
            self.assertEqual(errors,[])
        finally:app.destroy()
