import copy
import tkinter as tk
import unittest
from catalog_studio import project,presets,pairing
from catalog_studio.catalog_bundle_ui import linked_selection,prepare

class CatalogueLinkTests(unittest.TestCase):
    def sample(self):
        data=project.sample();p=presets.add(data,'Link test',empty=True)
        p['parameters']=[{'id':'P1','role':'BORE','unit':'mm','english_name':'BORE'}]
        pt={'id':'link-pt','kind':'PTSET','name':'/LINK-PT','revision':'01','elements':[],'parameter_preset_id':p['id']}
        gm={'id':'link-gm','kind':'GMSET','name':'/LINK-GM','revision':'01','elements':[],'parameter_preset_id':p['id'],pairing.PAIR_KEY:pt['id']}
        data['definitions'].extend([pt,gm]);return data,p,pt,gm

    def test_bidirectional_links_and_mismatch_atomicity(self):
        data,p,pt,gm=self.sample();before=copy.deepcopy(data)
        for kind,r in (('PTSET',pt),('GMSET',gm)):
            a,b,c,options=linked_selection(data,kind,r['id'])
            self.assertEqual((a,b,c),(pt['id'],gm['id'],p['id']))
        self.assertEqual(data,before)
        result,records,_=prepare(data,p['id'],ptset_id=pt['id'],gmset_id=gm['id'])
        self.assertEqual(records['SCOM']['ptset_id'],pt['id']);self.assertEqual(records['SCOM']['gmset_id'],gm['id'])
        with self.assertRaises(ValueError):prepare(data,'',ptset_id=pt['id'],gmset_id=gm['id'])
        self.assertEqual(data,before)
        second=copy.deepcopy(gm);second.update(id='second-gm',name='/SECOND-GM');data['definitions'].append(second)
        a,b,c,options=linked_selection(data,'PTSET',pt['id'])
        self.assertEqual(b,'');self.assertEqual(len(options),2)
        self.assertEqual(linked_selection(data,'PTSET',pt['id'],second['id'])[1],second['id'])

    def test_canvas_is_shared_renders_valve_and_does_not_modify_definitions(self):
        from catalog_studio.integrated import IntegratedStudio
        from catalog_studio.geometry_canvas import GeometryCanvas
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        errors=[];app.report_callback_exception=lambda k,v,t:errors.append(str(v))
        try:
            s=next(s for s in app.data['scoms'] if s['name']=='/SAMPLE-VALVE-80')
            app.cate_id=s['cate_id'];app.scom_id=s['id'];app.switch('catalog');app.update()
            view=app.preview;self.assertIsInstance(view,GeometryCanvas)
            self.assertGreater(len(view.scene.meshes),0)
            before=copy.deepcopy(app.data)
            old=(view.camera.yaw,view.camera.pitch)
            for event,x,y in (('<Button-1>',100,100),('<B1-Motion>',140,125),('<ButtonRelease-1>',140,125)):
                view.canvas.event_generate(event,x=x,y=y)
            app.update();self.assertNotEqual(old,(view.camera.yaw,view.camera.pitch))
            view.view_buttons['XY'].invoke();view.zoom(1.1);view.fit_all();app.update()
            view.focus_button.invoke();app.update();self.assertEqual(len(app.catalog_panes.panes()),1)
            view.focus_button.invoke();app.update();self.assertEqual(len(app.catalog_panes.panes()),2)
            view.open_details();app.update();view.close_details();app.update()
            self.assertEqual(app.data,before);self.assertEqual(errors,[])
        finally:app.destroy()

    def test_dialog_selection_updates_both_directions(self):
        from catalog_studio.integrated import IntegratedStudio
        from catalog_studio.catalog_bundle_ui import open_bundle
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        try:
            data,p,pt,gm=self.sample();data['active_parameter_preset_id']=p['id']
            app.data=data;app.cate_id=data['cates'][0]['id'];app.scom_id=None;app.switch('catalog');app.update()
            win=open_bundle(app);app.update()
            for combo,name,other,other_name in ((win.ptset_choice,pt['name'],win.gmset_choice,gm['name']), (win.gmset_choice,gm['name'],win.ptset_choice,pt['name'])):
                combo.set(name);combo.event_generate('<<ComboboxSelected>>');app.update()
                self.assertEqual(other.get(),other_name);self.assertEqual(win.preset_choice.get(),p['name'])
                self.assertEqual(str(win.create_button['state']),'normal')
            win.create_button.invoke();app.update()
            self.assertEqual(data['scoms'][-1]['ptset_id'],pt['id']);self.assertEqual(data['scoms'][-1]['gmset_id'],gm['id'])
        finally:app.destroy()
