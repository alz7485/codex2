import copy
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch
from catalog_studio import project, diagnostics, model_settings, presets
from catalog_studio.integrated import IntegratedStudio

class WorkflowUiTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v))
        self.app.update()
        self.gm=next(d for d in self.app.data['definitions'] if d.get('sample')=='piping-bend' and d['kind']=='GMSET')
        self.pt=project.get(self.app.data,'definitions',self.gm['paired_ptset_id'])
        self.scom=next(s for s in self.app.data['scoms'] if s.get('sample')=='piping-bend')
    def tearDown(self):
        if hasattr(self,'app'):
            self.app.update();self.app.destroy()
            self.assertEqual(self.errors,[])
    def select(self,record):
        self.app.definition_id=record['id'];self.app.switch(record['kind'].lower());self.app.update()
        return self.app.geometry_editor
    def children(self,w):
        for child in w.winfo_children():
            yield child
            yield from self.children(child)
    def test_role_and_shared_values_editor(self):
        e=self.select(self.pt);e.role_choice.set('分岐');e.assign_role();self.app.update()
        self.assertEqual(self.pt['elements'][0]['point_role'],'分岐')
        self.assertIn('分岐',e.elements.item(self.pt['elements'][0]['id'],'values')[2])
        before=copy.deepcopy(self.app.data['scoms'])
        def accept(title,fields,apply,**kwargs):
            values={key:str(initial) for key,label,initial,choices in fields}
            values.update(DDANGLE='45',P4='152');apply(values)
        with patch.object(self.app,'form',side_effect=accept):model_settings.edit(e)
        self.assertEqual(self.pt['model_settings']['DDANGLE'],45)
        self.assertEqual(self.gm['model_settings']['DDANGLE'],45)
        self.assertEqual(self.gm['schematic_dimensions']['values']['PARAM']['P4'],152)
        self.assertEqual(self.app.data['scoms'],before)
        e=self.select(self.gm);self.assertFalse(e.geometry_view.scene.issues)
    def test_catalog_parameter_context_and_edit_jump(self):
        self.app.scom_id=self.scom['id'];self.app.cate_id=self.scom['cate_id'];self.app.switch('catalog');self.app.update()
        inspector=self.app.catalog_inspector
        self.assertEqual(inspector.parameter_table.item('P4','values')[2],'RAD')
        inspector.parameter_table.selection_set('P4');inspector.open_parameter();self.app.update()
        self.assertEqual(inspector.editing['field'][2],('values','P4'));inspector.cancel()
    def test_diagnostics_jump_to_element_field_and_scom_cell(self):
        node=self.pt['elements'][0];node['attrs']['PAXI']=''
        self.scom['values'].pop('P4')
        self.app.switch('checks');self.app.update()
        row=next(r for r in self.app.diagnostic_rows.values() if r['element_id']==node['id'] and r['field']=='PAXI')
        self.assertTrue(diagnostics.navigate(self.app,row));self.app.update()
        self.assertEqual(self.app.page,'ptset');self.assertEqual(self.app.geometry_editor.tables['main'].selection(),('PAXI',))
        row=next(r for r in diagnostics.collect(self.app.data) if r['record_id']==self.scom['id'] and r['field']=='P4')
        diagnostics.navigate(self.app,row);self.app.update()
        inspector=self.app.catalog_inspector
        self.assertTrue(any(inspector.fields[i][2]==('values','P4') for i in inspector.tree.selection()))
    def test_group_filters_and_presets_prioritized_by_selected_ptset(self):
        e=self.select(self.gm);e.element_id=self.gm['elements'][1]['id'];e.refresh_element()
        e.role_choice.set('保温');e.assign_role();self.app.update()
        e.geometry_view.group_visibility['保温'].set(False);e.geometry_view.redraw()
        self.assertTrue(all(m.kind!='SCTO' for m in e.geometry_view.scene.meshes))
        matching=next(r for r in self.app.data['element_presets'] if r['kind']=='GMSET')
        other=copy.deepcopy(matching);other.update(id='incompatible',name='別規則',parameter_preset_id='')
        self.app.data['element_presets'].insert(0,other)
        win=self.app.set_creation_dialog('GMSET');self.app.update()
        combos=[w for w in self.children(win) if isinstance(w,ttk.Combobox)]
        combos[1].set(self.pt['name']);self.app.update()
        self.assertEqual(tuple(combos[0]['values']),('',matching['name'],'別規則'));win.destroy()
