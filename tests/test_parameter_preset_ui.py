import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from catalog_studio import project, presets
from catalog_studio.integrated import IntegratedStudio


class ParameterPresetUITests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.errors=[];self.app.report_callback_exception=lambda kind,value,trace:self.errors.append(str(value))
        self.profile=presets.add(self.app.data,'配管部品の規則')
        for p,english in zip(self.profile['parameters'],('Connection Bore','Outside Diameter','Face-to-Face Length','Large Bore','Small Bore')):p['english_name']=english
        self.app.data['active_parameter_preset_id']=self.profile['id'];self.app.geometry('1440x960');self.app.switch('rules');self.app.update();self.e=self.app.preset_editor
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def cell(self,pid,key,text):
        self.e.begin_cell(pid,key);self.app.update();self.assertIsNotNone(self.e.cell)
        self.e.cell['var'].set(text);self.assertTrue(self.e.finish_cell());self.app.update()

    def test_new_preset_starts_empty_and_inline_rows_save_from_project_save(self):
        win=self.e.add();self.app.update();win.name_var.set('新しい機器の規則');win.submit();self.app.update()
        self.assertEqual(self.e.parameters(),[]);self.assertEqual(presets.rules(self.app.data),[])
        self.e.add_row();self.app.update();self.e.cell['var'].set('接続口径（呼び）');self.e.finish_cell();self.cell('P1','english_name','Connection Bore')
        self.assertEqual(presets.rules(self.app.data),[])
        with tempfile.TemporaryDirectory() as folder:
            self.app.path=str(Path(folder)/'project.json');self.assertTrue(self.app.save_project())
            loaded=project.load(self.app.path);record=presets.get(loaded,presets.selected_id(loaded))
            self.assertEqual(record['parameters'][0]['meaning'],'接続口径（呼び）');self.assertEqual(record['parameters'][0]['english_name'],'Connection Bore')
        self.assertEqual(self.app.data['texts'],[]);self.assertEqual(self.errors,[])

    def test_preset_edits_save_without_changing_existing_catalogue_texts(self):
        self.app.data['texts'].append({'id':'existing-text','type':'TEXT','name':'/PARAM1','parent_id':self.app.cate_id,'revision':'01','attrs':{'STEXT':'Original Bore'}})
        before=copy.deepcopy(self.app.data['texts'])
        self.cell('P1','meaning','接続口径');self.cell('P1','english_name','Revised Connection Bore')
        self.assertEqual(self.profile['parameters'][0]['english_name'],'Connection Bore')
        self.assertTrue(self.e.save());self.assertEqual(self.profile['parameters'][0]['english_name'],'Revised Connection Bore')
        self.assertEqual(self.app.data['texts'],before);self.app.switch('ptset');self.app.switch('rules');self.app.update()
        self.assertEqual(self.app.preset_editor.table.item('P1','values')[2],'Revised Connection Bore')
        self.assertEqual(self.app.data['texts'],before);self.assertEqual(self.errors,[])

    def test_japanese_meaning_is_shown_beside_param_after_save_without_alias_rewrite(self):
        before=copy.deepcopy(self.app.data['scoms']);self.cell('P1','meaning','接続口径（呼び径）');self.cell('P1','english_name','Connection Bore');self.e.save()
        self.app.switch('ptset');self.app.update();editor=self.app.geometry_editor
        editor.preset_choice.set(self.profile['name']);editor.assign_preset();self.app.update()
        self.assertEqual(editor.tables['main'].canvas.itemcget(editor.tables['main'].canvas.find_withtag('caption:PBOR')[0],'text'),'接続口径（呼び径）')
        editor.tables['main'].begin_edit('PBOR');self.app.update();dialog=editor.tables['main'].editing['dialog'];dialog.insert_button.invoke();self.app.update()
        menu,index=dialog.reference_rows[('PARAM','P1')];self.assertIn('接続口径（呼び径）',menu.entrycget(index,'label'))
        self.assertEqual(self.profile['parameters'][0]['role'],'大径側外径');self.assertEqual(self.app.data['scoms'],before)
        dialog.dismiss_references();editor.tables['main'].cancel_edit();self.assertEqual(self.errors,[])

    def test_row_duplicate_delete_and_number_edit_do_not_renumber_other_rows(self):
        self.e.table.selection_set('P1');self.e.duplicate_row();self.app.update()
        self.assertEqual(self.e.parameters()[-1]['id'],'P6')
        self.assertEqual(self.e.parameters()[-1]['english_name'],'Connection Bore')
        self.cell('P6','number','10');self.assertEqual([p['id'] for p in self.e.parameters()],['P1','P2','P3','P4','P5','P10'])
        self.e.table.selection_set('P10');self.e.remove_parameter();self.app.update()
        self.assertEqual([p['id'] for p in self.e.parameters()],['P1','P2','P3','P4','P5'])
        presets.bind(self.app.data,self.app.data['scoms'][0],self.profile['id']);self.e.table.selection_set('P1');self.e.remove_parameter()
        self.assertIn('使用中',self.e.message['text']);self.assertEqual(len(self.e.parameters()),5);self.assertEqual(self.errors,[])

    def test_unsaved_edit_cancel_keeps_draft_and_discard_leaves_without_changing_preset(self):
        original=copy.deepcopy(self.profile);self.cell('P1','english_name','Unsaved')
        with patch('catalog_studio.preset_ui.messagebox.askyesnocancel',return_value=None):self.app.switch('ptset')
        self.assertEqual(self.app.page,'rules');self.assertEqual(self.e.parameters()[0]['english_name'],'Unsaved');self.assertEqual(self.profile,original)
        with patch('catalog_studio.preset_ui.messagebox.askyesnocancel',return_value=False):self.app.switch('ptset')
        self.app.update();self.assertEqual(self.app.page,'ptset');self.assertEqual(self.profile,original);self.assertEqual(self.errors,[])

    def test_preset_selection_guard_and_duplicate_preserve_all_names(self):
        other=presets.add(self.app.data,'別の規則');self.app.registered_browser.refresh();self.app.update();self.cell('P1','english_name','Draft')
        with patch('catalog_studio.preset_ui.messagebox.askyesnocancel',return_value=None):
            self.app.registered_browser.tree.selection_set('parameter_presets:'+other['id']);self.app.update()
        self.assertEqual(presets.selected_id(self.app.data),self.profile['id'])
        self.assertEqual(self.app.registered_browser.tree.selection(),('parameter_presets:'+self.profile['id'],))
        self.e.save();win=self.e.duplicate();self.app.update();win.name_var.set('複製した規則');win.submit();self.app.update()
        clone=presets.get(self.app.data,presets.selected_id(self.app.data));self.assertEqual(clone['parameters'][0]['english_name'],'Draft')
        self.cell('P1','english_name','Only Clone');self.e.save();self.assertEqual(self.profile['parameters'][0]['english_name'],'Draft');self.assertEqual(self.errors,[])

    def test_preset_editor_is_independent_of_cate_and_allows_incomplete_english(self):
        self.app.data['cates']=[];self.app.cate_id=None;self.app.switch('rules');self.app.update();self.e=self.app.preset_editor
        self.cell('P2','english_name','');self.cell('P1','meaning','接続口径');self.assertTrue(self.e.save())
        self.assertEqual(self.profile['parameters'][1]['english_name'],'');self.assertEqual(self.app.data['texts'],[])
        def labels(widget):
            result=[]
            if 'text' in widget.keys():result.append(str(widget['text']))
            for child in widget.winfo_children():result.extend(labels(child))
            return result
        visible=' '.join(labels(self.e));self.assertNotIn('CATE',visible);self.assertNotIn('生成',visible)
        self.assertEqual(self.e.table.heading('english')['text'],'STEXT');self.assertEqual(self.errors,[])

    def test_compact_layout_and_editable_cells_stay_visible_at_minimum_size(self):
        for size in ('1440x960','1120x780'):
            self.app.geometry(size);self.app.update()
            self.assertEqual(tuple(self.e.table['displaycolumns']),('number','meaning','english'))
            self.e.begin_cell('P1','english_name');self.app.update();entry=self.e.cell['entry']
            self.assertTrue(entry.winfo_ismapped());self.assertLessEqual(entry.winfo_rootx()+entry.winfo_width(),self.app.winfo_rootx()+self.app.winfo_width())
            self.e.cancel_cell()
            for widget in (self.e.save_button,self.e.add_row_button,self.app.registered_browser.add_button):
                self.assertTrue(widget.winfo_ismapped());self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(),self.app.winfo_rootx()+self.app.winfo_width())
                self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),self.app.winfo_rooty()+self.app.winfo_height())
        self.assertEqual(self.errors,[])
