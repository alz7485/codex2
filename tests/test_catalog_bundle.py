import copy
import tkinter as tk
import unittest
from catalog_studio import project,presets,browser_folders
from catalog_studio.catalog_bundle_ui import prepare

class CatalogBundleTests(unittest.TestCase):
    def source(self):
        data=project.sample();preset=presets.add(data,'Synthetic bundle',empty=True)
        preset['parameters']=[{'id':'P1','role':'BORE','unit':'mm','english_name':'NOM BORE'}, {'id':'P3','role':'LENGTH','unit':'mm','english_name':'LENGTH'}]
        import uuid
        pt={'id':uuid.uuid4().hex,'name':'/BUNDLE-PT','kind':'PTSET','revision':'01','elements':[],'parameter_preset_id':preset['id']}
        gm={'id':uuid.uuid4().hex,'name':'/BUNDLE-GM','kind':'GMSET','revision':'01','elements':[],'parameter_preset_id':preset['id'],'paired_ptset_id':pt['id']}
        data['definitions'].extend([pt,gm])
        return data,preset

    def test_prepare_exact_contents_preset_and_atomic_errors(self):
        data,preset=self.source();folder=browser_folders.add(data,'catalog','Parts')
        before=copy.deepcopy(data);candidate,r,rows=prepare(data,preset['id'],'folder:'+folder)
        self.assertEqual(data,before)
        self.assertEqual(len(candidate['cates'])-len(data['cates']),1)
        self.assertEqual(len(candidate['scoms'])-len(data['scoms']),1)
        self.assertEqual(len(candidate['texts'])-len(data['texts']),3)
        self.assertEqual(len(r['TEXT']),2);self.assertEqual(r['SCOM']['parameter_preset_id'],preset['id'])
        self.assertEqual(r['SCOM']['gmset_id'],'');self.assertEqual(r['SCOM']['ptset_id'],'')
        self.assertEqual([t['attrs']['STEXT'] for t in r['TEXT']],['NOM BORE','LENGTH'])
        self.assertEqual(r['SDTE']['parent_id'],r['CATE']['id'])
        self.assertEqual(r['SCOM']['cate_id'],r['CATE']['id'])
        self.assertEqual(candidate['browser_placements']['catalog|cates:'+r['CATE']['id']],folder)
        self.assertEqual(candidate.get('catalog_props',[]),data.get('catalog_props',[]))
        self.assertEqual(candidate.get('catalog_details',[]),data.get('catalog_details',[]))
        preset['parameters'][0]['english_name']='';before=copy.deepcopy(data)
        with self.assertRaises(ValueError):prepare(data,preset['id'])
        self.assertEqual(data,before)
        with self.assertRaises(ValueError):prepare(data,'missing')

    def test_menu_cancel_and_create(self):
        from catalog_studio.integrated import IntegratedStudio
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        errors=[];app.report_callback_exception=lambda k,v,t:errors.append(str(v))
        try:
            data,preset=self.source();data['active_parameter_preset_id']=preset['id']
            app.data=data;app.cate_id=data['cates'][0]['id'];app.scom_id=None;app.switch('catalog');app.update()
            b=app.registered_browser
            self.assertEqual([b.cate_menu.entrycget(i,'label') for i in (0,1)],['CATE一式作成','CATE作成'])
            before=copy.deepcopy(data);b.cate_menu.invoke(0);app.update();app.grab_current().destroy()
            self.assertEqual(data,before)
            b.cate_menu.invoke(0);app.update();window=app.grab_current()
            self.assertEqual(str(window.create_button['state']),'normal')
            window.create_button.invoke();app.update()
            self.assertEqual(len(data['cates'])-len(before['cates']),1)
            self.assertEqual(len(data['scoms'])-len(before['scoms']),1)
            self.assertEqual(len(data['texts'])-len(before['texts']),3)
            self.assertEqual(data['scoms'][-1]['ptset_id'],next(d['id'] for d in data['definitions'] if d['name']=='/BUNDLE-PT'))
            self.assertEqual(data['scoms'][-1]['gmset_id'],next(d['id'] for d in data['definitions'] if d['name']=='/BUNDLE-GM'))
            self.assertEqual(b.tree.selection(),('cates:'+app.cate_id,))
            count=len(data['cates']);b.cate_menu.invoke(1);app.update()
            self.assertIsNone(app.grab_current());self.assertEqual(len(data['cates']),count+1)
            # All buttons fit in one sidebar row.
            self.assertLessEqual(b.macro_button.winfo_x()+b.macro_button.winfo_width(),b.winfo_width())
            self.assertEqual(errors,[])
        finally:app.destroy()
