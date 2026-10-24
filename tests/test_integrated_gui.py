import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from catalog_studio.integrated import IntegratedStudio,PAGES
from catalog_studio import project

class IntegratedGuiTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest('GUI display unavailable: '+str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.update()
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def test_pages_expression_spec_link_and_empty_project(self):
        app=self.app
        for page,_ in PAGES:app.switch(page);app.update()
        app.definition_id=app.data['definitions'][0]['id'];app.switch('definitions');app.field='長さ';app.populate_attrs();app.update()
        app.formula.set('全長 / 2 + 3');app.update()
        self.assertIn('47.5',app.formula_result.cget('text'))
        app.formula.set('全長 / 0');app.update();self.assertIn('ゼロ',app.formula_result.cget('text'))
        app.switch('specs');app.update();app.goto_spec_scom();app.update()
        self.assertEqual(app.page,'catalog')
        for key in ('cates','scoms','definitions','specs','books'):app.data[key]=[]
        app.reset_selection()
        for page,_ in PAGES:app.switch(page);app.update()
        self.assertEqual(self.errors,[])
    def test_paste_is_atomic_and_shared_definitions_not_values(self):
        app=self.app;before=copy.deepcopy(app.data)
        candidate=app.parse_scom_paste('/PASTED\t65x40\t76.3\t48.6\t102\t65\t40')
        self.assertEqual(len(candidate['scoms']),len(before['scoms'])+1);self.assertEqual(app.data,before)
        self.assertEqual(candidate['definitions'],before['definitions'])
        with self.assertRaises(ValueError):app.parse_scom_paste('/OK\t65x40\t76.3\t48.6\t102\t65\t40\n/BAD\tbad')
        self.assertEqual(app.data,before)
    def test_unknown_element_readonly_and_cate_follows_preview_scom(self):
        app=self.app;definition=app.data['definitions'][0]
        definition['elements'].append({'id':'future','type':'future','name':'原文','attrs':{'RAW':'未知の式'}})
        app.definition_id=definition['id'];app.switch('definitions');app.update();app.element_table.selection_set('future');app.update()
        self.assertEqual(str(app.formula_entry.cget('state')),'readonly')
        self.assertIn('未対応',app.preview.message)
        newcate=project.add_cate(app.data)
        newscom=project.duplicate_scom(app.data,app.data['scoms'][0]);newscom['cate_id']=newcate['id'];app.scom_id=newscom['id']
        app.switch('catalog');app.update()
        self.assertEqual(app.cate_id,newcate['id']);self.assertTrue(app.scom_table.exists(newscom['id']))
        self.assertEqual(self.errors,[])
    def test_edit_preserves_unknown_values_and_unresolved_refs(self):
        app=self.app;scom=app.data['scoms'][0]
        scom.update(cate_id='missing-cate',gmset_id='missing-gm',ptset_id='');scom['values']['P99']=123
        def accept(title,fields,apply):apply({k:str(v) for k,label,v,choices in fields})
        with patch.object(app,'form',side_effect=accept):app.scom_form(scom)
        self.assertEqual(scom['cate_id'],'missing-cate');self.assertEqual(scom['gmset_id'],'missing-gm');self.assertEqual(scom['ptset_id'],'')
        self.assertEqual(scom['values']['P99'],123)
    def test_snapshot_save_and_reopen(self):
        app=self.app;app.switch('books');app.update();app.create_book();app.update()
        frozen=copy.deepcopy(app.data['books'][0]);app.data['scoms'][0]['values']['P1']=999
        self.assertEqual(app.data['books'][0],frozen)
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/'project.json')
            with patch('catalog_studio.integrated.filedialog.asksaveasfilename',return_value=path):self.assertTrue(app.save_project())
            with patch('catalog_studio.integrated.filedialog.askopenfilename',return_value=path):app.open_project()
            self.assertEqual(app.data['books'][0],frozen)
        self.assertEqual(self.errors,[])
