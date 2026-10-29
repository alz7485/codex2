"""Synthetic fixtures for the observed ALP shapes; no private macro copies."""
import copy
import unittest
from catalog_studio import project,catalog_macro,catalog_inspector

CATE="""INPUT BEGIN
NEW CATEGORY /TEST-IMPORT-CATE
PURP COMP
NEW SDTEXT /TEST-IMPORT-SDTE
SKEY 'TEST'
TTEX 'RED'
END
NEW TEXT /TEST-IMPORT-P1
STEX ' NOM BORE 1 '
END
NEW SCOMPONENT /TEST-IMPORT-SCOM
GTYP REDU
PARA 40 10 SAMPLE 42.5 $
36 7.5 $
12 3
END
END
OLD CATEGORY /TEST-IMPORT-CATE
LOCK
OLD SDTEXT /TEST-IMPORT-SDTE
LOCK
OLD TEXT /TEST-IMPORT-P1
LOCK
OLD SCOMPONENT /TEST-IMPORT-SCOM
PTRE PTSET /TEST-EXTERNAL-PT
GMRE GMSET /TEST-EXTERNAL-GM
LOCK
INPUT END CATEGORY /TEST-IMPORT-CATE
INPUT FINISH
"""
PROP="""INPUT BEGIN
NEW CMPTYPE /TEST-PROP
NEW CMPDATA /TEST-PROP-DATA
CWEI ( 4.25 )
END
NEW CMPDATA /TEST-PROP-DATA-2
CWEI ( 6.5 )
END
END
INPUT END CMPTYPE /TEST-PROP
INPUT FINISH
"""
DETAIL="""INPUT BEGIN
NEW SDTEXT /TEST-DETAIL
SKEY 'TST1'
RTEX ' VALVE   SAMPLE    BW  BW '
END
OLD SDTEXT /TEST-DETAIL
LOCK
INPUT END SDTEXT /TEST-DETAIL
INPUT FINISH
"""

class CatalogueAlpTests(unittest.TestCase):
    def test_cate_words_continuations_post_creation_refs_and_roundtrip(self):
        data=project.sample();before=copy.deepcopy(data)
        result,ids=catalog_macro.import_text(data,CATE)
        self.assertEqual(before,data)
        cate=project.get(result,'cates',ids[0]);self.assertEqual(cate['attrs']['PURP'],'COMP')
        s=next(r for r in result['scoms'] if r['cate_id']==ids[0])
        self.assertEqual(s['values']['P3'],'SAMPLE');self.assertEqual(s['values']['P8'],3)
        self.assertEqual(s['ptset_id'],'/TEST-EXTERNAL-PT');self.assertTrue(s['macro_locked'])
        text=next(r for r in result['texts'] if r['name']=='/TEST-IMPORT-P1')
        self.assertEqual(text['attrs']['STEXT'],' NOM BORE 1 ')
        out=catalog_macro.creation_text(result,ids[0]);r2,ids2=catalog_macro.import_text(data,out)
        self.assertEqual(project.get(r2,'cates',ids2[0])['attrs'],cate['attrs'])
        self.assertEqual(next(r for r in r2['scoms'] if r['cate_id']==ids2[0])['values'],s['values'])
        self.assertNotIn('LOCK',out);self.assertNotIn('OLD ',out)
        catalog_inspector.edit_value(result,'scoms',s['id'],('attrs','GTYP'),'VALV')
        self.assertEqual(s['attrs']['GTYP'],'VALV')
        # Existing definitions resolve by name without altering their preset.
        data['definitions'][0].update(name='/TEST-EXTERNAL-PT',kind='PTSET')
        resolved,_=catalog_macro.import_text(data,CATE)
        self.assertEqual(resolved['scoms'][-1]['ptset_id'],data['definitions'][0]['id'])

    def test_prop_detail_preserve_hierarchy_and_edit_values(self):
        data=project.sample();owner=data['cates'][0]['id']
        imported,ids=catalog_macro.import_text(data,PROP,owner)
        prop=project.get(imported,'catalog_props',ids[0])
        self.assertEqual(prop['e3d_type'],'CMPTYPE');self.assertEqual(len(prop['children']),2)
        self.assertEqual(prop['cate_id'],owner)
        catalog_inspector.edit_value(imported,'catalog_props',prop['id'],('children',0,'attrs','CWEI'),'8.25')
        self.assertEqual(prop['children'][0]['attrs']['CWEI'],8.25)
        before=copy.deepcopy(imported)
        with self.assertRaises(ValueError):catalog_inspector.edit_value(imported,'catalog_props',prop['id'],('children',0,'attrs','CWEI'),'"bad"')
        self.assertEqual(before,imported)
        result,ids=catalog_macro.import_text(imported,DETAIL,owner)
        detail=project.get(result,'catalog_details',ids[0])
        self.assertEqual(detail['attrs']['RTEX'],' VALVE   SAMPLE    BW  BW ')
        self.assertTrue(detail['macro_locked']);self.assertEqual(detail['e3d_type'],'SDTE')
        project.validate(result)

    def test_bad_commands_duplicate_unknown_selectors_wrappers_are_atomic(self):
        data=project.sample();before=copy.deepcopy(data)
        invalid=[CATE.replace('LOCK','DELETE ALL',1),CATE.replace('OLD CATEGORY /TEST-IMPORT-CATE','OLD CATEGORY /PREEXISTING'),
                 CATE.replace('INPUT END CATEGORY /TEST-IMPORT-CATE','INPUT END CATEGORY /WRONG'),
                 CATE.replace('PTRE PTSET','PTRE GMSET'),PROP.replace('4.25','1e999'),
                 PROP.replace('/TEST-PROP-DATA-2','/TEST-PROP-DATA'),DETAIL.replace("'TST1'","'broken"),
                 CATE.replace('12 3\n','12 3 $\n'),CATE.replace('END\nEND\n','END\n',1)]
        for source in invalid:
            with self.subTest(source=source[-80:]):
                with self.assertRaises(ValueError):catalog_macro.import_text(data,source)
                self.assertEqual(data,before)
        loaded,_=catalog_macro.import_text(data,PROP)
        with self.assertRaises(ValueError):catalog_macro.import_text(loaded,PROP)

    def test_gui_reads_three_files_and_selects_editable_record(self):
        import tkinter as tk
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from catalog_studio.integrated import IntegratedStudio
        from catalog_studio.catalog_macro_ui import import_macro
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        errors=[];app.report_callback_exception=lambda k,v,t:errors.append(str(v))
        try:
            app.switch('catalog');app.update()
            with tempfile.TemporaryDirectory() as temp:
                for i,source in enumerate((CATE,PROP,DETAIL)):
                    path=Path(temp)/f'part{i}.mac';path.write_bytes(source.replace('\n','\r\n').encode('cp932'))
                    with patch('catalog_studio.catalog_macro_ui.filedialog.askopenfilename',return_value=str(path)),patch('catalog_studio.catalog_macro_ui.messagebox.showerror') as error:
                        import_macro(app);app.update();error.assert_not_called()
                    self.assertTrue(app.catalog_inspector.fields)
                    target=app.catalog_inspector.targets()[0]
                    self.assertEqual(target[0],('cates','catalog_props','catalog_details')[i])
                    if i==1:
                        path=('children',0,'attrs','CWEI')
                        row=next(k for k,v in app.catalog_inspector.fields.items() if v[2]==path)
                        app.catalog_inspector.begin(row);app.catalog_inspector.editing['variable'].set('7.75')
                        self.assertTrue(app.catalog_inspector.finish());app.update()
                        self.assertEqual(target[1]['children'][0]['attrs']['CWEI'],7.75)
                out=Path(temp)/'project.json';project.save(app.data,out)
                loaded=project.load(out)
                self.assertEqual(loaded['catalog_props'][-1]['children'][0]['attrs']['CWEI'],7.75)
            # An unassociated standalone DETAIL is still visible and editable.
            result,ids=catalog_macro.import_text(app.data,DETAIL.replace('/TEST-DETAIL','/UNASSOCIATED'))
            app.data=result;app.cate_id='';app.scom_id=None;app.catalog_tab='members'
            app.catalog_member_key='catalog_details:'+ids[0];app.registered_browser.catalog_target=app.catalog_member_key
            app.render_page();app.update()
            self.assertTrue(app.registered_browser.tree.exists(app.catalog_member_key))
            self.assertEqual(app.catalog_inspector.targets()[0][1]['id'],ids[0])
            self.assertEqual(errors,[])
        finally:app.destroy()
