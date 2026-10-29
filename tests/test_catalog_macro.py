import copy
import unittest
from catalog_studio import project,catalogue,catalog_macro,macro_destinations

class CatalogMacroTests(unittest.TestCase):
    def test_round_trip_and_atomic_rejection(self):
        data=project.sample();c=project.add_cate(data,'/EXAMPLE-CATE')
        t=catalogue.add_record(data,'texts','TEXT','/EXAMPLE-TEXT',c['id']);t['attrs']['STEXT']='Sample'
        s=project.add_scom(data,c['id'],'/EXAMPLE-SCOM');s.update(gmset_id='',ptset_id='',values={'P1':12,'P2':24})
        source=catalog_macro.creation_text(data,c['id'],'DEST')
        self.assertTrue(source.startswith('/DEST\nNEW CATE'))
        target=project.sample();before=copy.deepcopy(target)
        imported,ids=catalog_macro.import_text(target,source)
        self.assertEqual(target,before)
        self.assertEqual(next(r for r in imported['scoms'] if r['cate_id']==ids[0])['values'],s['values'])
        for invalid in (source+'DELETE ALL\n',source.replace('END','UNKNOWN',1),source[:-4]):
            with self.assertRaises(ValueError):catalog_macro.import_text(target,invalid)
            self.assertEqual(target,before)
        with self.assertRaises(ValueError):catalog_macro.import_text(data,source)
        macro_destinations.save_options(target,'CATE',['DEST','/OTHER'])
        project.validate(target)
        self.assertEqual(macro_destinations.options(target,'CATE'),['/DEST','/OTHER'])

    def test_gui_macro_export_import_and_destinations(self):
        import tkinter as tk
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from catalog_studio.integrated import IntegratedStudio
        from catalog_studio import catalog_macro_ui
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        try:
            app.switch('catalog');app.update();b=app.registered_browser
            b.add_catalog_record('CATE');app.update()
            cate=project.get(app.data,'cates',app.cate_id);cate['name']='/GUI-MAC-CATE'
            b.add_catalog_record('TEXT');app.update()
            text=app.data['texts'][-1];text['name']='/GUI-MAC-TEXT';text['attrs']['STEXT']='Sample'
            macro_destinations.save_options(app.data,'CATE',['CATALOG-DEST'])
            before=copy.deepcopy(app.data)
            win=catalog_macro_ui.export_macro(app);app.update()
            self.assertIn('/CATALOG-DEST',next(w for w in win.winfo_children() if isinstance(w,tk.Text)).get('1.0','end'))
            win.destroy();self.assertEqual(app.data,before)
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'sample.mac'
                path.write_bytes(catalog_macro.creation_text(app.data,cate['id']).replace('/GUI-MAC','/NEW-GUI-MAC').encode('cp932'))
                with patch('catalog_studio.catalog_macro_ui.filedialog.askopenfilename',return_value=str(path)):
                    catalog_macro_ui.import_macro(app);app.update()
                self.assertEqual(project.get(app.data,'cates',app.cate_id)['name'],'/NEW-GUI-MAC-CATE')
            app.registered_browser.edit_macro_destinations();app.update();app.grab_current().destroy()
        finally:app.destroy()
