import copy
import tempfile
import tkinter as tk
import unittest
from fractions import Fraction
from pathlib import Path
from catalog_studio import element_schema as schema, expressions, project
from catalog_studio.integrated import IntegratedStudio
from catalog_studio.point_geometry import Camera, PLANES, axis_vector, formula, placement, position


class PointGeometryTests(unittest.TestCase):
    def test_projection_roundtrip_for_all_planes_and_views(self):
        camera=Camera()
        for plane in PLANES:
            for front in (False,True):
                if front:camera.face(plane)
                else:camera.yaw=40;camera.pitch=30
                point=[.5,-.5,.25];fixed=point[next(i for i in range(3) if i not in PLANES[plane])]
                x,y=camera.project(point,700,500);result=camera.unproject(x,y,700,500,plane,fixed)
                for actual,expected in zip(result,point):self.assertAlmostEqual(actual,expected)
    def test_edge_on_plane_is_reported(self):
        camera=Camera();camera.yaw=camera.pitch=0
        with self.assertRaises(ValueError):camera.unproject(300,250,700,500,'XY')
    def test_fractional_coordinates_are_parameter_expressions(self):
        for coefficient in (Fraction(-1,2),Fraction(2,3),Fraction(1),Fraction(0)):
            text=formula('P3',coefficient)
            self.assertEqual(expressions.evaluate(text,{'PARAM':{'P3':120}}),float(coefficient)*120)
        self.assertEqual(formula('P3',Fraction(-1,2)),'-PARAM[3] / 2')
    def test_signed_axial_placement_and_aliases(self):
        attrs=placement('PTAXI',(Fraction(-1,2),Fraction(1),Fraction(0)),'P3','-X')
        self.assertEqual(attrs,{'PDIS':'PARAM[3] / 2'})
        self.assertEqual(axis_vector('W'),(-1,0,0));self.assertEqual(axis_vector('U'),(0,0,1))
    def test_planar_move_changes_only_the_two_position_fields(self):
        attrs=placement('PTMIX',(Fraction(1),Fraction(1,2),Fraction(3,4)),'P3',plane='XY')
        self.assertEqual(attrs,{'PX':'PARAM[3]','PY':'PARAM[3] / 2'})
        self.assertNotIn('PAXI',attrs);self.assertNotIn('PZ',attrs)
    def test_unsupported_position_and_axis_are_not_guessed(self):
        with self.assertRaises(ValueError):position({'type':'PTPOS','attrs':{'PTCPOS':'original'}},{},{},[])
        with self.assertRaises(ValueError):axis_vector('X45U')
        with self.assertRaises(ValueError):placement('PTAXI',(0,1,0),'P3','X',plane='YZ')
    def test_position_evaluates_against_component_context(self):
        point={'type':'PTAXI','attrs':{'PAXI':'-X','PDIS':'PARAM 3 / 2'}}
        self.assertEqual(position(point,{'PARAM':{'P3':100}},{},[]),(-50,0,0))
        self.assertEqual(position(point,{'PARAM':{'P3':200}},{},[]),(-100,0,0))


class PointCanvasGuiTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest('GUI display unavailable: '+str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.update()
        self.editor=self.app.geometry_editor;self.editor.definition()['elements']=[]
        self.point=schema.add_element(self.editor.definition(),'PTCAR')
        self.point['attrs'].update(PX='PARAM 3 / 2',PY='0',PZ='PARAM 3 / 4',PTCDIR='-Y')
        self.editor.refresh();self.editor.open_point_canvas();self.app.update();self.view=self.editor.point_canvas
        self.view.face();self.app.update()
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def pixels(self,point):
        return tuple(round(v) for v in self.view.camera.project(point,self.view.canvas.winfo_width(),self.view.canvas.winfo_height()))
    def click(self,point):
        x,y=self.pixels(point);self.view.canvas.event_generate('<Button-1>',x=x,y=y);self.view.canvas.event_generate('<ButtonRelease-1>',x=x,y=y);self.app.update()
    def test_mouse_addition_is_preview_until_apply_and_saves_expressions(self):
        before=copy.deepcopy(self.editor.definition());self.view.mode.set('点を追加');self.click((1,-.5,0))
        self.assertEqual(self.editor.definition(),before);self.assertIsNotNone(self.view.pending)
        self.view.apply_button.invoke();self.app.update();new=self.editor.element()
        self.assertEqual(new['type'],'PTCAR');self.assertEqual(new['attrs']['PX'],'PARAM[3]');self.assertEqual(new['attrs']['PY'],'-PARAM[3] / 2')
        self.assertEqual(self.editor.elements.selection(),(new['id'],));self.assertEqual(new['attrs']['NUMB'],'2')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'points.json';project.save(self.app.data,path);loaded=project.load(path)
            point=project.get(loaded,'definitions',self.editor.definition_id)['elements'][-1]
            self.assertEqual(point['attrs'],new['attrs'])
        self.assertEqual(self.errors,[])
    def test_cancelled_placement_does_not_create_a_point(self):
        before=copy.deepcopy(self.app.data);self.view.mode.set('点を追加');self.click((.5,.5,0));self.view.cancel();self.app.update()
        self.assertEqual(self.app.data,before);self.assertIsNone(self.view.pending);self.assertEqual(self.errors,[])
    def test_drag_preserves_other_coordinate_direction_and_point_type(self):
        original=copy.deepcopy(self.point['attrs']);x,y=self.pixels((.5,0,.25));tx,ty=self.pixels((1,.5,.25))
        self.view.canvas.event_generate('<Button-1>',x=x,y=y);self.view.canvas.event_generate('<B1-Motion>',x=tx,y=ty);self.view.canvas.event_generate('<ButtonRelease-1>',x=tx,y=ty);self.app.update()
        self.assertEqual(self.point['attrs'],original);self.view.apply_button.invoke();self.app.update()
        self.assertEqual(self.point['attrs']['PX'],'PARAM[3]');self.assertEqual(self.point['attrs']['PY'],'PARAM[3] / 2')
        self.assertEqual(self.point['attrs']['PZ'],original['PZ']);self.assertEqual(self.point['attrs']['PTCDIR'],'-Y');self.assertEqual(self.point['type'],'PTCAR')
        self.assertEqual(self.errors,[])
    def test_stale_proposal_cannot_overwrite_attribute_edit(self):
        x,y=self.pixels((.5,0,.25));tx,ty=self.pixels((1,0,.25))
        self.view.canvas.event_generate('<Button-1>',x=x,y=y);self.view.canvas.event_generate('<B1-Motion>',x=tx,y=ty);self.app.update()
        self.editor.tables['main'].selection_set('PX');self.app.update();self.editor.expression.set('PARAM 3 / 3');self.app.update()
        self.view.apply_button.invoke();self.app.update()
        self.assertEqual(self.point['attrs']['PX'],'PARAM 3 / 3');self.assertIn('属性が変更',self.view.note['text']);self.assertEqual(self.errors,[])
    def test_selection_and_manual_attribute_edits_update_canvas(self):
        other=schema.add_element(self.editor.definition(),'PTAXI');other['attrs'].update(PAXI='-X',PDIS='PARAM 3')
        self.editor.refresh();self.app.update();self.click((-1,0,0))
        self.assertEqual(self.editor.element_id,other['id']);self.assertEqual(self.editor.elements.selection(),(other['id'],))
        self.editor.tables['main'].selection_set('PDIS');self.app.update();self.editor.expression.set('PARAM 3 / 2');self.app.update()
        self.assertEqual(self.view.positions[other['id']],(-.5,0,0));self.assertEqual(self.errors,[])
    def test_rotation_zoom_and_navigation_do_not_edit_data(self):
        before=copy.deepcopy(self.app.data);self.view.canvas.event_generate('<Button-3>',x=200,y=200);self.view.canvas.event_generate('<B3-Motion>',x=240,y=230);self.view.zoom(1.2);self.app.update()
        self.assertNotEqual(self.view.camera.yaw,0);self.assertEqual(self.app.data,before)
        win=self.view;self.app.switch('gmset');self.app.update();self.assertFalse(win.winfo_exists());self.assertEqual(self.errors,[])
