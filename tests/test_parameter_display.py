import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from catalog_studio import presets, project
from catalog_studio.integrated import IntegratedStudio


class ParameterDisplayTests(unittest.TestCase):
    def setUp(self):
        self.data = project.sample()
        self.profile = presets.add(self.data, '部品 A の規則')
        next(p for p in self.profile['parameters'] if p['id'] == 'P3')['role'] = '面間距離'
        self.record = {'parameter_preset_id': self.profile['id']}

    def test_aliases_and_multiple_references_keep_the_source_spelling(self):
        text = '(attrib para[3] + 0.5 TIMES PARAM 1 + P3)'
        before = copy.deepcopy(self.data)
        result = presets.display_expression(self.data, self.record, text)
        self.assertEqual(result, '(attrib para[3]（面間距離） + 0.5 TIMES PARAM 1（大径側外径） + P3（面間距離）)')
        self.assertEqual(self.data, before)
        self.assertEqual(presets.expression_names(self.data,self.record,text),'PARAM 3 面間距離 / PARAM 1 大径側外径')
        self.assertEqual(presets.display_expression(self.data, self.record, 'PARAM 30'), 'PARAM 30（設定名未登録）')

    def test_other_reference_families_have_their_own_names(self):
        self.profile['reference_roles'] = {'IPARAM': {'P1': '断熱厚'}, 'DES PARAM': {'P3': '設計長さ'}, 'APARAM': {'P3': '取付先寸法'}}
        text = 'PARAM 3 + IPARAM 1 + DESP[3] + DES PARA[3] + APARA[3] + OPARAM 3'
        result = presets.display_expression(self.data, self.record, text)
        self.assertEqual(result, 'PARAM 3（面間距離） + IPARAM 1（断熱厚） + DESP[3]（設計長さ） + DES PARA[3]（設計長さ） + APARA[3]（取付先寸法） + OPARAM 3（設定名未登録）')
        self.assertEqual(presets.expression_names(self.data,self.record,text),'PARAM 3 面間距離 / IPARAM 1 断熱厚 / DES PARAM 3 設計長さ / APARAM 3 取付先寸法 / OPARAM 3 設定名未登録')

    def test_literals_and_similar_words_are_not_annotated(self):
        text = '\'PARAM 3\' + "PARA[3]" + PARAMETER3 + PARAM 3'
        self.assertEqual(presets.display_expression(self.data, self.record, text), '\'PARAM 3\' + "PARA[3]" + PARAMETER3 + PARAM 3（面間距離）')
        self.assertEqual(presets.expression_names(self.data,self.record,text),'面間距離')
        self.assertEqual(presets.expression_names(self.data,self.record,"'PARAM 3' + 100"),'')


class ParameterDisplayGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = IntegratedStudio()
        except tk.TclError as exc:
            self.skipTest('GUI display unavailable: ' + str(exc))
        self.errors = []
        self.app.report_callback_exception = lambda kind, value, trace: self.errors.append(str(value))
        self.app.update()

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app.destroy()

    def test_visible_preset_selection_updates_table_and_input_caption_without_changing_numbers(self):
        e = self.app.geometry_editor
        profiles = [presets.add(self.app.data, name) for name in ('旧部品の規則', '新部品の規則')]
        for profile, role in zip(profiles, ('面間距離', '胴部長さ')):
            next(p for p in profile['parameters'] if p['id'] == 'P3')['role'] = role
        e.refresh()
        e.tables['main'].selection_set('PDIS')
        self.app.update()
        e.expression.set('PARAM 3 / 2')
        self.assertTrue(e.preset_choice.winfo_ismapped())
        self.assertFalse(e.settings_frame.winfo_ismapped())
        unrelated = copy.deepcopy(self.app.data['definitions'][1])
        for profile, role in zip(profiles, ('面間距離', '胴部長さ')):
            e.preset_choice.set(profile['name'])
            e.preset_choice.event_generate('<<ComboboxSelected>>')
            self.app.update()
            self.assertEqual(presets.selected_id(self.app.data, e.definition()), profile['id'])
            table=e.tables['main']
            self.assertEqual(table.item('PDIS', 'values')[-1], 'PARAM 3 / 2')
            self.assertEqual(table.canvas.itemcget(table.canvas.find_withtag('value:PDIS')[0],'text'),'PARAM 3 / 2')
            self.assertEqual(table.canvas.itemcget(table.canvas.find_withtag('caption:PDIS')[0],'text'),role)
            self.assertEqual(e.expression_caption['text'],role)
            self.assertEqual(e.expression.get(), 'PARAM 3 / 2')
            self.assertEqual(e.element()['attrs']['PDIS'], 'PARAM 3 / 2')
        self.assertEqual(self.app.data['definitions'][1], unrelated)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'catalog.json'
            project.save(self.app.data, path)
            loaded = project.load(path)
            definition = project.get(loaded, 'definitions', e.definition_id)
            self.assertEqual(definition['elements'][0]['attrs']['PDIS'], 'PARAM 3 / 2')
        self.assertEqual(self.errors, [])

    def test_editing_shows_live_names_but_description_stays_literal(self):
        e = self.app.geometry_editor
        e.tables['main'].selection_set('PDIS')
        self.app.update()
        e.expression.set('PARA[3] + PARAM 1')
        self.assertEqual(e.expression_caption['text'], 'PARAM 3 全長 / PARAM 1 大径側外径')
        e.reference_button.invoke()
        e.ref_number.set('3')
        self.app.update()
        self.assertIn('PARAM 3 / 全長', e.role_label['text'])
        e.tables['main'].selection_set('DESC')
        self.app.update()
        e.expression.set('PARAM 3 という説明文')
        self.assertEqual(e.tables['main'].item('DESC', 'values')[-1], 'PARAM 3 という説明文')
        self.assertFalse(e.expression_caption.winfo_ismapped())
        self.assertEqual(self.errors, [])
