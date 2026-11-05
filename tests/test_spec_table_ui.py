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

    def test_inline_cells_commit_cancel_and_references(self):
        from types import SimpleNamespace
        from catalog_studio.integrated import IntegratedStudio
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        try:
            app.switch('specs');app.update()
            tree=app.spec_table;entry=app.spec()['entries'][0]
            children=set(app.winfo_children())
            def edit(key):
                tree.configure(displaycolumns=('name','angle','text','scom_id'))
                app.update()
                box=tree.bbox(entry['id'],key)
                spec_table_ui.edit_cell(app,SimpleNamespace(x=box[0]+8,y=box[1]+8))
                app.update()
                return app.spec_cell_edit
            widget,var,*_=edit('angle')
            self.assertIsInstance(widget,tk.ttk.Entry)
            var.set('45,90');widget.event_generate('<Return>');app.update()
            self.assertEqual(entry['angle'],'45,90')
            widget,var,*_=edit('text');var.set('取消値')
            widget.event_generate('<Escape>');app.update()
            self.assertEqual(entry.get('text',''),'')
            widget,var,*_=edit('text');var.set('保存する値')
            app.commit_definition_name()
            self.assertEqual(entry['text'],'保存する値')
            widget,var,_,_,mapping=edit('scom_id')
            self.assertIsInstance(widget,tk.ttk.Combobox)
            target=app.data['scoms'][1]
            var.set(next(k for k,v in mapping.items() if v==target['id']))
            widget.event_generate('<<ComboboxSelected>>');app.update()
            self.assertEqual(entry['scom_id'],target['id'])
            self.assertEqual(set(app.winfo_children()),children)
            project.validate(app.data)
        finally:app.destroy()

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
            original=[e['id'] for e in app.spec()['entries']]
            entries=app.spec()['entries']
            for entry,number in zip(entries,('100','20','3')):entry['angle']=number
            selected=entries[1]['id'];app.spec_table.selection_set(selected)
            # Invoke the real heading callback, rather than the sort helper.
            app.tk.call(app.spec_table.heading('angle','command'));app.update()
            self.assertEqual(app.spec_table.get_children(),tuple(e['id'] for e in reversed(entries)))
            self.assertEqual(app.spec_table.selection(),(selected,))
            app.tk.call(app.spec_table.heading('angle','command'));app.update()
            self.assertEqual(app.spec_table.get_children(),tuple(original))
            self.assertEqual([e['id'] for e in app.spec()['entries']],original)
            entries[1]['angle']='';spec_table_ui.populate(app)
            self.assertEqual(app.spec_table.get_children()[-1],selected)
            self.assertTrue(app.spec_table.heading('angle','text').endswith('▼'))
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
