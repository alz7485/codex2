import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from catalog_studio import project, presets, booklet, element_schema, expressions
from catalog_studio.integrated import IntegratedStudio


class PresetTests(unittest.TestCase):
    def setUp(self):self.data=project.sample()
    def profile(self,name='過去登録・レデューサー'):
        profile=presets.add(self.data,name);profile.update(period='旧登録',component='レデューサー',description='自作テストの規則')
        return profile
    def bind_all(self,profile):
        for collection in ('scoms','definitions'):
            for record in self.data[collection]:presets.bind(self.data,record,profile['id'])
    def test_active_selection_never_changes_existing_labels_values_or_expressions(self):
        original=copy.deepcopy(self.data);profile=self.profile()
        profile['parameters'][0]['role']='別コンポーネント径'
        self.data['active_parameter_preset_id']=profile['id']
        self.assertEqual(presets.rules(self.data)[0]['role'],'別コンポーネント径')
        self.assertEqual(presets.rules(self.data,self.data['scoms'][0])[0]['role'],'大径側外径')
        self.assertEqual(self.data['scoms'],original['scoms']);self.assertEqual(self.data['definitions'],original['definitions'])
    def test_per_scom_types_description_and_extra_values_survive_roundtrip(self):
        profile=self.profile();profile['parameters'][0].update(role='接続コード',description='この番号の日本語説明',unit='',value_type='word')
        scom=project.add_scom(self.data);scom['values']={'P1':'BW','P99':77}
        presets.bind(self.data,scom,profile['id']);project.validate(self.data)
        self.assertEqual(scom['values'],{'P1':'BW','P99':77})
        self.assertEqual(presets.rules(self.data,scom)[0]['description'],'この番号の日本語説明')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'data.json';project.save(self.data,path);self.assertEqual(project.load(path),self.data)
    def test_failed_assignment_is_atomic_and_never_converts_values(self):
        profile=self.profile();profile['parameters'][0]['value_type']='word';scom=self.data['scoms'][0];original=copy.deepcopy(scom)
        with self.assertRaises(ValueError):presets.bind(self.data,scom,profile['id'])
        self.assertEqual(scom,original)
    def test_rebinding_swapped_role_names_keeps_number_semantics(self):
        profile=self.profile();profile['parameters'][0]['role']='小径側外径';profile['parameters'][1]['role']='大径側外径'
        definition=self.data['definitions'][0];before=copy.deepcopy(definition['elements'])
        presets.bind(self.data,definition,profile['id'])
        self.assertEqual(definition['elements'][0]['attrs']['大径'],'P1')
        self.assertEqual(definition['elements'][0]['attrs']['小径'],'P2')
        self.assertEqual(definition['parameter_preset_history'][0]['elements'],before)
    def test_rename_is_scoped_to_one_preset_and_frozen_books_do_not_change(self):
        profile=self.profile();self.bind_all(profile);book=booklet.snapshot(self.data);frozen=copy.deepcopy(book)
        other=copy.deepcopy(self.data['definitions'][0]);other.update(id='other',name='/OTHER',parameter_preset_id='')
        other['elements'][0]['attrs']['大径']='大径側外径';self.data['definitions'].append(other)
        self.data['definitions'][0]['elements'][0]['attrs']['大径']='大径側外径'
        presets.rename(self.data,'P1','胴部径',profile['id'])
        self.assertEqual(self.data['definitions'][0]['elements'][0]['attrs']['大径'],'胴部径')
        self.assertEqual(other['elements'][0]['attrs']['大径'],'大径側外径');self.assertEqual(book,frozen)
        self.assertEqual(self.data['parameters'][0]['role'],'大径側外径')
    def test_mismatch_missing_preset_and_used_delete_are_explicit(self):
        profile=self.profile();presets.bind(self.data,self.data['scoms'][0],profile['id'])
        problems='\n'.join(project.issues(self.data));self.assertIn('プリセットが異なります',problems)
        with self.assertRaises(ValueError):presets.remove(self.data,profile['id'])
        del self.data['parameter_presets'][0]
        self.assertEqual(presets.rules(self.data,self.data['scoms'][0]),[])
        self.assertIn('プリセットが見つかりません','\n'.join(project.issues(self.data)))
        with self.assertRaises(ValueError):booklet.snapshot(self.data)
    def test_clone_is_independent_and_new_records_use_selected_preset(self):
        profile=self.profile();second=presets.add(self.data,'現在登録・レデューサー',profile['id'])
        second['parameters'][0]['role']='現在の径';second['parameters'][2]['role']='胴部長さ';self.assertEqual(profile['parameters'][0]['role'],'大径側外径')
        self.data['active_parameter_preset_id']=second['id']
        definition=project.add_definition(self.data,'GMSET');self.assertEqual(presets.selected_id(self.data,definition),second['id'])
        pointset=project.add_definition(self.data,'PTSET');self.assertEqual(pointset['elements'][1]['attrs']['位置'],'胴部長さ')
        scom=project.add_scom(self.data);self.assertEqual(presets.selected_id(self.data,scom),second['id']);self.assertEqual(scom['gmset_id'],definition['id'])
    def test_old_projects_and_books_keep_the_legacy_dictionary(self):
        original=copy.deepcopy(self.data);book=booklet.snapshot(self.data)
        profile=self.profile();self.data['active_parameter_preset_id']=profile['id']
        self.assertEqual(project.parameters_for(self.data,self.data['scoms'][0]),project.parameters_for(original,original['scoms'][0]))
        self.data['books']=[book];project.validate(self.data)
    def test_mixed_preset_pdf_has_separate_headers_and_frozen_explanations(self):
        try:from pypdf import PdfReader
        except ImportError:self.skipTest('pypdf required')
        profile=self.profile();profile['parameters'][0].update(role='旧胴部外径',description='旧登録の日本語説明')
        presets.bind(self.data,self.data['scoms'][0],profile['id'])
        for definition in self.data['definitions']:presets.bind(self.data,definition,profile['id'])
        book=booklet.snapshot(self.data);profile['parameters'][0]['description']='変更後の説明'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'book.pdf';booklet.generate_pdf(book,path)
            content='\n'.join(page.extract_text() for page in PdfReader(path).pages)
            for text in ('過去登録・レデューサー','旧胴部外径','旧登録の日本語説明','既存規則（従来データ）','プリセットが異なります'):self.assertIn(text,content)
            self.assertNotIn('変更後の説明',content)
    def test_preset_validation_rejects_bad_ids_duplicates_and_embedded_values(self):
        profile=self.profile();profile['parameters'][0]['value']=3
        with self.assertRaises(ValueError):project.validate(self.data)
        del profile['parameters'][0]['value'];self.data['parameter_presets'].append(copy.deepcopy(profile))
        with self.assertRaises(ValueError):project.validate(self.data)


class PresetGuiTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.update()
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def test_preset_management_and_current_default_dont_relabel_old_scom(self):
        app=self.app;profile=presets.add(app.data,'現在登録');profile['parameters'][0].update(role='胴部径',description='日本語の詳細説明')
        old=copy.deepcopy(app.data['scoms'][0]);app.switch('rules');app.update();editor=app.preset_editor
        editor.list.selection_set('preset:'+profile['id']);app.update()
        self.assertEqual(presets.selected_id(app.data),profile['id']);self.assertEqual(app.data['scoms'][0],old)
        self.assertIn('日本語の詳細説明',app.preset_editor.table.item('P1','values'))
        app.switch('catalog');app.update();self.assertIn('大径側外径',app.scom_detail.cget('text'));self.assertNotIn('胴部径',app.scom_detail.cget('text'))
        self.assertEqual(self.errors,[])
    def test_definition_assignment_and_role_label_paste_binding(self):
        app=self.app;profile=presets.add(app.data,'コンポーネント専用');profile['parameters'][0].update(role='部品の外径',description='部品専用の日本語説明')
        editor=app.geometry_editor;editor.refresh();editor.preset_choice.set(profile['name']);editor.assign_preset();app.update()
        editor.ref_kind.set('PARAM');editor.ref_number.set('1');editor.update_role()
        self.assertIn('部品専用の日本語説明',editor.role_label.cget('text'))
        editor.field='PDIS';editor.busy=True;editor.load_field();editor.busy=False
        self.assertIn('プリセットが異なります',editor.validation_note.cget('text'))
        scom=app.data['scoms'][0];presets.bind(app.data,scom,profile['id']);app.scom_id=scom['id']
        app.data['active_parameter_preset_id']=''
        candidate=app.parse_scom_paste('/PASTED-PRESET\t65x40\t76\t48\t100\t65\t40')
        self.assertEqual(presets.selected_id(candidate,candidate['scoms'][-1]),profile['id']);self.assertEqual(self.errors,[])
    def test_scom_edit_and_parameter_edit_are_bound_to_their_own_dictionary(self):
        app=self.app;profile=presets.add(app.data,'WORD 用');profile['parameters'][0].update(role='接続コード',unit='',value_type='word')
        scom=project.add_scom(app.data);scom['values']={'P1':'BW'};presets.bind(app.data,scom,profile['id'])
        def accept(title,fields,apply):
            values={k:str(initial) for k,_,initial,_ in fields}
            self.assertEqual(values['P1'],'BW');apply(values)
        with patch.object(app,'form',side_effect=accept):app.scom_form(scom)
        self.assertEqual(scom['values']['P1'],'BW')
        app.data['active_parameter_preset_id']=profile['id'];app.switch('rules');app.update()
        parameter=profile['parameters'][0]
        def rename(title,fields,apply):apply({k:('新しい説明' if k=='description' else str(initial)) for k,_,initial,_ in fields})
        with patch.object(app,'form',side_effect=rename):app.preset_editor.parameter_form(parameter)
        self.assertEqual(parameter['description'],'新しい説明');self.assertEqual(app.data['parameters'][0]['role'],'大径側外径');self.assertEqual(self.errors,[])
