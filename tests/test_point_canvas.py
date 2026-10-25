import copy
import tempfile
import tkinter as tk
import unittest
from fractions import Fraction
from pathlib import Path
from catalog_studio import element_schema as schema, expressions, project
from catalog_studio.integrated import IntegratedStudio
from catalog_studio.point_geometry import Camera, PLANES, LAYOUT_KEY, DIMENSIONS_KEY, axis_vector, formula, placement, position, schematic_placement, schematic_position


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
    def create(self,point,kind='PTCAR'):
        self.click(point);self.assertTrue(self.view.context_menu.winfo_ismapped())
        self.view.create_menu.invoke(list(schema.PT_TYPES).index(kind));self.app.update()

    def test_blank_click_menu_creates_selected_kind_at_clicked_position(self):
        before=copy.deepcopy(self.editor.definition());self.click((1,-.53,0))
        self.assertEqual(self.editor.definition(),before);self.assertIsNone(self.view.pending)
        self.assertEqual(self.view.context_menu.entrycget(0,'label'),'点を作成')
        self.view.create_menu.invoke(1);self.app.update();new=self.editor.element()
        self.assertEqual(new['type'],'PTCAR');self.assertEqual(new['attrs']['PX'],'');self.assertEqual(new['attrs']['PY'],'')
        self.assertEqual(new['attrs']['PZ'],'0');self.assertEqual(new['attrs']['PTCDIR'],'X')
        self.assertAlmostEqual(new[LAYOUT_KEY][1],-.53,delta=.01)
        self.assertEqual(self.editor.elements.selection(),(new['id'],));self.assertEqual(new['attrs']['NUMB'],'2')
        self.assertEqual(schema.missing_fields(new),('PX','PY'));self.assertFalse(self.view.context_menu.winfo_ismapped())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'points.json';project.save(self.app.data,path);loaded=project.load(path)
            point=project.get(loaded,'definitions',self.editor.definition_id)['elements'][-1]
            self.assertEqual(point,new)
        self.assertEqual(self.errors,[])

    def test_cancelled_menu_does_not_create_a_point(self):
        before=copy.deepcopy(self.app.data);self.click((.5,.5,0));self.view.context_menu.invoke(2);self.app.update()
        self.assertEqual(self.app.data,before);self.assertIsNone(self.view.pending)
        self.assertFalse(self.view.context_menu.winfo_ismapped());self.assertIsNone(self.view.menu_context);self.assertEqual(self.errors,[])

    def drag(self,target,release=True):
        x,y=self.pixels(self.view.positions[self.point['id']]);tx,ty=self.pixels(target)
        self.view.canvas.event_generate('<Button-1>',x=x,y=y);self.view.canvas.event_generate('<B1-Motion>',x=tx,y=ty)
        if release:self.view.canvas.event_generate('<ButtonRelease-1>',x=tx,y=ty)
        self.app.update()

    def test_click_only_selects_and_drag_commits_on_release(self):
        original=copy.deepcopy(self.point);self.click(self.view.positions[self.point['id']])
        self.assertEqual(self.editor.element_id,self.point['id']);self.assertEqual(self.point,original)
        self.assertFalse(self.view.context_menu.winfo_ismapped())
        self.drag((1,.53,.8),release=False);self.assertEqual(self.point,original)
        self.view.canvas.event_generate('<ButtonRelease-1>',x=0,y=0);self.app.update()
        self.assertEqual(self.point['attrs']['PX'],original['attrs']['PX']);self.assertEqual(self.point['attrs']['PY'],'0')
        self.assertEqual(self.point['attrs']['PZ'],original['attrs']['PZ']);self.assertEqual(self.point['attrs']['PTCDIR'],'-Y')
        self.assertIn(LAYOUT_KEY,self.point);self.assertIsNone(self.view.pending);self.assertEqual(self.errors,[])

    def test_drag_keeps_canvas_stable_and_escape_cancels_before_release(self):
        before=copy.deepcopy(self.app.data);size=(self.view.canvas.winfo_width(),self.view.canvas.winfo_height())
        self.drag((1,.5,.8),release=False)
        self.assertEqual((self.view.canvas.winfo_width(),self.view.canvas.winfo_height()),size)
        self.assertEqual(self.view.pending['attrs'],{})
        self.view.canvas.event_generate('<Escape>');self.app.update();self.view.canvas.event_generate('<ButtonRelease-1>',x=0,y=0);self.app.update()
        self.assertEqual(self.app.data,before);self.assertIsNone(self.view.pending);self.assertEqual(self.errors,[])

    def test_stale_drag_cannot_overwrite_attribute_edit(self):
        self.drag((1,0,.8),release=False);self.editor.tables['main'].selection_set('PX');self.app.update()
        self.editor.expression.set('PARAM 3 / 3');self.app.update()
        self.view.canvas.event_generate('<ButtonRelease-1>',x=0,y=0);self.app.update()
        self.assertEqual(self.point['attrs']['PX'],'PARAM 3 / 3');self.assertIn('属性・配置が変更',self.view.note['text']);self.assertEqual(self.errors,[])

    def test_distance_edits_follow_the_older_point_but_scom_values_do_not_change_the_layout(self):
        other=schema.add_element(self.editor.definition(),'PTAXI');other['attrs'].update(PAXI='-X',PDIS='PARAM 3')
        self.editor.refresh();self.app.update();layout=self.view.positions[other['id']];self.click(layout)
        self.assertEqual(self.editor.element_id,other['id'])
        self.editor.tables['main'].selection_set('PDIS');self.app.update();self.editor.expression.set('PARAM 3 / 2');self.app.update()
        expected=tuple(v/2 for v in layout);self.assertEqual(self.view.positions[other['id']],expected)
        self.app.data['scoms'][0]['values']['P3']=9000;self.view.refresh_options();self.app.update()
        self.assertEqual(self.view.positions[other['id']],expected);self.assertEqual(self.errors,[])

    def test_rotation_zoom_and_navigation_do_not_edit_data(self):
        before=copy.deepcopy(self.app.data);self.view.canvas.event_generate('<Button-3>',x=200,y=200);self.view.canvas.event_generate('<B3-Motion>',x=240,y=230);self.view.zoom(1.2);self.app.update()
        self.assertNotEqual(self.view.camera.yaw,0);self.assertEqual(self.app.data,before)
        win=self.view;self.app.switch('gmset');self.app.update();self.assertFalse(win.winfo_exists());self.assertEqual(self.errors,[])

    def test_empty_required_values_are_red_until_inline_input_commits(self):
        self.create((1,0,0));table=self.editor.tables['main'];self.assertTrue(table.canvas.find_withtag('required:PX'))
        self.assertFalse(table.canvas.find_withtag('required:PZ'));self.assertFalse(table.canvas.find_withtag('required:DESC'))
        table.begin_edit('PX');table.editing['variable'].set('PARAM 3 / 2');table.finish_edit();self.app.update()
        self.assertFalse(table.canvas.find_withtag('required:PX'))
        table.begin_edit('PX');table.editing['variable'].set('');table.finish_edit();self.app.update()
        self.assertTrue(table.canvas.find_withtag('required:PX'));self.assertEqual(self.errors,[])

    def test_all_point_types_can_be_placed_without_parameters_or_scom(self):
        self.app.data['scoms'].clear();self.editor.definition()['parameter_preset_id']=''
        for index,kind in enumerate(schema.PT_TYPES):
            self.create((-.85,.37+index*.25,0),kind);point=self.editor.element()
            self.assertEqual(point['type'],kind);self.assertIn(LAYOUT_KEY,point)
            self.assertIn(point['attrs']['PAXI' if kind in ('PTAXI','PTMIX') else 'PTCDIR'],('-X','Y'))
        self.assertEqual(self.errors,[])

    def test_display_buttons_toggle_without_data_changes(self):
        before=copy.deepcopy(self.app.data)
        for label,tag in (('グリッド','grid'),('座標軸','axes'),('点番号','labels'),('関係線','relations')):
            self.assertTrue(self.view.canvas.find_withtag(tag));self.view.display_buttons[label].invoke();self.app.update()
            self.assertFalse(self.view.canvas.find_withtag(tag));self.view.display_buttons[label].invoke();self.app.update()
            self.assertTrue(self.view.canvas.find_withtag(tag))
        self.view.view_buttons['立体'].invoke()
        for plane in PLANES:
            self.view.view_buttons[plane].invoke();self.assertEqual(self.view.view.get(),plane)
            self.assertEqual(self.view.plane.get(),'XY')
            camera=Camera();camera.face(plane);self.assertEqual(self.view.camera.basis(),camera.basis())
        self.assertEqual(self.app.data,before);self.assertEqual(self.errors,[])

    def test_menu_context_is_invalidated_when_plane_or_set_changes(self):
        before=copy.deepcopy(self.app.data);self.click((-.8,-.7,0));self.view.plane.set('XZ');self.view.plane_changed();self.view.create_menu.invoke(0);self.app.update()
        self.assertEqual(self.app.data,before)
        self.click((-.8,-.7,0));self.editor.definition_id='missing';self.view.create_menu.invoke(0);self.app.update()
        self.assertEqual(self.app.data,before);self.assertIn('セット・基準面が変更',self.view.note['text']);self.assertEqual(self.errors,[])

    def axial(self,seed,axis='X',distance='PARAM 3'):
        point=schema.add_element(self.editor.definition(),'PTAXI');point['attrs'].update(PAXI=axis,PDIS=distance);point[LAYOUT_KEY]=list(seed);return point

    def test_oblique_axis_drag_moves_shared_dependents_without_changing_formulas(self):
        self.editor.definition()['elements']=[]
        self.point=self.axial((.7,.7,0),'X45Y');other=self.axial((.2,0,0),'X','PARAM 3 / 2')
        self.editor.refresh();self.app.update();attrs=copy.deepcopy(self.point['attrs']);scoms=copy.deepcopy(self.app.data['scoms'])
        self.drag((1.8,.6,0),release=False)
        candidate=self.view.pending['point'];self.assertAlmostEqual(candidate[0],candidate[1]);self.assertAlmostEqual(candidate[0],1.2,delta=.01)
        self.assertEqual(self.point[LAYOUT_KEY],[.7,.7,0]);self.assertGreater(self.view.positions[other['id']][0],.8)
        self.view.canvas.event_generate('<ButtonRelease-1>',x=0,y=0);self.app.update()
        self.assertAlmostEqual(self.point[LAYOUT_KEY][0],self.point[LAYOUT_KEY][1]);self.assertEqual(self.point['attrs'],attrs)
        self.assertEqual(self.app.data['scoms'],scoms);self.assertEqual(self.errors,[])

    def test_overlapping_shared_point_can_be_selected_and_updates_the_shared_dimension(self):
        self.editor.definition()['elements']=[];self.axial((1.4,0,0));self.point=self.axial((.3,0,0))
        self.editor.refresh();self.editor.elements.selection_set(self.point['id']);self.editor.select_element();self.app.update()
        attrs=[copy.deepcopy(p['attrs']) for p in self.editor.definition()['elements']];self.app.dirty=False;self.drag((2,0,0))
        self.assertEqual(self.editor.element_id,self.point['id']);self.assertTrue(self.app.dirty)
        for point in self.editor.definition()['elements']:self.assertAlmostEqual(self.view.positions[point['id']][0],2,delta=.01)
        self.assertEqual([p['attrs'] for p in self.editor.definition()['elements']],attrs);self.assertEqual(self.errors,[])

    def test_later_parameter_assignment_reuses_existing_value_regardless_of_numb(self):
        self.editor.definition()['elements']=[];later=self.axial((.4,0,0),distance='');later['attrs']['NUMB']='1'
        first=self.axial((1.4,0,0));first['attrs']['NUMB']='20'
        self.editor.refresh();self.editor.elements.selection_set(later['id']);self.editor.select_element();self.app.update()
        table=self.editor.tables['main'];table.begin_edit('PDIS');table.editing['variable'].set('PARAM 3');self.assertTrue(table.finish_edit());self.app.update()
        self.assertAlmostEqual(self.view.positions[later['id']][0],1.4);self.assertAlmostEqual(self.view.positions[first['id']][0],1.4)
        self.assertEqual(self.editor.definition()[DIMENSIONS_KEY]['values']['PARAM']['P3'],1.4);self.assertEqual(self.errors,[])

    def test_cancelled_shared_drag_does_not_commit_values_or_other_point_positions(self):
        self.editor.definition()['elements']=[];first=self.axial((1.4,0,0));self.point=self.axial((-.3,0,0),'-X')
        self.editor.refresh();self.app.update();before=copy.deepcopy(self.app.data)
        self.drag((-2,0,0),release=False)
        self.assertAlmostEqual(self.view.positions[first['id']][0],2,delta=.01)
        self.view.cancel();self.app.update();self.assertEqual(self.app.data,before)
        self.assertEqual(self.view.positions[first['id']][0],1.4);self.assertEqual(self.errors,[])

    def test_cartesian_drag_obeys_zero_and_shared_coordinate_expressions(self):
        attrs=copy.deepcopy(self.point['attrs']);self.drag((1.2,.8,0))
        x,y,z=self.view.positions[self.point['id']]
        self.assertEqual(y,0);self.assertAlmostEqual(z,x/2);self.assertEqual(self.point['attrs'],attrs);self.assertEqual(self.errors,[])

    def test_earlier_reference_edit_invalidates_a_pending_drag(self):
        self.editor.definition()['elements']=[];first=self.axial((1.4,0,0));self.point=self.axial((-.3,0,0),'-X')
        self.editor.refresh();self.app.update();self.drag((-.8,0,0),release=False)
        first['attrs']['PDIS']='PARAM 3 / 2';self.view.apply();self.app.update()
        self.assertIn('属性・配置が変更',self.view.note['text']);self.assertEqual(self.point[LAYOUT_KEY],[-.3,0,0]);self.assertEqual(self.errors,[])

    def test_unresolved_angle_cannot_be_replaced_by_mouse_placement(self):
        self.editor.definition()['elements']=[];self.point=self.axial((.7,.7,0),'X(ANGL / 2)Y')
        self.editor.refresh();self.app.update();before=copy.deepcopy(self.app.data)
        self.view.propose(*self.pixels((1,0,0)),ident=self.point['id']);self.view.apply();self.app.update()
        self.assertIsNone(self.view.pending);self.assertIn('ANGL',self.view.note['text']);self.assertEqual(self.app.data,before);self.assertEqual(self.errors,[])


class SchematicGeometryTests(unittest.TestCase):
    def test_axial_placement_uses_direction_without_inventing_distance(self):
        point,attrs=schematic_placement('PTAXI',(-.73,.31,0))
        self.assertEqual(point,(-.73,0,0));self.assertEqual(attrs,{'PAXI':'-X','PDIS':''})
        point,attrs=schematic_placement('PTAXI',(-1,0,0),{'PAXI':'X','PDIS':'PARAM 3 / 2'})
        self.assertNotIn('PDIS',attrs);self.assertNotIn('PAXI',attrs)

    def test_move_preserves_coordinate_expression_outside_active_plane(self):
        point,attrs=schematic_placement('PTCAR',(1,.5,0),{'PX':'PARAM 3','PY':'0','PZ':'PARAM 4','PTCDIR':'X'},'XY')
        self.assertNotIn('PZ',attrs);self.assertNotIn('PY',attrs);self.assertNotIn('PTCDIR',attrs)

    def test_complex_directions_are_never_rewritten(self):
        point,attrs=schematic_placement('PTPOS',(1,1,0),{'PTCD':'X(ANGL / 2)Y45U','PTCPOS':'original'})
        self.assertEqual(attrs,{})
        point,attrs=schematic_placement('PTMIX',(1,1,0),{'PAXI':'P2','PX':'PARAM 3','PY':'PARAM 4','PZ':'0'})
        self.assertNotIn('PAXI',attrs)
        with self.assertRaises(ValueError):schematic_placement('PTAXI',(1,1,0),{'PAXI':'P2','PDIS':'PARAM 3'})

    def test_layout_survives_presets_and_rejects_invalid_json_metadata(self):
        from catalog_studio import element_library
        data=project.sample();definition=project.add_definition(data,'PTSET');definition['elements']=[]
        point=schema.add_element(definition,'PTCAR');point[LAYOUT_KEY]=[.73,.41,0]
        record=element_library.register(data,definition,'仮配置付き');target=project.add_definition(data,'PTSET');target['elements']=[]
        recalled=element_library.recall(data,target,record['id']);self.assertEqual(recalled[0][LAYOUT_KEY],[.73,.41,0])
        recalled[0][LAYOUT_KEY][0]=9;self.assertEqual(point[LAYOUT_KEY],[.73,.41,0])
        for invalid in ([0,1],['0',1,2],[True,0,1],[float('nan'),0,0],[10001,0,0]):
            point[LAYOUT_KEY]=invalid
            with self.assertRaises(ValueError):project.validate(data)

    def test_unknown_position_expressions_get_only_provisional_layout(self):
        element={'type':'PTPOS','attrs':{'PTCPOS':'unparsed original'}};original=copy.deepcopy(element)
        self.assertEqual(len(schematic_position(element)),3);self.assertEqual(element,original)
