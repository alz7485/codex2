import unittest
from unittest.mock import patch
import tkinter as tk
from catalog_studio.app import Studio

class GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = Studio()
        except tk.TclError as exc:
            self.skipTest('GUI display unavailable: ' + str(exc))
        self.errors=[]
        self.app.report_callback_exception=lambda kind,value,tb:self.errors.append(str(value))
        self.app.update()
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def test_edit_and_structure(self):
        app=self.app
        app.expr.set('全長 / 2 + 5');app.update()
        self.assertIn('65',app.result.cget('text'))
        app.expr.set('全長 / 0');app.update()
        self.assertIn('ゼロ',app.result.cget('text'))
        app.expr.set('全長 / 2')
        app.add('cylinder');app.duplicate();app.update()
        self.assertEqual(len(app.project['elements']),5)
        with patch('catalog_studio.app.messagebox.askyesno',return_value=True):app.delete()
        app.update()
        self.assertEqual(len(app.project['elements']),4)
        app.selected='shape1';app.field='位置';app.refresh();app.change_value('P3','200');app.update()
        self.assertIn('100',app.result.cget('text'))
        self.assertGreater(len(app.canvas.find_all()),20)
        self.assertEqual(self.errors,[])
