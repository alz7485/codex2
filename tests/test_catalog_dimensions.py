import copy
import math
import tkinter as tk
import unittest
from types import SimpleNamespace
from catalog_studio import catalog_dimensions as dims,geometry_scene as geo,project

class CatalogDimensionTests(unittest.TestCase):
    def test_actual_world_measurements_not_pixels_and_invalid_layouts(self):
        mesh=geo.Mesh('one','one','SBOX',vertices=[(0,0,0),(120,50,30)])
        scene=geo.Scene(meshes=[mesh],actual=True,points={0:((0,0,0),(0,0,1),'P0'),1:((0,0,0),(1,0,0),'P1'),2:((120,0,0),(1,0,0),'P2')})
        rows=dims.measurements(scene)
        values={r['key']:r['value'] for r in rows}
        self.assertEqual(values,{'extent:X':120,'extent:Y':50,'extent:Z':30,'points:1:2':120})
        scene.actual=False;self.assertEqual(dims.measurements(scene),[])
        data=project.sample()
        for bad in ({'id':{'extent:X':[math.nan,0]}},{'id':{'extent:X':[3,0]}},{'id':{'bad':[0,0]}},[]):
            data[dims.KEY]=bad
            with self.assertRaises(ValueError):project.validate(data)

    def test_expression_keeps_operators_and_switches_only_param_names(self):
        from catalog_studio import catalog_param_dimensions as paramdims,presets
        from catalog_studio.valve_sample import prepare
        data,_=prepare(project.sample());scom=next(s for s in data['scoms'] if s['name']=='/SAMPLE-VALVE-80')
        definition=project.get(data,'definitions',scom['gmset_id'])
        parameter=presets.rules(data,definition)[0]
        view=SimpleNamespace(editor=SimpleNamespace(data=data,preview_scom_id=scom['id'],definition=lambda:definition),dimension_stext=SimpleNamespace(get=lambda:False))
        expr='PARAM 1 + 2 * PARAM 1'
        self.assertEqual(dims.description(view,{'expression':expr}),'PA1（'+presets.meaning(parameter)+'） + 2 * PA1（'+presets.meaning(parameter)+'）')
        data['texts'].append({'id':'text-test','type':'TEXT','parent_id':scom['cate_id'],'attrs':{'STEXT':'Nominal bore'},'parameter_text_source':{'preset_id':presets.selected_id(data,scom),'parameters':'P1'}})
        view.dimension_stext=SimpleNamespace(get=lambda:True)
        self.assertEqual(dims.description(view,{'expression':expr}),'PA1（Nominal bore） + 2 * PA1（Nominal bore）')
        self.assertEqual(paramdims.display_expression(view,'IPARAM 1 + PA2'),'IPARAM 1 + PA2')

    def test_geometry_click_filters_dimensions_without_changing_project_or_rotation(self):
        from catalog_studio.integrated import IntegratedStudio
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        try:
            s=next(s for s in app.data['scoms'] if s['name']=='/SAMPLE-VALVE-80')
            app.cate_id=s['cate_id'];app.scom_id=s['id'];app.switch('catalog');app.update()
            view=app.preview;before=copy.deepcopy(app.data)
            # Find a visible face away from dimension labels.
            candidate=None
            for points,ident in reversed(view.pick_faces):
                x=sum(p[0] for p in points)/len(points);y=sum(p[1] for p in points)/len(points)
                if not dims.hit(view,x,y) and view.pick_element(x,y)==ident:
                    candidate=(x,y,ident);break
            self.assertIsNotNone(candidate)
            x,y,ident=candidate;event=SimpleNamespace(x=x,y=y)
            view.press(event);view.release(event);app.update()
            self.assertEqual(view.editor.element_id,ident)
            self.assertTrue(all(r['element_id']==ident for r in view.dimension_measurements))
            self.assertEqual(app.data,before)
            view.press(event);view.move(SimpleNamespace(x=x+30,y=y+20));view.release(SimpleNamespace(x=x+30,y=y+20))
            self.assertEqual(view.editor.element_id,ident)
            view.dimension_lines.set(False);view.redraw();self.assertFalse(view.dimension_items)
            view.press(SimpleNamespace(x=5,y=90));view.release(SimpleNamespace(x=5,y=90))
            self.assertIsNone(view.editor.element_id);self.assertFalse(view.dimension_items)
            view.dimension_lines.set(True);view.redraw();self.assertGreater(len(view.dimension_measurements),1)
            self.assertEqual(app.data,before)
        finally:app.destroy()

    def test_drag_moves_only_annotation_commits_on_release_and_roundtrips(self):
        import tempfile
        from pathlib import Path
        from catalog_studio.integrated import IntegratedStudio
        try:app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        errors=[];app.report_callback_exception=lambda k,v,t:errors.append(str(v))
        try:
            s=next(s for s in app.data['scoms'] if s['name']=='/SAMPLE-VALVE-80')
            app.cate_id=s['cate_id'];app.scom_id=s['id'];app.switch('catalog');app.update()
            view=app.preview;self.assertTrue(view.actual);self.assertGreater(len(view.dimension_items),0)
            rows=view.dimension_measurements
            diameter=next(r for r in rows if r['diameter'])
            key=diameter['key']
            self.assertTrue(view.dimension_items[key]['label'].startswith('⌀'))
            self.assertNotIn('対応STEXTなし',view.dimension_items[key]['label'])
            view.dimension_buttons['stext'].invoke();app.update()
            self.assertIn(dims.description(view,diameter),view.dimension_items[key]['label'])
            view.dimension_buttons['stext'].invoke();app.update()
            self.assertIn('（',view.dimension_items[key]['label'].split('\n')[1])
            view.dimension_buttons['visible'].invoke();app.update()
            self.assertFalse(view.dimension_items)
            view.dimension_buttons['visible'].invoke();app.update()
            app.catalog_tab='members';app.catalog_member_key='texts:missing';view.redraw()
            self.assertIn(key,view.dimension_items)
            before=copy.deepcopy(app.data);yaw=view.camera.yaw
            item=view.dimension_items[key]['text'];x,y=view.canvas.coords(item)
            view.canvas.event_generate('<Button-1>',x=round(x),y=round(y));app.update()
            self.assertIsNotNone(view.dimension_drag)
            view.canvas.event_generate('<B1-Motion>',x=round(x+25),y=round(y-22));app.update()
            self.assertEqual(app.data,before);self.assertEqual(view.camera.yaw,yaw)
            view.canvas.event_generate('<ButtonRelease-1>',x=round(x+25),y=round(y-22));app.update()
            self.assertIn(key,app.data[dims.KEY][s['id']])
            remaining=copy.deepcopy(app.data);remaining.pop(dims.KEY)
            self.assertEqual(remaining,before)
            with tempfile.TemporaryDirectory() as t:
                path=Path(t)/'dimensions.json';project.save(app.data,path);loaded=project.load(path)
                self.assertEqual(loaded[dims.KEY],app.data[dims.KEY])
            stored=copy.deepcopy(app.data)
            item=view.dimension_items[key]['text'];x,y=view.canvas.coords(item)
            view.press(SimpleNamespace(x=x,y=y));view.move(SimpleNamespace(x=x+40,y=y+10));view.cancel()
            self.assertEqual(app.data,stored);self.assertIsNone(view.dimension_drag)
            view.mode.set('仮サイズ');view.mode_changed();app.update()
            self.assertFalse(view.dimension_items);self.assertFalse(view.canvas.find_withtag('catalog-dimension'))
            view.mode.set('SCOM 実寸');view.mode_changed();app.update()
            self.assertIn(key,view.dimension_items)
            view.view_buttons['XY'].invoke();app.update()
            self.assertAlmostEqual(next(r['value'] for r in view.dimension_measurements if r['key']==key),diameter['value'])
            self.assertEqual(app.data,stored);self.assertEqual(errors,[])
        finally:app.destroy()
