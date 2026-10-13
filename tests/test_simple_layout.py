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

    def test_geometry_options_follow_element_and_preview_closes_on_navigation(self):
        self.app.switch('gmset')
        self.app.update()
        e = self.app.geometry_editor
        self.assertFalse(any(button.winfo_ismapped() for button, match in e.helper_buttons))
        self.assertIsNone(e.canvas)
        e.negative.set(True)
        e.populate_library()
        e.library.selection_clear(0, 'end')
        e.library.selection_set(list(schema.NEGATIVE_BASE).index('NSCY'))
        e.add_element()
        self.app.update()
        self.assertTrue(next(button for button, match in e.helper_buttons if match == 'negative').winfo_ismapped())
        e.open_preview()
        self.app.update()
        win = e.preview_window
        self.assertTrue(win.winfo_exists())
        self.app.switch('catalog')
        self.app.update()
        self.assertFalse(win.winfo_exists())
        self.assertEqual(self.errors, [])
