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
    def submit(self,kind,name='',preset='',pointset=''):
        win=self.app.set_creation_dialog(kind);self.app.update()
        widgets=list(self.descendants(win))
        entry=next(w for w in widgets if isinstance(w,ttk.Entry) and not isinstance(w,ttk.Combobox))
        entry.insert(0,name)
        choices=[w for w in widgets if isinstance(w,ttk.Combobox)]
        choices[0].set(preset)
        if kind=='GMSET':choices[1].set(pointset)
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

    def test_pointset_binding_and_parameter_inheritance(self):
        point=next(d for d in self.app.data['definitions'] if d['kind']=='PTSET')
        self.submit('GMSET','/PAIRED',pointset=point['name'])
        record=self.app.definition()
        self.assertEqual(record['paired_ptset_id'],point['id'])
        self.assertEqual(record['parameter_preset_id'],point.get('parameter_preset_id',''))
        self.assertEqual(self.app.data['creation_draft'],{'ptset_id':point['id'],'gmset_id':record['id']})
        self.submit('PTSET','/BEND-POINT','標準 BEND')
        point=self.app.definition()
        self.submit('GMSET','/BEND-GEOMETRY','標準 BEND',point['name'])
        self.assertEqual(self.app.definition()['paired_ptset_id'],point['id'])
        self.assertEqual(len(self.app.definition()['elements']),2)

    def test_incompatible_parameter_presets_are_atomic(self):
        point=next(d for d in self.app.data['definitions'] if d['kind']=='PTSET')
        before=copy.deepcopy(self.app.data)
        win=self.submit('GMSET','/INCOMPATIBLE','標準 BEND',point['name'])
        self.assertTrue(win.winfo_exists());self.assertEqual(self.app.data,before)

    def test_select_pointset_by_name_button(self):
        point=next(d for d in self.app.data['definitions'] if d['kind']=='PTSET')
        point['name']='/PT-SAMPLE'
        win=self.app.set_creation_dialog('GMSET');self.app.update()
        widgets=list(self.descendants(win))
        entry=next(w for w in widgets if isinstance(w,ttk.Entry) and not isinstance(w,ttk.Combobox))
        choice=[w for w in widgets if isinstance(w,ttk.Combobox)][1]
        button=next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')=='名称からPTSETを選択')
        entry.insert(0,'/GM-SAMPLE');button.invoke()
        self.assertEqual(choice.get(),'/PT-SAMPLE')
        for name in ('GM-NOTFOUND','WRONG','GM-'):
            entry.delete(0,'end');entry.insert(0,name);button.invoke()
            self.assertEqual(choice.get(),'/PT-SAMPLE')
        entry.delete(0,'end');entry.insert(0,'GM-SAMPLE');button.invoke()
        next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')=='作成').invoke()
        self.app.update()
        self.assertEqual(self.app.definition()['paired_ptset_id'],point['id'])

    def test_name_from_selected_pointset(self):
        point=next(d for d in self.app.data['definitions'] if d['kind']=='PTSET')
        point['name']='/PT-REVERSE'
        win=self.app.set_creation_dialog('GMSET');self.app.update()
        widgets=list(self.descendants(win))
        entry=next(w for w in widgets if isinstance(w,ttk.Entry) and not isinstance(w,ttk.Combobox))
        choice=[w for w in widgets if isinstance(w,ttk.Combobox)][1]
        button=next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')=='PTSETから名称を入力')
        entry.insert(0,'existing');button.invoke()
        self.assertEqual(entry.get(),'existing')
        choice.set(point['name']);button.invoke()
        self.assertEqual(entry.get(),'/GM-REVERSE')
