import copy
import tkinter as tk
import unittest
from catalog_studio import element_schema as schema
from catalog_studio.integrated import IntegratedStudio


class RegisteredBrowserTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = IntegratedStudio()
        except tk.TclError as exc:
            self.skipTest('GUI display unavailable: ' + str(exc))
        self.errors = []
        self.app.report_callback_exception = lambda kind, value, trace: self.errors.append(str(value))
        self.app.update()
        self.browser = self.app.registered_browser

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app.destroy()

    def select_record(self, collection, ident):
        self.browser.tree.selection_set(collection + ':' + ident)
        self.app.update()

    def test_select_sets_opens_their_attributes_and_keeps_edits(self):
        pt = self.app.geometry_editor.definition()
        gm = next(d for d in self.app.data['definitions'] if d['id'] == 'ui-gmset')
        e = self.app.geometry_editor
        e.tables['main'].selection_set('PDIS')
        self.app.update()
        e.expression.set('PARAM 3 / 4')
        self.select_record('definitions', gm['id'])
        self.assertEqual(self.app.page, 'gmset')
        self.assertEqual(self.app.geometry_editor.definition()['id'], gm['id'])
        self.select_record('definitions', pt['id'])
        self.assertEqual(self.app.page, 'ptset')
        self.assertEqual(self.app.geometry_editor.element()['attrs']['PDIS'], 'PARAM 3 / 4')
        self.assertEqual(self.errors, [])

    def test_filter_and_name_changes_do_not_modify_other_records(self):
        data = copy.deepcopy(self.app.data)
        self.browser.search.set('/UI-GEOMETRY')
        self.app.update()
        # Search uses the registered record's actual name, not a page label.
        gm = next(d for d in self.app.data['definitions'] if d['id'] == 'ui-gmset')
        self.browser.search.set(gm['name'])
        self.app.update()
        self.assertTrue(self.browser.tree.exists('definitions:' + gm['id']))
        self.assertEqual(self.app.data, data)
        self.browser.search.set('')
        self.app.update()
        e = self.app.geometry_editor
        e.def_name.set('/RENAMED-REGISTERED-POINTS')
        e.commit_name()
        self.app.update()
        self.assertEqual(self.browser.tree.item('definitions:' + e.definition_id, 'text'), '/RENAMED-REGISTERED-POINTS')
        self.assertEqual(self.errors, [])

    def test_scom_spec_and_top_navigation_are_independent_of_set_selection(self):
        scom = self.app.data['scoms'][1]
        spec = self.app.data['specs'][0]
        self.select_record('scoms', scom['id'])
        self.assertEqual(self.app.page, 'catalog')
        self.assertEqual(self.app.scom_id, scom['id'])
        self.select_record('specs', spec['id'])
        self.assertEqual(self.app.page, 'specs')
        self.assertEqual(self.app.spec_id, spec['id'])
        self.app.nav['ptset'].invoke()
        self.app.update()
        self.assertEqual(self.app.page, 'ptset')
        self.assertEqual(self.browser.tree.selection(), ('definitions:' + self.app.geometry_editor.definition_id,))
        self.assertEqual(self.errors, [])

    def test_typing_values_keeps_editor_and_list_stable(self):
        e = self.app.geometry_editor
        selected = self.browser.tree.selection()
        e.tables['main'].selection_set('PDIS')
        self.app.update()
        for text in ('PARAM 3', 'PARAM 3 +', 'PARAM 3 + 1'):
            e.expression.set(text)
            self.app.update()
            self.assertIs(self.app.geometry_editor, e)
            self.assertEqual(self.browser.tree.selection(), selected)
        definition = {'id': 'new-visible-set', 'name': '/REGISTERED-NEW-GM', 'kind': 'GMSET', 'revision': '01', 'elements': []}
        schema.add_element(definition, 'SCYL')
        self.app.data['definitions'].append(definition)
        self.app.mark()
        self.app.update()
        self.assertTrue(self.browser.tree.exists('definitions:' + definition['id']))
        self.select_record('definitions', definition['id'])
        self.assertEqual(self.app.geometry_editor.definition_id, definition['id'])
        self.assertEqual(self.errors, [])
