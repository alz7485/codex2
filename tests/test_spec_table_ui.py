import json
import tkinter as tk
import unittest
from catalog_studio import project, spec_table_ui

class SpecTableTests(unittest.TestCase):
    def test_new_fields_round_trip_and_validation(self):
        data=project.sample()
        entry=project.add_spec_entry(data,data['specs'][0])
        entry.update(name='V080',angle='45,90',height='120 MM',text='説明 日本語')
        loaded=json.loads(json.dumps(data))
        project.validate(loaded)
        self.assertEqual(loaded['specs'][0]['entries'][-1]['height'],'120 MM')
        entry['angle']=[]
        with self.assertRaises(ValueError):project.validate(data)

    def test_table_and_detached_preview(self):
        from catalog_studio.integrated import IntegratedStudio
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        try:
            app.switch('specs');app.update()
            self.assertTrue({'angle','height','text'}<=set(app.spec_table['columns']))
            self.assertEqual(len(app.spec_table.get_children()),len(app.spec()['entries']))
            self.assertTrue(app.spec_table_rules.lines)
            app.spec_table.xview_moveto(1);app.update()
            self.assertTrue(app.spec_table_rules.lines)
            app.spec_table.xview_moveto(0);app.update()
            spec_table_ui.open_preview(app);app.update()
            window=app.spec_preview_window
            spec_table_ui.open_preview(app)
            self.assertIs(window,app.spec_preview_window)
            entries=app.spec()['entries']
            for entry in entries[:2]:
                app.spec_table.selection_set(entry['id']);app.update()
                self.assertEqual(app.spec_preview.editor.preview_scom_id,entry['scom_id'])
            app.spec_table.column('angle',width=145)
            spec_table_ui.remember_widths(app)
            window.destroy();app.render_page();app.update()
            self.assertEqual(app.spec_table.column('angle','width'),145)
            app.spec_type_filter.set('missing');spec_table_ui.populate(app)
            self.assertEqual(app.spec_table.get_children(),())
            project.validate(app.data)
        finally:app.destroy()
