import copy
import tkinter as tk
import unittest
from catalog_studio.integrated import IntegratedStudio


class ValveSampleGuiTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.update()

    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()

    def test_startup_samples_can_be_selected_in_both_registered_lists(self):
        records=[r for r in self.app.data['definitions'] if r.get('sample')=='manual-valve']
        self.assertEqual(len(records),2)
        for record in records:
            self.app.switch(record['kind'].lower());self.app.update()
            tree=self.app.registered_browser.tree;key='definitions:'+record['id']
            self.assertTrue(tree.exists(key))
            tree.selection_set(key);tree.event_generate('<<TreeviewSelect>>');self.app.update()
            self.assertEqual(self.app.geometry_editor.definition()['id'],record['id'])
            self.assertEqual(len(self.app.geometry_editor.elements.get_children()),3 if record['kind']=='PTSET' else 7)
        self.assertEqual(self.errors,[])

    def test_add_sample_keeps_existing_records_and_selects_new_pair(self):
        before=copy.deepcopy(self.app.data)
        self.app.add_valve_sample();self.app.update()
        self.assertEqual(self.app.page,'gmset');self.assertTrue(self.app.dirty)
        for key in ('definitions','cates','scoms','parameter_presets'):
            self.assertEqual(self.app.data[key][:len(before.get(key,[]))],before.get(key,[]))
        gm=self.app.geometry_editor.definition()
        self.assertEqual(gm['sample'],'manual-valve')
        self.assertTrue(gm['name'].endswith('-2'))
        self.assertEqual(self.app.geometry_editor.preview_scom_id,self.app.scom_id)
        self.assertEqual(self.errors,[])
