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
            values={r['key']:r['value'] for r in view.dimension_measurements}
            self.assertAlmostEqual(values['extent:X'],240)
            self.assertAlmostEqual(values['points:1:2'],240)
            before=copy.deepcopy(app.data);yaw=view.camera.yaw
            key='extent:X';item=view.dimension_items[key]['text'];x,y=view.canvas.coords(item)
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
            self.assertAlmostEqual(next(r['value'] for r in view.dimension_measurements if r['key']=='extent:X'),240)
            self.assertEqual(app.data,stored);self.assertEqual(errors,[])
        finally:app.destroy()
