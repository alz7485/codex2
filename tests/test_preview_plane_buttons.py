import copy
import tkinter as tk
import unittest
from catalog_studio.integrated import IntegratedStudio


class PlaneButtonTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.update();self.v=self.app.geometry_editor.point_canvas
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def f5(self):self.app.focus_force();self.app.event_generate('<F5>');self.app.update()

    def test_buttons_and_f5_cycle_plane_without_changing_view_or_project(self):
        before=copy.deepcopy(self.app.data);basis=self.v.camera.basis()
        for plane in ('XZ','YZ','XY'):
            self.f5();self.assertEqual(self.v.plane.get(),plane)
            self.assertEqual(self.v.camera.basis(),basis)
            self.assertTrue(self.v.plane_buttons[plane].instate(['selected']))
        self.v.plane_buttons['YZ'].invoke();self.app.update();self.assertEqual(self.v.plane.get(),'YZ')
        self.v.view_buttons['XZ'].invoke();self.app.update();self.assertEqual(self.v.view.get(),'XZ');self.assertEqual(self.v.plane.get(),'YZ')
        for buttons in (self.v.plane_buttons,self.v.view_buttons):
            for button in buttons.values():self.assertTrue(button['image']);self.assertEqual(str(button['compound']),'left')
        self.assertEqual(self.app.data,before);self.assertEqual(self.errors,[])

    def test_f5_is_not_duplicated_on_navigation_and_ignores_modal_dialog(self):
        for _ in range(3):self.app.switch('gmset');self.app.update();self.app.switch('ptset');self.app.update()
        self.v=self.app.geometry_editor.point_canvas;self.f5();self.assertEqual(self.v.plane.get(),'XZ')
        dialog=tk.Toplevel(self.app);dialog.grab_set();self.app.update()
        self.f5();self.assertEqual(self.v.plane.get(),'XZ');dialog.destroy()
        self.app.switch('gmset');self.app.update();self.assertFalse(self.app.bind('<F5>'))
        for b in self.app.geometry_editor.geometry_view.view_buttons.values():self.assertTrue(b['image'])
        self.assertEqual(self.errors,[])
