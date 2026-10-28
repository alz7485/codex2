import copy
import tkinter as tk
from tkinter import ttk
import unittest

from catalog_studio.integrated import IntegratedStudio
from catalog_studio import element_schema as schema


class PointAuthoringTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = IntegratedStudio()
        except tk.TclError as exc:
            self.skipTest('GUI display unavailable: ' + str(exc))
        self.errors = []
        self.app.report_callback_exception = lambda kind, value, trace: self.errors.append(str(value))
        for key in ('definitions', 'scoms', 'cates', 'specs', 'books'):
            self.app.data[key] = []
        self.app.reset_selection()
        self.app.switch('ptset')
        self.app.update()

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app.destroy()

    def descendants(self, widget):
        for child in widget.winfo_children():
            yield child
            yield from self.descendants(child)

    def create_set(self):
        browser=self.app.registered_browser
        browser.add_button.invoke();self.app.update()
        browser.rename_item();browser.renaming['variable'].set('/MY-POINTS')
        self.assertTrue(browser.finish_rename());self.app.update()
        return self.app.geometry_editor

    def choose_type(self, editor, index):
        if not editor.creating:
            editor.add_button.invoke()
            self.app.update()
        editor.library.selection_clear(0, 'end')
        editor.library.selection_set(index)
        editor.library.event_generate('<<ListboxSelect>>')
        self.app.update()

    def test_named_set_is_empty_until_explicit_point_creation(self):
        editor = self.app.geometry_editor
        self.assertEqual(str(editor.create_element_button['state']), 'disabled')
        browser=self.app.registered_browser
        browser.add_button.invoke();self.app.update()
        self.assertEqual(self.app.geometry_editor.definition()['name'],'新しいアイテム(1)')
        browser.rename_item();browser.renaming['variable'].set('')
        self.assertFalse(browser.finish_rename())
        browser.renaming['variable'].set('/NAMED-SET')
        self.assertTrue(browser.finish_rename());self.app.update()
        editor = self.app.geometry_editor
        self.assertEqual(editor.definition()['name'], '/NAMED-SET')
        self.assertTrue(self.app.registered_browser.tree.exists('definitions:' + editor.definition_id))
        self.assertEqual(editor.definition()['elements'], [])
        self.assertEqual(editor.elements.get_children(), ())
        self.assertIsNone(editor.element())
        self.assertEqual(str(editor.create_element_button['state']), 'normal')
        self.assertEqual(self.app.page, 'ptset')
        self.assertEqual(self.errors, [])

    def test_each_choice_explains_definition_then_create_selects_fresh_point(self):
        editor = self.create_set()
        cases = (
            ('PTAXI', ('PAXI', 'PDIS'), ('NUMB', 'PCON', 'PBOR', 'PAXI', 'PDIS')),
            ('PTCAR', ('PX', 'PY', 'PZ', 'PTCDIR'), ('NUMB', 'PCON', 'PBOR', 'PX', 'PY', 'PZ', 'PTCDIR')),
            ('PTMIX', ('PX', 'PY', 'PZ', 'PAXI'), ('NUMB', 'PCON', 'PBOR', 'PX', 'PY', 'PZ', 'PAXI')),
            ('PTPOS', ('PTCPOS', 'PTCDIR'), ('NUMB', 'PCON', 'PBOR', 'PTCPOS', 'PTCDIR')),
        )
        identifiers = set()
        for index, (kind, help_tokens, fields) in enumerate(cases):
            before = copy.deepcopy(editor.definition()['elements'])
            selected = editor.element_id
            self.choose_type(editor, index)
            self.assertEqual(editor.definition()['elements'], before)
            self.assertEqual(editor.element_id, selected)
            for token in help_tokens:
                self.assertIn(token, editor.type_help['text'])
            self.assertEqual(editor.create_element_button['text'], kind + ' を作成')
            editor.create_element_button.invoke()
            self.app.update()
            point = editor.element()
            self.assertEqual(point['type'], kind)
            self.assertEqual(point['attrs']['NUMB'], str(index + 1))
            self.assertNotIn(point['id'], identifiers)
            identifiers.add(point['id'])
            self.assertEqual(editor.elements.selection(), (point['id'],))
            self.assertEqual(editor.tables['main'].get_children(), fields+schema.PT_DETAIL)
        self.assertEqual(len(editor.definition()['elements']), 4)
        self.assertEqual(self.errors, [])

    def test_edit_selected_points_independently_and_refresh_displayed_number(self):
        editor = self.create_set()
        editor.create_element_button.invoke()
        self.app.update()
        first = editor.element()
        editor.tables['main'].selection_set('PDIS')
        self.app.update()
        editor.expression.set('PARAM 3 / 2')
        self.choose_type(editor, 1)
        editor.create_element_button.invoke()
        self.app.update()
        second = editor.element()
        editor.tables['main'].selection_set('PY')
        self.app.update()
        editor.expression.set('0.5 * APARAM[3]')
        editor.elements.selection_set(first['id'])
        self.app.update()
        editor.tables['main'].selection_set('PDIS')
        self.app.update()
        self.assertEqual(editor.expression.get(), 'PARAM 3 / 2')
        self.assertEqual(second['attrs']['PY'], '0.5 * APARAM[3]')
        editor.tables['main'].selection_set('NUMB')
        self.app.update()
        editor.expression.set('10')
        self.assertEqual(editor.elements.item(first['id'], 'values'), ('10',first['name'],'PTAXI'))
        editor.elements.selection_set(second['id'])
        self.app.update()
        editor.tables['main'].selection_set('PY')
        self.app.update()
        self.assertEqual(editor.expression.get(), '0.5 * APARAM[3]')
        self.assertEqual(self.errors, [])

    def test_cancel_rename_preserves_created_set(self):
        browser=self.app.registered_browser
        browser.add_button.invoke();self.app.update()
        before=copy.deepcopy(self.app.data)
        browser.rename_item();browser.renaming['variable'].set('取消')
        browser.cancel_rename();self.app.update()
        self.assertEqual(self.app.data,before)
        self.assertEqual(self.app.geometry_editor.definition()['name'],'新しいアイテム(1)')
        self.assertEqual(self.errors,[])
