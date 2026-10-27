import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from catalog_studio import element_library, element_schema as schema, presets, project
from catalog_studio.integrated import IntegratedStudio
from catalog_studio.element_presets_ui import refresh_ptset_presets


class PointsetPresetSelectorTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest('GUI display unavailable: '+str(exc))
        self.errors=[]
        self.app.report_callback_exception=lambda kind,value,trace:self.errors.append(str(value))
        self.app.update();self.e=self.app.geometry_editor
        source={'kind':'PTSET','elements':[]}
        point=schema.add_element(source,'PTCAR');point['name']='新しい接続点'
        point['attrs'].update(PX='PARAM 3',PY='0',PZ='0',PTCDIR='X')
        point['schematic_position']=[1,0,0]
        self.first=element_library.register(self.app.data,source,'直交座標の配置')
        source['elements'][0]['name']='別の接続点'
        self.second=element_library.register(self.app.data,source,'別の配置')
        geometry=next(d for d in self.app.data['definitions'] if d['kind']=='GMSET')
        element_library.register(self.app.data,geometry,'形状専用の配置')
        self.e.refresh();self.app.update()

    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()

    def select(self,record):
        self.e.element_preset_choice.set(record['name'])
        self.e.element_preset_choice.event_generate('<<ComboboxSelected>>')
        self.app.update()
        self.assertEqual(self.errors,[])

    def test_empty_set_loads_without_confirmation_and_only_lists_pointset_presets(self):
        e=self.e;e.definition()['elements'].clear();e.refresh();self.app.update()
        self.assertEqual(tuple(e.element_preset_choice['values']),(self.first['name'],self.second['name']))
        self.assertLess(e.element_preset_choice.winfo_rooty(),e.elements.winfo_rooty())
        with patch('catalog_studio.element_presets_ui.messagebox.askyesno') as confirm:self.select(self.first)
        confirm.assert_not_called()
        copied=e.definition()['elements'][0]
        self.assertEqual(copied['name'],'新しい接続点')
        self.assertEqual(copied['schematic_position'],[1,0,0])
        self.assertNotEqual(copied['id'],self.first['elements'][0]['id'])
        self.assertEqual(e.element_id,copied['id'])
        self.assertEqual(e.element_preset_choice.get(),self.first['name'])
        self.app.switch('gmset');self.app.update()
        self.assertEqual(tuple(self.app.geometry_editor.element_preset_choice['values']),('形状専用の配置',))

    def test_one_existing_element_cancel_preserves_data_selection_and_dirty_state(self):
        e=self.e;e.definition()['elements'][:]=e.definition()['elements'][:1];e.refresh();self.app.update()
        before=copy.deepcopy(self.app.data);selected=e.element_id;dirty=self.app.dirty
        with patch('catalog_studio.element_presets_ui.messagebox.askyesno',return_value=False) as confirm:
            self.select(self.first)
        confirm.assert_called_once()
        self.assertIn('1 個',confirm.call_args.args[1])
        self.assertEqual(self.app.data,before);self.assertEqual(e.element_id,selected)
        self.assertEqual(self.app.dirty,dirty)
        self.assertEqual(e.element_preset_choice.get(),'プリセットを選択')

    def test_switch_replaces_whole_list_and_cancel_restores_previous_preset(self):
        e=self.e
        with patch('catalog_studio.element_presets_ui.messagebox.askyesno',return_value=True) as confirm:self.select(self.first)
        confirm.assert_called_once();e.element()['attrs']['PX']='PARAM 3 / 2';e.refresh()
        before=copy.deepcopy(self.app.data)
        with patch('catalog_studio.element_presets_ui.messagebox.askyesno',return_value=False) as confirm:self.select(self.second)
        confirm.assert_called_once();self.assertEqual(self.app.data,before)
        self.assertEqual(e.element_preset_choice.get(),self.first['name'])
        with patch('catalog_studio.element_presets_ui.messagebox.askyesno') as confirm:self.select(self.first)
        confirm.assert_not_called();self.assertEqual(self.app.data,before)
        with patch('catalog_studio.element_presets_ui.messagebox.askyesno',return_value=True):self.select(self.second)
        self.assertEqual(len(e.definition()['elements']),1)
        self.assertEqual(e.element()['name'],'別の接続点')
        self.assertEqual(e.element()['attrs']['PX'],'PARAM 3')
        self.assertEqual(e.definition()['element_preset_id'],self.second['id'])
        self.assertEqual(self.first['elements'][0]['attrs']['PX'],'PARAM 3')

    def test_replacement_adopts_param_roles_and_roundtrips_source_selection(self):
        e=self.e;profile=presets.add(self.app.data,'別の部品の規則')
        profile['parameters'][2]['role']='新しい全長';self.first['parameter_preset_id']=profile['id']
        with patch('catalog_studio.element_presets_ui.messagebox.askyesno',return_value=True) as confirm:self.select(self.first)
        self.assertIn('PARAM プリセットも',confirm.call_args.args[1])
        self.assertEqual(e.preset_choice.get(),profile['name'])
        self.assertEqual(e.tables['main'].canvas.itemcget(e.tables['main'].canvas.find_withtag('caption:PX')[0],'text'),'新しい全長')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'project.json';project.save(self.app.data,path)
            self.app.data=project.load(path)
        self.app.switch('gmset');self.app.update();self.app.definition_id=e.definition_id
        self.app.switch('ptset');self.app.update()
        self.assertEqual(self.app.geometry_editor.element_preset_choice.get(),self.first['name'])

    def test_missing_param_preset_failure_preserves_current_data_and_choice(self):
        e=self.e
        with patch('catalog_studio.element_presets_ui.messagebox.askyesno',return_value=True):self.select(self.first)
        self.second['parameter_preset_id']='missing-profile';before=copy.deepcopy(self.app.data)
        with patch('catalog_studio.element_presets_ui.messagebox.askyesno',return_value=True),patch('catalog_studio.element_presets_ui.messagebox.showerror') as error:
            self.select(self.second)
        error.assert_called_once();self.assertEqual(self.app.data,before)
        self.assertEqual(e.element_preset_choice.get(),self.first['name'])

    def test_selector_refresh_follows_set_and_library_renames_and_disables_when_empty(self):
        e=self.e
        with patch('catalog_studio.element_presets_ui.messagebox.askyesno',return_value=True):self.select(self.first)
        self.first['name']='名称を更新した配置';refresh_ptset_presets(e)
        self.assertEqual(e.element_preset_choice.get(),self.first['name'])
        other={'id':'empty-pt','name':'/EMPTY','kind':'PTSET','revision':'01','elements':[]}
        self.app.data['definitions'].append(other);e.definition_id=other['id'];e.refresh();self.app.update()
        self.assertEqual(e.element_preset_choice.get(),'プリセットを選択')
        self.app.data['element_presets'].clear();e.refresh();self.app.update()
        self.assertEqual(str(e.element_preset_choice['state']),'disabled')
        self.assertEqual(e.element_preset_choice.get(),'未登録')
