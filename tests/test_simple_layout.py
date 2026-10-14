import copy
import tkinter as tk
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
        self.assertEqual(e.tables['main'].get_children(), schema.fields('PTPOS'))
        self.assertEqual(self.errors, [])

    def test_parameter_picker_keeps_role_and_value_when_closed(self):
        e = self.app.geometry_editor
        e.tables['main'].selection_set('PDIS')
        self.app.update()
        e.expression.set('')
        self.assertFalse(e.reference_controls.winfo_ismapped())
        e.reference_button.invoke()
        self.app.update()
        e.ref_number.set('3')
        self.assertTrue(e.reference_controls.winfo_ismapped())
        self.assertIn('全長', e.role_label['text'])
        e.insert_reference()
        self.app.update()
        e.reference_button.invoke()
        self.app.update()
        self.assertFalse(e.reference_controls.winfo_ismapped())
        self.assertEqual(e.element()['attrs']['PDIS'], 'PARAM[3]')
        e.tables['main'].selection_set('NUMB')
        self.app.update()
        self.assertEqual(str(e.reference_button['state']), 'disabled')
        self.assertEqual(self.errors, [])

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
        self.assertFalse(view.settings_frame.winfo_ismapped())
        self.assertFalse(any(isinstance(child,tk.Toplevel) for child in app.winfo_children()))
        for size in ('1440x960','1120x780'):
            app.geometry(size);app.update()
            widgets=(app.registered_browser.tree,e.elements,view.canvas,e.tables['main'])
            for before,after in zip(widgets,widgets[1:]):
                self.assertLessEqual(before.winfo_rootx()+before.winfo_width(),after.winfo_rootx())
            self.assertGreater(view.canvas.winfo_width(),220)
            e.tables['main'].selection_set('PDIS');app.update()
            for widget in (e.expression_entry,e.reference_button,e.add_button):
                self.assertTrue(widget.winfo_ismapped())
                self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(),app.winfo_rootx()+app.winfo_width())
                self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),app.winfo_rooty()+app.winfo_height())
        view.mode.set('点を追加');view.toggle_settings();app.update()
        self.assertTrue(view.settings_frame.winfo_ismapped());self.assertFalse(view.add_options.winfo_ismapped())
        self.assertGreater(view.canvas.winfo_height(),150)
        view.toggle_settings();app.update()
        self.assertFalse(view.settings_frame.winfo_ismapped());self.assertTrue(view.add_options.winfo_ismapped())
        self.assertGreater(view.canvas.winfo_height(),150)
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
        self.assertEqual(e.tables['main'].item('PX','values')[2],'PARAM 3（全長）')
        self.assertEqual(self.errors,[])
