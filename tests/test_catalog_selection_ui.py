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
            for kind,labels in (('CATE',{'PURP'}),('SDTE',{'SKEY','TTEX','RTEX'}),('TEXT',{'STEX'}),('SCOM',{'GTYP','GMRE','PTRE'})):
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
            view=app.catalog_inspector;row=next(iter(view.fields));view.begin(row)
            view.editing['variable'].set('COMP');self.assertTrue(view.finish());app.update()
            self.assertEqual(project.get(app.data,'cates',app.cate_id)['attrs']['PURP'],'COMP')
            self.assertEqual(errors,[])
        finally:app.destroy()
