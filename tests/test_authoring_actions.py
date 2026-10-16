import copy
import tkinter as tk
import unittest
from tkinter import ttk
from catalog_studio.integrated import IntegratedStudio
from catalog_studio import element_schema as schema,element_library
from catalog_studio.element_presets_ui import register_current,choose,PresetEditor


class AuthoringActionTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest('GUI display unavailable: '+str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.update();self.editor=self.app.geometry_editor
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def descendants(self,widget):
        for child in widget.winfo_children():yield child;yield from self.descendants(child)
    def button(self,win,text):return next(w for w in self.descendants(win) if isinstance(w,ttk.Button) and w['text']==text)
    def test_inline_commit_cancel_and_selection_change_keep_the_right_element(self):
        e=self.editor;table=e.tables['main'];point=e.element();original=copy.deepcopy(point['attrs'])
        table.selection_set('PDIS');self.app.update();table.canvas.focus_force();table.canvas.event_generate('<Return>');self.app.update()
        self.assertTrue(table.editing['entry'].winfo_ismapped());table.editing['variable'].set('PARAM 3 / 3')
        self.assertEqual(point['attrs'],original);table.editing['entry'].event_generate('<Escape>');self.app.update()
        self.assertIsNone(table.editing);self.assertEqual(point['attrs'],original)
        table.begin_edit('PDIS');table.editing['variable'].set('PARAM 3 / 3')
        other=e.definition()['elements'][1];unchanged=copy.deepcopy(other['attrs']);e.elements.selection_set(other['id']);self.app.update()
        self.assertEqual(point['attrs']['PDIS'],'PARAM 3 / 3');self.assertEqual(other['attrs'],unchanged)
        self.assertEqual(self.errors,[])
    def test_drag_moves_element_and_renumbers_but_cancelled_drop_changes_nothing(self):
        e=self.editor;d=e.definition();d['elements']=[]
        for number in (10,20,30):schema.add_element(d,'PTAXI')['attrs']['NUMB']=str(number)
        e.refresh();self.app.update();before=copy.deepcopy(d);first=d['elements'][0]['id'];last=d['elements'][2]['id']
        self.assertEqual(tuple(e.elements['columns']),('number','name'))
        a=e.elements.bbox(first);b=e.elements.bbox(last);x=20;start=a[1]+a[3]//2;end=b[1]+b[3]-2
        e.elements.event_generate('<ButtonPress-1>',x=x,y=start);e.elements.event_generate('<B1-Motion>',x=x,y=end);e.elements.event_generate('<ButtonRelease-1>',x=x,y=end);self.app.update()
        self.assertEqual([p['id'] for p in d['elements']],[before['elements'][1]['id'],last,first])
        self.assertEqual([p['attrs']['NUMB'] for p in d['elements']],['1','2','3'])
        now=copy.deepcopy(d);box=e.elements.bbox(first);e.elements.event_generate('<ButtonPress-1>',x=x,y=box[1]+2);e.elements.event_generate('<B1-Motion>',x=x,y=200);e.elements.event_generate('<ButtonRelease-1>',x=x,y=200);self.app.update()
        self.assertEqual(d,now);self.assertEqual(self.errors,[])
    def test_addition_uses_a_separate_window_and_context_menu_has_no_move_commands(self):
        e=self.editor;before=copy.deepcopy(e.definition());e.add_button.invoke();self.app.update()
        self.assertIsInstance(e.creation_frame,tk.Toplevel);self.assertTrue(e.creation_frame.winfo_ismapped())
        e.library.selection_clear(0,'end');e.library.selection_set(2);e.library.event_generate('<<ListboxSelect>>');self.app.update()
        self.assertIn('PAXI',e.type_help['text']);e.cancel_creation_button.invoke();self.app.update();self.assertEqual(e.definition(),before)
        labels=[e.context_menu.entrycget(i,'label') for i in range(e.context_menu.index('end')+1) if e.context_menu.type(i)!='separator']
        self.assertIn('複製',labels);self.assertIn('削除',labels);self.assertNotIn('上へ移動',labels)
        self.assertFalse(any(isinstance(w,ttk.Menubutton) for w in self.descendants(e)))
        self.assertEqual(self.errors,[])
    def test_whole_group_registration_recall_and_preset_edit_do_not_change_old_copies(self):
        e=self.editor;original=copy.deepcopy(e.definition()['elements']);win=register_current(e);self.app.update()
        self.button(win,'登録').invoke();self.app.update();record=e.data['element_presets'][0]
        self.assertEqual(len(record['elements']),len(original));win=choose(e,'recall');self.app.update();self.button(win,'呼び出す').invoke();self.app.update()
        called=copy.deepcopy(e.definition()['elements']);self.assertEqual(len(called),2*len(original))
        win=PresetEditor(e,record);self.app.update();working=win.geometry_editor;table=working.tables['main']
        table.selection_set('PDIS');self.app.update();table.begin_edit('PDIS');table.editing['variable'].set('PARAM 3 * 2');win.save();self.app.update()
        self.assertFalse(win.winfo_exists());self.assertEqual(e.definition()['elements'],called)
        self.assertEqual(record['elements'][0]['attrs']['PDIS'],'PARAM 3 * 2')
        self.assertEqual(self.errors,[])
    def test_inline_edit_is_committed_when_project_is_saved(self):
        import tempfile
        from pathlib import Path
        from catalog_studio import project
        e=self.editor;table=e.tables['main'];table.selection_set('PDIS');self.app.update();table.begin_edit('PDIS');table.editing['variable'].set('PARAM 3 / 4')
        with tempfile.TemporaryDirectory() as folder:
            self.app.path=str(Path(folder)/'edited.json');self.assertTrue(self.app.save_project())
            loaded=project.load(self.app.path);d=project.get(loaded,'definitions',e.definition_id)
            self.assertEqual(d['elements'][0]['attrs']['PDIS'],'PARAM 3 / 4')
        self.assertEqual(self.errors,[])

    def test_direction_buttons_wait_for_dialog_confirmation(self):
        e=self.editor;table=e.tables['main'];table.selection_set('PAXI');self.app.update();table.begin_edit('PAXI');self.app.update()
        entry=table.editing['entry'];self.assertNotIsInstance(entry,ttk.Combobox)
        original=e.element()['attrs']['PAXI'];table.editing['dialog'].direction_buttons['-Y'].invoke();self.app.update()
        self.assertEqual(e.element()['attrs']['PAXI'],original);table.editing['dialog'].confirm_button.invoke();self.app.update()
        self.assertIsNone(table.editing);self.assertEqual(e.element()['attrs']['PAXI'],'-Y');self.assertEqual(self.errors,[])

    def test_conflicting_inline_edit_blocks_project_replacement_until_cancelled(self):
        from unittest.mock import patch
        e=self.editor;table=e.tables['main'];table.selection_set('PDIS');self.app.update();table.begin_edit('PDIS')
        table.editing['variable'].set('PARAM 3 / 4');e.element()['attrs']['PDIS']='PARAM 3 / 5'
        with patch('catalog_studio.integrated.messagebox.askyesnocancel') as prompt:
            self.assertFalse(self.app.guard());prompt.assert_not_called()
        self.assertEqual(e.element()['attrs']['PDIS'],'PARAM 3 / 5');self.assertIsNotNone(table.editing)
        table.cancel_edit();self.assertTrue(e.commit_inline());self.assertEqual(self.errors,[])
