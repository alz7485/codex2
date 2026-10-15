import copy
import tkinter as tk
import unittest
from catalog_studio import element_library,element_schema as schema,presets
from catalog_studio.element_presets_ui import PresetEditor
from catalog_studio.integrated import IntegratedStudio


class ValueEditorTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest('GUI display unavailable: '+str(exc))
        self.errors=[];self.app.report_callback_exception=lambda kind,value,tb:self.errors.append(str(value));self.app.update()
        self.editor=self.app.geometry_editor;self.table=self.editor.tables['main']

    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
        self.assertEqual(self.errors,[])

    def open(self,key='PDIS'):
        self.table.selection_set(key);self.app.update();self.editor.focus_value_input();self.app.update()
        return self.table.editing['dialog']

    def test_parameter_tools_keep_draft_until_confirmed_and_cancel_restores_everything(self):
        before=copy.deepcopy(self.app.data);dialog=self.open()
        self.assertIsInstance(dialog,tk.Toplevel);dialog.insert_button.invoke();self.app.update()
        self.assertEqual(self.app.data,before);menu,index=dialog.reference_rows[('PARAM','P3')]
        self.assertIn('全長',menu.entrycget(index,'label'));menu.invoke(index);self.app.update()
        self.assertEqual(dialog.variable.get(),'PARAM[3]');dialog.half_button.invoke();self.app.update()
        self.assertEqual(dialog.variable.get(),'(PARAM[3]) / 2');self.assertEqual(self.app.data,before)
        dialog.insert_button.focus_force();self.app.update();self.assertIsNotNone(self.table.editing)
        dialog.cancel_button.invoke();self.app.update();self.assertEqual(self.app.data,before)
        self.assertIsNone(self.table.editing);self.assertIsNone(self.app.grab_current())

    def test_confirm_uses_selected_profile_and_family_specific_names(self):
        profile=presets.add(self.app.data,'部品ごとの規則');profile['reference_roles']={'IPARAM':{'P1':'断熱厚さ'}}
        next(p for p in profile['parameters'] if p['id']=='P3')['role']='面間距離'
        presets.bind(self.app.data,self.editor.definition(),profile['id']);self.editor.refresh();self.app.update()
        dialog=self.open();dialog.variable.set('');dialog.insert_button.invoke();self.app.update()
        menu,index=dialog.reference_rows[('PARAM','P3')];self.assertIn('面間距離',menu.entrycget(index,'label'))
        menu.invoke(index);dialog.operator_buttons['+'].invoke();dialog.insert_button.invoke();self.app.update()
        menu,index=dialog.reference_rows[('IPARAM','P1')];self.assertIn('断熱厚さ',menu.entrycget(index,'label'))
        menu.invoke(index);self.app.update()
        self.assertIn('面間距離',dialog.caption['text']);self.assertIn('断熱厚さ',dialog.caption['text'])
        dialog.confirm_button.invoke();self.app.update();raw=self.editor.element()['attrs']['PDIS']
        self.assertEqual(raw,'PARAM[3] + IPARAM[1]');self.assertNotIn('断熱',raw);self.assertIsNone(self.table.editing)

    def test_dismissing_parameter_list_and_normalizing_leave_source_unchanged(self):
        original=self.editor.element()['attrs']['PDIS'];dialog=self.open()
        draft=dialog.variable.get();dialog.insert_button.invoke();self.app.update()
        self.assertTrue(dialog.reference_menu.winfo_ismapped());dialog.reference_menu.event_generate('<Escape>');self.app.update()
        self.assertFalse(dialog.reference_menu.winfo_ismapped());self.assertTrue(dialog.winfo_exists())
        self.assertEqual(dialog.variable.get(),draft);self.assertIs(self.app.grab_current(),dialog)
        self.assertEqual(self.editor.element()['attrs']['PDIS'],original)
        dialog.variable.set('0.5 TIMES PARAM 3');dialog.normalize_button.invoke();self.app.update()
        self.assertEqual(dialog.variable.get(),'(0.5 * PARAM[3])');self.assertEqual(self.editor.element()['attrs']['PDIS'],original)
        dialog.cancel_button.invoke()

    def test_literal_attributes_use_small_editor_and_preserve_text(self):
        formula=self.open();formula_height=formula.winfo_height();formula.cancel()
        dialog=self.open('DESC');self.assertFalse(dialog.uses_parameters)
        self.assertLess(dialog.winfo_height(),formula_height);dialog.variable.set('PARAM 3 という説明文')
        self.assertEqual(dialog.caption['text'],'');dialog.confirm_button.invoke();self.app.update()
        self.assertEqual(self.editor.element()['attrs']['DESC'],'PARAM 3 という説明文')

    def test_conflicting_edit_stays_open_and_reports_error_in_dialog(self):
        dialog=self.open();dialog.variable.set('PARAM 3 / 2');self.editor.element()['attrs']['PDIS']='PARAM 3 / 7'
        dialog.confirm_button.invoke();self.app.update()
        self.assertTrue(dialog.winfo_exists());self.assertIn('属性が変更',dialog.error['text'])
        self.assertEqual(self.editor.element()['attrs']['PDIS'],'PARAM 3 / 7');dialog.cancel()

    def test_editor_reuses_one_window_and_restores_preset_window_grab(self):
        record=element_library.register(self.app.data,self.editor.definition(),'編集用プリセット')
        parent=PresetEditor(self.editor,record);self.app.update();editor=parent.geometry_editor;table=editor.tables['main']
        table.begin_edit('PDIS');self.app.update();dialog=table.editing['dialog'];dialog.variable.set('PARAM 3 / 2')
        table.begin_edit('PDIS');self.assertIs(table.editing['dialog'],dialog)
        self.assertIs(self.app.grab_current(),dialog);dialog.insert_button.invoke();self.app.update();dialog.cancel();self.app.update()
        self.assertIs(self.app.grab_current(),parent);parent.destroy();self.app.update()

    def test_list_insertion_replaces_selected_range_and_rejects_stale_draft(self):
        dialog=self.open();dialog.variable.set('PARAM[1] + 100');dialog.entry.selection_range(11,14)
        dialog.insert_button.invoke();self.app.update();menu,index=dialog.reference_rows[('PARAM','P3')];menu.invoke(index);self.app.update()
        self.assertEqual(dialog.variable.get(),'PARAM[1] + PARAM[3]')
        dialog.insert_button.invoke();self.app.update();menu,index=dialog.reference_rows[('PARAM','P1')]
        dialog.variable.set('PARAM[2]');menu.invoke(index);self.app.update()
        self.assertEqual(dialog.variable.get(),'PARAM[2]');self.assertIn('挿入位置を選び直',dialog.error['text'])
        dialog.cancel()

    def test_parameter_list_does_not_invent_roles_for_unregistered_families(self):
        dialog=self.open();dialog.insert_button.invoke();self.app.update()
        self.assertEqual(tuple(dialog.reference_menus),schema.REFERENCE_TYPES)
        other=dialog.reference_menus['IPARAM'];self.assertEqual(other.entrycget(0,'state'),'disabled')
        dialog.dismiss_references();dialog.variable.set('IPARAM[99]');dialog.confirm_button.invoke();self.app.update()
        self.assertEqual(self.editor.element()['attrs']['PDIS'],'IPARAM[99]')
