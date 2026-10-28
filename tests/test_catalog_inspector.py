import copy
import tkinter as tk
import unittest
from catalog_studio import catalog_workspace,project,presets
from catalog_studio.catalog_inspector import edit_value
from catalog_studio.catalog_text_batch import prepare,open_batch
from catalog_studio.integrated import IntegratedStudio


class InspectorTests(unittest.TestCase):
    def sample(self):
        data=project.sample()
        return catalog_workspace.prepare_bundle(data,'/INSPECT',rtex='Description',stext='Old text')

    def test_cell_edits_preserve_ids_references_and_reject_invalid_values(self):
        data,records=self.sample();s=records['SCOM'];ident=s['id']
        edit_value(data,'texts',records['TEXT']['id'],('attrs','STEXT'),'Changed')
        self.assertEqual(records['TEXT']['attrs']['STEXT'],'Changed')
        edit_value(data,'scoms',ident,('name',),'/RENAMED')
        self.assertEqual(s['id'],ident)
        s['gmset_id']='unknown-reference'
        edit_value(data,'scoms',ident,('size',),'80')
        self.assertEqual(s['gmset_id'],'unknown-reference')
        s.setdefault('component_attrs',{})['custom']=True
        edit_value(data,'scoms',ident,('component_attrs','custom'),'false')
        self.assertIs(s['component_attrs']['custom'],False)
        before=copy.deepcopy(data)
        with self.assertRaises(ValueError):edit_value(data,'scoms',ident,('values','P1'),'invalid-number')
        self.assertEqual(data,before)
        with self.assertRaises(ValueError):edit_value(data,'cates',records['CATE']['id'],('name',),'/RENAMED')
        self.assertEqual(data,before)

    def test_preset_batch_is_atomic_and_does_not_overwrite(self):
        data,records=self.sample();source=presets.rules(data)
        for p in source:p['english_name']='Meaning '+p['id']
        before=copy.deepcopy(data)
        rows,created=prepare(data,records['CATE']['id'],'')
        self.assertEqual(len(created),len(source));self.assertEqual(data,before)
        self.assertEqual(created[0]['attrs']['STEXT'],source[0]['english_name'])
        data['texts'].extend(created);before=copy.deepcopy(data)
        with self.assertRaises(ValueError):prepare(data,records['CATE']['id'],'')
        self.assertEqual(data,before)

    def test_click_edit_selection_and_batch_dialog(self):
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        errors=[];app.report_callback_exception=lambda k,v,t:errors.append(str(v))
        try:
            data,records=self.sample();app.data=data;app.cate_id=records['CATE']['id'];app.scom_id=records['SCOM']['id'];app.switch('catalog');app.update()
            app.catalog_tree.selection_set('texts:'+records['TEXT']['id']);app.update();view=app.catalog_inspector
            self.assertTrue(view.winfo_ismapped());self.assertFalse(app.catalog_members.winfo_ismapped())
            iid=next(i for i,f in view.fields.items() if f[2]==('attrs','STEXT'))
            view.tree.see(iid);app.update();box=view.tree.bbox(iid,'value')
            view.tree.event_generate('<ButtonRelease-1>',x=box[0]+10,y=box[1]+10);app.update()
            self.assertIsNotNone(view.editing)
            view.editing['variable'].set('Changed in cell');self.assertTrue(view.finish());app.update()
            self.assertEqual(records['TEXT']['attrs']['STEXT'],'Changed in cell')
            for p in presets.rules(data):p['english_name']='English '+p['id']
            before=copy.deepcopy(data);window=open_batch(app);app.update();window.destroy();self.assertEqual(data,before)
            window=open_batch(app);app.update();window.create_button.invoke();app.update()
            self.assertEqual(len(data['texts'])-len(before['texts']),len(presets.rules(data)))
            self.assertTrue(all(r['parent_id']==records['CATE']['id'] for r in data['texts'] if 'parameter_text_source' in r))
            self.assertEqual(errors,[])
        finally:app.destroy()
