import copy
import tkinter as tk
from tkinter import ttk
import unittest
from catalog_studio.integrated import IntegratedStudio

class SetCreationDialogTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.app.update()
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def descendants(self,w):
        for child in w.winfo_children():
            yield child
            yield from self.descendants(child)
    def submit(self,kind,name='',preset=''):
        win=self.app.set_creation_dialog(kind);self.app.update()
        widgets=list(self.descendants(win))
        entry=next(w for w in widgets if isinstance(w,ttk.Entry) and not isinstance(w,ttk.Combobox))
        entry.insert(0,name)
        next(w for w in widgets if isinstance(w,ttk.Combobox)).set(preset)
        next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')=='作成').invoke()
        self.app.update();return win
    def test_blank_and_named_presets_for_both_kinds(self):
        for kind in ('PTSET','GMSET'):
            count=len(self.app.data['definitions'])
            self.submit(kind)
            self.assertEqual(len(self.app.data['definitions']),count+1)
            record=self.app.definition()
            self.assertEqual(record['elements'],[]);self.assertEqual(record['kind'],kind)
            self.assertTrue(record['name'].startswith('新しいアイテム'))
            self.submit(kind,'/CUSTOM-'+kind,'標準 BEND')
            record=self.app.definition()
            self.assertEqual(record['name'],'/CUSTOM-'+kind)
            self.assertEqual(len(record['elements']),2)
            self.assertEqual(record['parameter_preset_id'],'builtin-piping-param-bend')
    def test_cancel_and_duplicate_do_not_mutate(self):
        before=copy.deepcopy(self.app.data)
        win=self.app.set_creation_dialog('PTSET');win.destroy()
        self.assertEqual(self.app.data,before)
        win=self.submit('PTSET',self.app.data['definitions'][0]['name'])
        self.assertTrue(win.winfo_exists());self.assertEqual(self.app.data,before)
    def test_kind_filter(self):
        win=self.app.set_creation_dialog('GMSET')
        choice=next(w for w in self.descendants(win) if isinstance(w,ttk.Combobox))
        self.assertEqual(tuple(choice['values']),('','標準 BEND'))
