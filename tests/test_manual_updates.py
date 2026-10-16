import copy
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from catalog_studio import (expressions as expr, project, element_schema as schema,
                            geometry_scene as geo, geometry_preview, catalogue,
                            element_library, model_settings, representation)
from test_geometry_scene import fixture


class ManualUpdatesTests(unittest.TestCase):
    def setUp(self):self.data,self.pt,self.gm,self.scom,self.node=fixture()

    def bounds(self,mesh,axis):return min(p[axis] for p in mesh.vertices),max(p[axis] for p in mesh.vertices)

    def test_signed_cylinder_extends_backwards_and_retains_formula(self):
        self.node['attrs'].update(PAXI='-Y',PDIS='PARAM 3 / 2',PHEI='-PARAM 3')
        original=copy.deepcopy(self.data)
        scene=geo.build_scene(self.data,self.gm,self.scom,True)
        self.assertEqual(scene.issues,[]);self.assertEqual(self.bounds(scene.meshes[0],1),(-50,50))
        self.assertEqual(self.data,original)
        self.node['attrs']['PHEI']='0'
        self.assertIn('0以外',' '.join(geo.build_scene(self.data,self.gm,self.scom,True).issues))

    def test_signed_height_shares_positive_param_from_any_handle(self):
        self.pt['elements']=[]
        self.node['attrs'].update(PAXI='X',PDIS='0',PHEI='-2 * PARAM 3')
        other=schema.add_element(self.gm,'SCYL');other['attrs'].update(PAXI='X',PDIA='PARAM 1',PHEI='PARAM 3')
        preview=geometry_preview.remember(self.data,self.gm)
        self.assertGreater(preview.dimensions.values[('PARAM','P3')],0)
        mesh=geo.build_scene(self.data,self.gm).meshes[0];length=self.bounds(mesh,0)[1]-self.bounds(mesh,0)[0]
        state=preview.resize(self.node['id'],0,length*2)
        geometry_preview.store(self.data,self.gm,state)
        meshes=geo.build_scene(self.data,self.gm).meshes
        self.assertAlmostEqual(self.bounds(meshes[0],0)[0],-length*2)
        self.assertAlmostEqual(self.bounds(meshes[1],0)[1],length)

    def test_omitted_point_geometry_uses_y_and_zero_without_writing_defaults(self):
        for kind in ('PTAXI','PTCAR','PTMIX'):
            self.pt['elements']=[];node=schema.add_element(self.pt,kind);node['attrs']={'NUMB':'1'}
            self.node['attrs']['PAXI']='X';before=copy.deepcopy(self.pt)
            scene=geo.build_scene(self.data,self.gm,self.scom,True)
            self.assertEqual(scene.issues,[]);self.assertEqual(scene.points[1][:2],((0,0,0),(0,1,0)))
            self.assertEqual(self.pt,before)

    def test_unit_literals_and_numeric_parameter_input_are_database_values(self):
        for text,value in (('10inch',254),('2cm + 3mm',23),('1ft',304.8),('90degrees',90)):
            self.assertAlmostEqual(expr.evaluate(text),value)
            self.assertAlmostEqual(expr.evaluate(expr.normalized(text)),value)
        self.assertEqual(project.parse_value({'id':'P1','unit':'mm'},'10inch'),254)
        self.assertEqual(project.parse_value({'id':'P1','unit':'inch'},'254mm'),10)
        self.assertEqual(project.parse_value({'id':'P1','unit':'inch'},'2 * 5'),10)
        self.assertEqual(expr.evaluate('PARAM 1',{'PARAM':{'P1':10}},parameters=[{'id':'P1','role':'OD','unit':'inch'}],expected='DIST'),254)
        with self.assertRaises(ValueError):project.parse_value({'id':'P1','unit':'mm'},'90degrees')
        self.node['attrs'].update(PDIA='1inch',PHEI='2inch')
        scene=geo.build_scene(self.data,self.gm,self.scom,True)
        self.assertEqual(scene.issues,[]);self.assertAlmostEqual(self.bounds(scene.meshes[0],1)[1],12.7)

    def test_dimensions_checked_in_math_functions_and_final_attribute(self):
        parameters=[{'id':'P1','role':'length','unit':'mm'},{'id':'P2','role':'angle','unit':'degrees'}]
        context={'PARAM':{'P1':25,'P2':30}}
        self.assertAlmostEqual(expr.evaluate('PARAM 1 * SIN(PARAM 2)',context,parameters=parameters,expected='DIST'),12.5)
        for text in ('PARAM 1 + PARAM 2','SIN(PARAM 1)','ASIN(PARAM 2)'):
            with self.assertRaises(ValueError):expr.evaluate(text,context,parameters=parameters)
        with self.assertRaises(ValueError):expr.evaluate('PARAM 2',context,parameters=parameters,expected='DIST')
        with self.assertRaises(ValueError):expr.evaluate('PARAM 1 * PARAM 1',context,parameters=parameters,expected='DIST')

    def test_functions_and_design_aliases_have_degree_semantics(self):
        self.assertAlmostEqual(expr.evaluate('ASIN(0.5)'),30)
        self.assertAlmostEqual(expr.evaluate('ATAN(1)'),45)
        self.assertAlmostEqual(expr.evaluate('COS(60degrees)'),.5)
        self.assertEqual(expr.evaluate('TWICE DDA',attributes={'DDANGLE':35}),70)
        for text in ('ASIN(2)','ACOS(-2)','TAN(90degrees)'):
            with self.assertRaises(ValueError):expr.evaluate(text)

    def test_negative_target_axes_and_design_setting_direction(self):
        self.pt['elements'][0]['attrs'].update(PAXI='Z 70 -X')
        scene=geo.build_scene(self.data,self.gm,self.scom,True)
        self.assertEqual(scene.issues,[])
        vector=scene.points[1][1];self.assertAlmostEqual(vector[0],-math.sin(math.radians(70)))
        self.assertAlmostEqual(vector[2],math.cos(math.radians(70)))
        self.gm['model_settings']={'DDANGLE':30,'DDHEIGHT':60}
        self.node['attrs'].update(PAXI='X TWICE DDA Y',PHEI='DDHEIGHT')
        self.assertEqual(geo.build_scene(self.data,self.gm,self.scom,True).issues,[])
        self.assertFalse(catalogue.definition_issues(self.gm,self.data['parameters'],self.scom))

    def test_missing_design_value_never_invents_a_dimension(self):
        self.node['attrs']['PHEI']='PARAM 3 * SIN(DDANGLE)'
        scene=geo.build_scene(self.data,self.gm)
        self.assertFalse(scene.meshes);self.assertIn('DDANGLE',' '.join(scene.issues))
        self.gm['model_settings']={'DDANGLE':30}
        self.assertEqual(geo.build_scene(self.data,self.gm).issues,[])

    def test_design_settings_persist_in_project_and_presets(self):
        self.gm['model_settings']=model_settings.parse({'DDANGLE':'ASIN(0.5)','DDHEIGHT':'2inch'})
        record=element_library.register(self.data,self.gm,'設計値付き')
        self.assertEqual(record['model_settings']['DDHEIGHT'],50.8)
        target=copy.deepcopy(self.gm);target['id']='copy';target['elements']=[];target.pop('model_settings')
        self.data['definitions'].append(target);element_library.recall(self.data,target,record['id'])
        self.assertEqual(target['model_settings'],self.gm['model_settings'])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'values.json';project.save(self.data,path);self.assertEqual(project.load(path),self.data)
        for bad in ({'DDANGLE':True},{'DDHEIGHT':float('nan')},{'OTHER':2}):
            with self.assertRaises(ValueError):model_settings.validate(bad)

    def test_pskey_accepts_documented_words_and_keeps_connection_type_separate(self):
        point=self.pt['elements'][0];point['attrs']['PCON']='BWD'
        for word in schema.PSKEY_CHOICES+('unset',):
            point['attrs']['PSKEY']=word
            self.assertFalse(any('PSKEY' in x for x in catalogue.definition_issues(self.pt,self.data['parameters'])))
        point['attrs']['PSKEY']='UNKNOWN'
        self.assertTrue(any('PSKEY' in x for x in catalogue.definition_issues(self.pt,self.data['parameters'])))

    def test_neutral_axis_explicit_ordinals_fallback_priority_and_reorder(self):
        d={'id':'struct','kind':'PTSSET','name':'/S','revision':'01','attrs':{},'elements':[]}
        self.data['definitions'].append(d)
        for key in ('ZAXI','NAXI','NA'):schema.add_element(d,'PLINE')['attrs']['PKEY']=key
        self.assertEqual(schema.neutral_axis(d),(d['elements'][2],'fallback'))
        self.assertFalse(catalogue.definition_issues(d))
        d['attrs']['NAREF']='2';target=d['elements'][1]
        element_library.reorder(self.data,d,target['id'],0)
        self.assertEqual(d['attrs']['NAREF'],'1');self.assertIs(schema.neutral_axis(d)[0],target)
        d['attrs']['NAREF']='99';self.assertTrue(catalogue.definition_issues(d))

    def test_level_is_two_integers_and_legacy_twenty_limit_is_not_enforced(self):
        self.node['attrs']['LEVEL']='1.5 3'
        self.assertTrue(any('LEVEL' in x for x in catalogue.definition_issues(self.gm)))
        self.node['attrs']['LEVEL']='-2 3'
        self.assertFalse(any('LEVEL' in x for x in catalogue.definition_issues(self.gm)))
        d={'id':'struct','kind':'GMSSET','name':'/S','revision':'01','elements':[]}
        for _ in range(21):schema.add_element(d,'SREC')['attrs']['OBST']='2'
        self.assertFalse(any('20' in x for x in catalogue.definition_issues(d)))

    def test_negative_children_are_saved_and_drawn_without_boolean_claim(self):
        child=schema.add_child(self.node,'NSCY');child['attrs'].update(PAXI='X',PDIA='PARAM 1 / 2',PHEI='PARAM 3',PDIS='0')
        self.assertFalse(any('子要素' in x for x in catalogue.definition_issues(self.gm,self.data['parameters'])))
        scene=geo.build_scene(self.data,self.gm,self.scom,True)
        self.assertEqual(scene.issues,[]);self.assertEqual(len(scene.meshes),2);self.assertTrue(scene.meshes[1].negative)
        self.assertEqual(self.bounds(scene.meshes[0],1),(-20,20))
        self.node['attrs'].update(PDIA='40',PHEI='100')
        preview=geometry_preview.GeometryPreview(self.data,self.gm)
        self.assertFalse(preview.has_dimensions(self.node))
        self.assertIsNotNone(preview.resize(child['id'],0,2))
        dish=schema.add_child(self.node,'NSDS');self.assertEqual(schema.positive(dish['type']),'SDSH')
        with self.assertRaises(ValueError):schema.add_child(child,'NSCY')

    def test_visibility_routes_level_policy_and_hidden_error_explanation(self):
        self.node['attrs'].update(LEVEL='1 3',OBST='1',CLFLA='TRUE',TUFLA='FALSE')
        settings={'mode':'属性確認','cl':True,'tube':False,'obst':False,'level':2}
        self.assertTrue(representation.visibility(self.node,settings)[0])
        settings.update(cl=False,obst=True);self.assertTrue(representation.visibility(self.node,settings)[2])
        settings['level']=4;self.assertFalse(representation.visibility(self.node,settings)[0])
        settings['obst_bypass']=True;self.assertTrue(representation.visibility(self.node,settings)[0])
        settings.update(obst=False,cl=False,tube=False)
        original=copy.deepcopy(self.data)
        scene=geo.build_scene(self.data,self.gm,self.scom,True,representation_settings=settings)
        self.assertFalse(scene.meshes);self.assertIn(self.node['id'],scene.hidden);self.assertEqual(self.data,original)
        self.assertTrue(geo.build_scene(self.data,self.gm,self.scom,True).meshes)


class ManualUpdatesGuiTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from catalog_studio.integrated import IntegratedStudio
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v))
        self.app.data,self.pt,self.gm,self.scom,self.node=fixture()
        self.app.definition_id=self.gm['id'];self.app.switch('gmset');self.app.update()
        self.editor=self.app.geometry_editor;self.editor.element_id=self.node['id'];self.editor.refresh();self.app.update()

    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()

    def test_representation_switch_and_dialog_show_hidden_selection_without_changing_project(self):
        view=self.editor.geometry_view;before=copy.deepcopy(self.app.data)
        view.rep_options.update(tube=False,cl=False,obst=False);view.representation_mode.set('属性確認');view.representation_changed();self.app.update()
        self.assertFalse(view.scene.meshes);self.assertIn('表示条件',view.issue_label.cget('text'))
        self.assertEqual(self.app.data,before)
        def accept(title,fields,apply):
            values={key:initial for key,_,initial,_ in fields};values.update(obst='ON',level='0');apply(values)
        self.node['attrs']['OBST']='2'
        with patch.object(self.app,'form',side_effect=accept):representation.edit(view)
        self.app.update();self.assertTrue(view.scene.meshes);self.assertEqual(self.errors,[])

    def test_design_settings_dialog_and_child_editing(self):
        def accept(title,fields,apply):apply({key:('2inch' if key=='DDHEIGHT' else '') for key,_,initial,_ in fields})
        with patch.object(self.app,'form',side_effect=accept):model_settings.edit(self.editor)
        self.assertEqual(self.gm['model_settings'],{'DDHEIGHT':50.8})
        self.editor.add_negative_child('NSCY');self.app.update()
        self.assertEqual(self.editor.element()['type'],'NSCY');self.assertTrue(self.editor.elements.exists(self.node['children'][0]['id']))
        self.assertEqual(self.errors,[])
