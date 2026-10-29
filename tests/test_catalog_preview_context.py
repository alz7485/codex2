import copy
import tkinter as tk
import unittest
from catalog_studio import project,catalogue
from catalog_studio.integrated import IntegratedStudio

class CatalogPreviewContextTests(unittest.TestCase):
    def test_same_cate_keeps_last_scom_canvas_and_camera_other_cate_starts_first(self):
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        errors=[];app.report_callback_exception=lambda k,v,t:errors.append(str(v))
        try:
            cate=app.data['cates'][0];parts=[s for s in app.data['scoms'] if s['cate_id']==cate['id']]
            t=catalogue.add_record(app.data,'texts','TEXT','/PREVIEW-CONTEXT-TEXT',cate['id'])
            empty=project.add_cate(app.data,'/EMPTY-CONTEXT')
            app.switch('catalog');app.update();b=app.registered_browser
            def select(key):b.tree.selection_set(key);app.update()
            select('scoms:'+parts[-1]['id'])
            view=app.preview;view.camera.yaw=12;view.camera.pitch=22;view.zoom_factor=1.3
            view.render_mode.set('ワイヤー');view.redraw();app.update()
            before=copy.deepcopy(app.data)
            for key in ('texts:'+t['id'],'cates:'+cate['id'],'texts:'+t['id']):
                select(key)
                self.assertIs(app.preview,view)
                self.assertEqual(app.scom_id,parts[-1]['id'])
                self.assertEqual(view.editor.preview_scom_id,parts[-1]['id'])
                self.assertEqual((view.camera.yaw,view.camera.pitch,view.zoom_factor),(12,22,1.3))
                self.assertEqual(view.render_mode.get(),'ワイヤー')
            self.assertFalse(view.editor.reference_bar.winfo_ismapped())
            select('cates:'+empty['id']);self.assertIsNone(app.scom_id);self.assertIsNone(app.preview.editor.preview_scom_id)
            select('texts:'+t['id']);self.assertEqual(app.scom_id,parts[0]['id'])
            self.assertEqual(app.preview.editor.preview_scom_id,parts[0]['id'])
            self.assertEqual(app.data,before);self.assertEqual(errors,[])
        finally:app.destroy()

    def test_cate_names_edit_updates_left_tree_without_changing_ids_or_preview(self):
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        try:
            c=app.data['cates'][0]
            t=catalogue.add_record(app.data,'texts','TEXT','/NAME-LIST-TEXT',c['id'])
            catalogue.add_record(app.data,'texts','SDTE','/NAME-LIST-SDTE',c['id'])
            app.switch('catalog');app.update();b=app.registered_browser
            b.tree.selection_set('cates:'+c['id']);app.update()
            view=app.preview;inspector=app.catalog_inspector
            self.assertEqual(inspector.tree.headings,('アイテム / 種類','名前'))
            self.assertTrue(all(field[2]==('name',) for field in inspector.fields.values()))
            row=next(i for i,f in inspector.fields.items() if f[1]==t['id'])
            inspector.begin(row);inspector.editing['variable'].set('/RENAMED-IN-CATE')
            self.assertTrue(inspector.finish());app.update()
            self.assertEqual(t['name'],'/RENAMED-IN-CATE')
            self.assertIn('/RENAMED-IN-CATE',b.tree.item('texts:'+t['id'],'text'))
            self.assertIs(app.preview,view)
            row=next(i for i,f in inspector.fields.items() if f[1]==t['id'])
            inspector.begin(row);inspector.editing['variable'].set(app.data['scoms'][0]['name'])
            self.assertFalse(inspector.finish());inspector.cancel()
            self.assertEqual(t['name'],'/RENAMED-IN-CATE')
        finally:app.destroy()
