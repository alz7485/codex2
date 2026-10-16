import copy
import tkinter as tk
from tkinter import ttk
import unittest

from catalog_studio import element_schema as schema
from catalog_studio.integrated import IntegratedStudio


class SimpleAuthoringTests(unittest.TestCase):
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

    def test_management_menu_opens_by_mouse_and_navigates_to_presets(self):
        app=self.app;menu=app.more_nav_menu;button=app.more_nav_button
        for page,label in (('rules','PARAM プリセット'),('texts','説明・材質'),('rules','PARAM プリセット')):
            button.event_generate('<Motion>',x=15,y=15,warp=True);app.update()
            button.event_generate('<ButtonPress-1>',x=15,y=15)
            button.event_generate('<ButtonRelease-1>',x=15,y=15);app.update()
            self.assertTrue(menu.winfo_ismapped())
            index=next(i for i in range(menu.index('end')+1) if menu.entrycget(i,'label')==label)
            y=menu.yposition(index)+5
            menu.event_generate('<Motion>',x=20,y=y,warp=True);app.update()
            menu.event_generate('<ButtonRelease-1>',x=20,y=y);app.update()
            self.assertEqual(app.page,page);self.assertFalse(menu.winfo_ismapped())
            if page=='rules':self.assertTrue(app.preset_editor.winfo_ismapped())
        self.assertEqual(self.errors,[])

    def test_point_addition_can_be_cancelled_then_created_and_selected(self):
        e = self.app.geometry_editor
        before = copy.deepcopy(e.definition())
        self.assertFalse(e.creation_frame.winfo_ismapped())
        e.add_button.invoke()
        self.app.update()
        self.assertTrue(e.creation_frame.winfo_ismapped())
        e.library.selection_clear(0, 'end')
        e.library.selection_set(3)
        e.library.event_generate('<<ListboxSelect>>')
        self.app.update()
        self.assertIn('PTCPOS', e.type_help['text'])
        e.add_button.invoke()
        self.app.update()
        self.assertEqual(e.definition(), before)
        e.add_button.invoke()
        e.create_element_button.invoke()
        self.app.update()
        self.assertEqual(e.element()['type'], 'PTPOS')
        self.assertEqual(e.elements.selection(), (e.element_id,))
        self.assertFalse(e.creation_frame.winfo_ismapped())
        self.assertEqual(e.tables['main'].get_children(), schema.fields('PTPOS')+schema.PT_DETAIL)
        self.assertEqual(self.errors, [])

    def test_parameter_picker_in_dialog_inserts_without_committing_until_confirmed(self):
        e=self.app.geometry_editor;table=e.tables['main'];table.selection_set('PDIS');self.app.update()
        original=e.element()['attrs']['PDIS'];e.focus_value_input();self.app.update();dialog=table.editing['dialog']
        dialog.variable.set('');dialog.insert_button.invoke();self.app.update()
        menu,index=dialog.reference_rows[('PARAM','P3')];self.assertIn('全長',menu.entrycget(index,'label'))
        menu.invoke(index);self.app.update()
        self.assertEqual(dialog.variable.get(),'PARAM[3]');self.assertEqual(e.element()['attrs']['PDIS'],original)
        dialog.confirm_button.invoke();self.app.update();self.assertEqual(e.element()['attrs']['PDIS'],'PARAM[3]')
        table.selection_set('NUMB');self.app.update();e.focus_value_input();self.app.update()
        self.assertFalse(table.editing['dialog'].uses_parameters);table.cancel_edit();self.assertEqual(self.errors,[])

    def test_hidden_settings_remain_editable_and_keep_point_values(self):
        e = self.app.geometry_editor
        attrs = copy.deepcopy(e.element()['attrs'])
        self.assertFalse(e.settings_frame.winfo_ismapped())
        e.operations_menu.invoke(e.settings_menu_index)
        self.app.update()
        self.assertTrue(e.preset_choice.winfo_ismapped())
        e.def_name.set('/RENAMED-SIMPLE-POINTS')
        e.operations_menu.invoke(e.settings_menu_index)
        self.app.update()
        self.assertFalse(e.settings_frame.winfo_ismapped())
        self.assertEqual(e.definition()['name'], '/RENAMED-SIMPLE-POINTS')
        self.assertEqual(e.def_choice.get(), '/RENAMED-SIMPLE-POINTS')
        self.assertEqual(e.element()['attrs'], attrs)
        menu=self.app.more_nav_menu
        index=next(i for i in range(menu.index('end')+1) if menu.entrycget(i,'label')=='PARAM プリセット')
        menu.invoke(index)
        self.app.update()
        self.assertEqual(self.app.page,'rules')
        self.assertEqual(self.errors, [])

    def test_geometry_options_follow_element_and_inline_preview_closes_on_navigation(self):
        self.app.switch('gmset')
        self.app.update()
        e = self.app.geometry_editor
        self.assertFalse(any(button.winfo_ismapped() for button, match in e.helper_buttons))
        self.assertTrue(e.canvas.winfo_ismapped())
        e.negative.set(True)
        e.populate_library()
        e.library.selection_clear(0, 'end')
        e.library.selection_set(list(schema.NEGATIVE_BASE).index('NSCY'))
        e.add_element()
        self.app.update()
        self.assertTrue(next(button for button, match in e.helper_buttons if match == 'negative').winfo_ismapped())
        e.open_preview()
        self.app.update()
        preview = e.canvas
        self.assertTrue(preview.winfo_exists())
        self.assertFalse(any(isinstance(child,tk.Toplevel) for child in self.app.winfo_children()))
        self.app.switch('catalog')
        self.app.update()
        self.assertFalse(preview.winfo_exists())
        self.assertEqual(self.errors, [])

    def test_four_columns_keep_the_preview_and_value_input_visible(self):
        app=self.app;e=app.geometry_editor;view=e.point_canvas
        self.assertTrue(view.canvas.winfo_ismapped())
        self.assertFalse(any(isinstance(child,tk.Toplevel) for child in app.winfo_children()))
        for size in ('1440x960','1120x780'):
            app.geometry(size);app.update()
            widgets=(app.registered_browser.tree,e.elements,view.canvas,e.tables['main'])
            for before,after in zip(widgets,widgets[1:]):
                self.assertLessEqual(before.winfo_rootx()+before.winfo_width(),after.winfo_rootx())
            self.assertGreater(view.canvas.winfo_width(),220)
            e.tables['main'].selection_set('PDIS');app.update()
            e.focus_value_input();app.update();entry=e.tables['main'].editing['entry']
            dialog=e.tables['main'].editing['dialog']
            self.assertIsInstance(dialog,tk.Toplevel)
            for widget in (entry,dialog.insert_button,dialog.confirm_button,e.add_button):
                self.assertTrue(widget.winfo_ismapped())
                self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(),app.winfo_rootx()+app.winfo_width())
                self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),app.winfo_rooty()+app.winfo_height())
            e.tables['main'].cancel_edit();app.update()
        controls=list(view.plane_buttons.values())+list(view.view_buttons.values())+list(view.display_buttons.values())
        self.assertEqual(len({widget.winfo_rooty() for widget in controls}),1)
        self.assertEqual(tuple(view.control_groups),('基準面','視点','表示'))
        for group in view.control_groups.values():self.assertIsInstance(group,ttk.LabelFrame)
        viewport=view.control_viewport
        self.assertEqual(bool(view.control_scroll.winfo_ismapped()),view.control_row.winfo_reqwidth()>viewport.winfo_width())
        sash=e.main_split.sashpos(1)
        e.main_split.sashpos(1,e.main_split.sashpos(0)+200);app.update()
        self.assertTrue(view.control_scroll.winfo_ismapped())
        view.control_viewport.xview_moveto(1);app.update();last=controls[-1]
        self.assertLessEqual(last.winfo_rootx()+last.winfo_width(),viewport.winfo_rootx()+viewport.winfo_width())
        view.control_viewport.xview_moveto(0);app.update()
        self.assertGreaterEqual(controls[0].winfo_rootx(),viewport.winfo_rootx())
        e.main_split.sashpos(1,sash);app.update()
        app.geometry('1440x960');app.update()
        self.assertFalse(view.control_scroll.winfo_ismapped())
        for widget in controls:
            self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(),viewport.winfo_rootx()+viewport.winfo_width())
        self.assertGreater(view.canvas.winfo_height(),300)
        self.assertFalse(any(isinstance(child,ttk.Button) for child in view.winfo_children()))
        self.assertEqual(self.errors,[])

    def test_switching_registered_set_replaces_preview_and_updates_attributes(self):
        app=self.app;old=app.geometry_editor.point_canvas
        record={'id':'inline-test-set','name':'/ANOTHER-PTSET','kind':'PTSET','revision':'01','elements':[]}
        point=schema.add_element(record,'PTCAR');point['attrs'].update(PX='PARAM 3',PY='0',PZ='0',PTCDIR='X')
        app.data['definitions'].append(record);app.registered_browser.refresh();app.update()
        app.registered_browser.tree.selection_set('definitions:'+record['id']);app.update()
        e=app.geometry_editor
        self.assertFalse(old.winfo_exists());self.assertEqual(e.definition_id,record['id'])
        self.assertTrue(e.point_canvas.canvas.winfo_ismapped());self.assertEqual(e.element_id,point['id'])
        table=e.tables['main']
        self.assertEqual(table.item('PX','values')[2],'PARAM 3')
        self.assertEqual(table.canvas.itemcget(table.canvas.find_withtag('caption:PX')[0],'text'),'全長')
        self.assertEqual(self.errors,[])

    def test_clicking_the_meaning_line_selects_the_attribute_for_editing(self):
        e=self.app.geometry_editor;table=e.tables['main'];canvas=table.canvas
        top,bottom=table.bounds['PDIS'];y=top+table.name_font.metrics('linespace')+12-canvas.canvasy(0)
        canvas.event_generate('<Button-1>',x=15,y=round(y));self.app.update()
        self.assertEqual(e.field,'PDIS');self.assertEqual(table.selection(),('PDIS',))
        e.expression.set('PARAM 3 / 3');self.app.update()
        self.assertEqual(e.element()['attrs']['PDIS'],'PARAM 3 / 3')
        canvas.focus_force();canvas.event_generate('<Up>');self.app.update()
        self.assertEqual(e.field,'PAXI');self.assertEqual(self.errors,[])

    def test_keyboard_scroll_reaches_last_attribute_and_keeps_value_editable(self):
        self.app.switch('gmset');self.app.update();e=self.app.geometry_editor
        point=schema.add_element(e.definition(),'LPYR');e.element_id=point['id'];e.refresh()
        self.app.geometry('1120x780');self.app.update();table=e.tables['main'];canvas=table.canvas
        canvas.focus_force();canvas.event_generate('<End>');self.app.update()
        self.assertEqual(e.field,'PURP');top,bottom=table.bounds['PURP']
        self.assertGreaterEqual(top,canvas.canvasy(0)-1)
        self.assertLessEqual(bottom,canvas.canvasy(0)+canvas.winfo_height()+1)
        e.expression.set('DEMO');self.app.update();self.assertEqual(point['attrs']['PURP'],'DEMO')
        self.assertEqual(table.item('PURP','values')[-1],'DEMO')
        canvas.focus_force();canvas.event_generate('<Home>');self.app.update()
        self.assertEqual(e.field,'PAAX');self.assertLessEqual(canvas.canvasy(0),1)
        self.assertEqual(self.errors,[])
