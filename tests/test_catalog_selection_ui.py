import tkinter as tk
import unittest
from unittest.mock import patch
from catalog_studio.integrated import IntegratedStudio
from catalog_studio import project

class CatalogSelectionTests(unittest.TestCase):
    def test_instant_add_list_rename_and_selected_macro_fields(self):
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        errors=[];app.report_callback_exception=lambda k,v,t:errors.append(str(v))
        try:
            app.switch('catalog');app.update();b=app.registered_browser
            for kind,labels in (('CATE',set()),('SDTE',{'SKEY','TTEX','RTEX'}),('TEXT',{'STEX'}),('SCOM',{'GTYP','GMRE','PTRE'})):
                with patch.object(app,'form') as form:
                    b.add_catalog_record(kind);app.update();form.assert_not_called()
                key=b.tree.selection()[0];collection,record=b.items[key]
                self.assertEqual(len(app.catalog_inspector.targets()),1)
                self.assertEqual(app.catalog_inspector.targets()[0][1]['id'],record['id'])
                view=app.catalog_inspector
                displayed={view.tree.item(i,'values')[0] for i in view.fields}
                self.assertTrue(labels<=displayed)
                self.assertFalse({'NAME','REVISION','DESCRIPTION','SIZE','ANGL','PARAM プリセット'}&displayed)
                ident=record['id'];name='/TEST-RENAME-'+kind
                b.tree.focus_set();b.tree.event_generate('<F2>');app.update()
                self.assertIsNotNone(b.renaming)
                b.renaming['variable'].set(name);self.assertTrue(b.finish_rename());app.update()
                self.assertEqual(project.get(app.data,collection,ident)['name'],name)
                self.assertIn(name,app.catalog_inspector.title['text'])
                self.assertIn(name,b.tree.item(key,'text'))
            s=app.data['scoms'][-1];old=s['name']
            b.rename_item();b.renaming['variable'].set(app.data['cates'][-1]['name'])
            self.assertFalse(b.finish_rename());self.assertEqual(s['name'],old);b.cancel_rename()
            b.tree.selection_set('cates:'+app.cate_id);app.update()
            view=app.catalog_inspector;row=next(iter(view.fields));field=view.fields[row];view.begin(row)
            view.editing['variable'].set('/RIGHT-LIST-RENAMED');self.assertTrue(view.finish());app.update()
            self.assertEqual(project.get(app.data,field[0],field[1])['name'],'/RIGHT-LIST-RENAMED')
            self.assertEqual(errors,[])
        finally:app.destroy()

    def test_preview_is_center_and_shared_attribute_table_has_meanings(self):
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        try:
            app.switch('catalog');app.update()
            for width,height in ((1620,960),(1300,780)):
                app.geometry(f'{width}x{height}');app.update()
                view=app.catalog_inspector;table=view.tree
                self.assertLess(app.preview.canvas.winfo_rootx(),table.winfo_rootx())
                self.assertGreater(app.preview.canvas.winfo_width(),300)
                self.assertLessEqual(table.winfo_rootx()+table.winfo_width(),app.winfo_rootx()+app.winfo_width())
                row=next(i for i,f in view.fields.items() if f[2]==('attrs','GTYP'))
                self.assertEqual(table.rows[row][1],'部品の汎用型')
                table.see(row);app.update();a,b=table.bounds[row]
                x=int(table.canvas.winfo_width()*.6);y=int(a-table.canvas.canvasy(0)+10)
                table.canvas.event_generate('<Button-1>',x=x,y=y)
                table.canvas.event_generate('<ButtonRelease-1>',x=x,y=y);app.update()
                self.assertIsNotNone(view.editing)
                view.editing['variable'].set('REDU');self.assertTrue(view.finish());app.update()
                self.assertEqual(project.get(app.data,'scoms',app.scom_id)['attrs']['GTYP'],'REDU')
        finally:app.destroy()
