import tkinter as tk
from tkinter import ttk
import unittest

class ToneTests(unittest.TestCase):
    def test_shared_actions_tables_and_sdte_search(self):
        from catalog_studio.integrated import IntegratedStudio
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        try:
            errors=[]
            app.report_callback_exception=lambda kind,value,tb:errors.append(str(value))
            style=ttk.Style(app)
            self.assertEqual(style.lookup('TButton','background'),'#eaf1ff')
            app.switch('specs');app.update()
            self.assertEqual(style.lookup('Spec.Treeview','rowheight'),26)
            self.assertTrue(app.spec_table.rules.lines)
            app.switch('books');app.update()
            self.assertTrue(app.books_table.rules.lines)
            app.switch('sdte_cmpt');app.update()
            editor=app.sdte_cmpt_editor
            editor.add('SDTE');app.update()
            ident=editor.tree.selection()[0]
            editor.search.set('no-match-123');app.update()
            self.assertEqual(editor.tree.get_children('catalog_details'),())
            editor.refresh();app.update()
            editor.search.set('');app.update()
            self.assertTrue(editor.tree.exists(ident))
            self.assertIn(ident,editor.tree.get_children('catalog_details'))
            editor.add('CMPT');editor.add('CMPDATA');app.update()
            child=editor.tree.selection()[0]
            editor.search.set(editor.tree.item(child,'text'));app.update()
            self.assertTrue(editor.tree.bbox(child))
            self.assertFalse(errors,errors)
        finally:app.destroy()
