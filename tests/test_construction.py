import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from catalog_studio import element_schema as schema, project
from catalog_studio.integrated import IntegratedStudio

class SchemaTests(unittest.TestCase):
    def test_lists_and_hidden_defaults(self):
        self.assertEqual(len(schema.PT_TYPES),4);self.assertEqual(len(schema.GM_TYPES),18);self.assertEqual(len(schema.NEGATIVE_BASE),15)
        self.assertEqual(schema.fields('SCYL'),('PAXI','PHEI','PDIA','PDIS','TVISI','BVISI'))
        self.assertEqual(schema.fields('PTPOS'),('NUMB','PCON','PBOR','PTCPOS','PTCDIR'))
        for kind in schema.PT_TYPES:
            self.assertTrue(all(schema.default_attrs(kind)[k]=='unset' for k in schema.PT_DETAIL))
        self.assertEqual(schema.fields('NSRU'),());self.assertEqual(schema.fields('NSRU','negative'),schema.NEGATIVE_EXTRA)
    def test_alias_and_type_change_preserve_values(self):
        e={'id':'one','name':'点','type':'PTPOS','attrs':{'PTCD':'X45U','EXTRA':'原文'}}
        self.assertEqual(schema.value(e,'PTCDIR'),'X45U')
        schema.set_value(e,'PTCDIR','E');self.assertEqual(e['attrs']['PTCD'],'E');self.assertNotIn('PTCDIR',e['attrs'])
        schema.change_type(e,'PTCAR');self.assertEqual(e['attrs']['EXTRA'],'原文');self.assertEqual(e['attrs']['PTCD'],'E')
        self.assertEqual(e['type_history'][0]['type'],'PTPOS')
    def test_all_types_roundtrip(self):
        data=project.sample()
        for definition in schema.demo_definitions():
            definition['elements']=[]
            types=schema.PT_TYPES if definition['kind']=='PTSET' else list(schema.GM_TYPES)+list(schema.NEGATIVE_BASE)
            for kind in types:schema.add_element(definition,kind)
            data['definitions'].append(definition)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'schema.json';project.save(data,path);self.assertEqual(project.load(path),data)
    def test_numbering_and_category(self):
        definition=schema.demo_definitions()[0]
        e=schema.add_element(definition,'PTAXI');self.assertEqual(e['attrs']['NUMB'],'5')
        with self.assertRaises(ValueError):schema.add_element(definition,'SCYL')

class ConstructionGuiTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest('GUI display unavailable: '+str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.update()
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def select_field(self,editor,key):
        editor.tables[editor.section].selection_set(key);self.app.update()
    def test_ptset_fields_details_insert_and_type_switch(self):
        editor=self.app.geometry_editor
        self.assertEqual(self.app.page,'ptset')
        self.assertEqual(editor.element()['type'],'PTAXI')
        self.assertEqual(editor.tables['main'].get_children(),schema.fields('PTAXI'))
        self.assertNotIn('PSKEY',editor.tables['main'].get_children())
        self.select_field(editor,'PDIS');editor.expression.set('(para[1] * tan (angl / 2))');self.app.update()
        self.assertEqual(editor.element()['attrs']['PDIS'],'(para[1] * tan (angl / 2))')
        editor.expression.set('');editor.ref_kind.set('DES APARAM');editor.ref_number.set('3');editor.insert_reference();self.app.update()
        self.assertEqual(editor.element()['attrs']['PDIS'],'DES APARAM[3]')
        editor.tabs.select(1);self.app.update();self.assertEqual(editor.tables['detail'].get_children(),schema.PT_DETAIL)
        self.select_field(editor,'DESC');editor.expression.set('読み込み値を保持');self.app.update()
        self.assertEqual(editor.element()['attrs']['DESC'],'読み込み値を保持')
        editor.type_choice.set('PTCAR')
        with patch('catalog_studio.construction_ui.messagebox.askyesno',return_value=True):editor.change_type()
        self.app.update();self.assertIn('PX',editor.tables['main'].get_children());self.assertEqual(editor.element()['attrs']['DESC'],'読み込み値を保持')
        self.assertEqual(self.errors,[])
    def test_gmset_negative_common_and_duplicate(self):
        app=self.app;app.switch('gmset');app.update();editor=app.geometry_editor
        self.assertEqual(editor.element()['type'],'SCYL')
        self.assertEqual(editor.library.size(),18)
        editor.negative.set(True);editor.populate_library();self.assertEqual(editor.library.size(),15)
        index=list(schema.NEGATIVE_BASE).index('NSRU');editor.library.selection_clear(0,'end');editor.library.selection_set(index);editor.add_element();app.update()
        self.assertEqual(editor.element()['type'],'NSRU')
        editor.tabs.select(2);app.update();self.assertEqual(editor.tables['negative'].get_children(),schema.NEGATIVE_EXTRA)
        self.select_field(editor,'PJOI');editor.expression.set('/原文参照');app.update()
        editor.tabs.select(1);app.update();self.select_field(editor,'OBST');editor.expression.set('1：ソフト');app.update()
        self.assertEqual(editor.element()['attrs']['OBST'],'1');self.assertEqual(editor.element()['attrs']['PJOI'],'/原文参照')
        original=copy.deepcopy(editor.element());editor.duplicate_element();app.update()
        self.assertNotEqual(editor.element()['id'],original['id']);self.assertEqual(editor.element()['attrs'],original['attrs'])
        self.assertEqual(self.errors,[])
    def test_save_reload_after_field_and_name_edit(self):
        app=self.app;editor=app.geometry_editor
        self.select_field(editor,'PDIS');editor.expression.set('0.5 TIMES PARAM 13');editor.def_name.set('/NEW-POINTS')
        with tempfile.TemporaryDirectory() as folder:
            app.path=str(Path(folder)/'project.json');self.assertTrue(app.save_project())
            loaded=project.load(app.path);d=next(d for d in loaded['definitions'] if d['name']=='/NEW-POINTS')
            self.assertEqual(d['elements'][0]['attrs']['PDIS'],'0.5 TIMES PARAM 13')
        self.assertEqual(self.errors,[])
