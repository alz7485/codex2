import copy
import math
import tempfile
import unittest
from pathlib import Path
from catalog_studio import geometry_scene as geo, element_schema as schema, project, presets, element_library


def fixture():
    data=project.sample();data['definitions']=[];data['scoms']=[]
    pt={'id':'points','name':'/TEST-PTSET','kind':'PTSET','revision':'01','elements':[]}
    for direction,distance in (('-X','PARAM 3 / 2'),('X','PARAM 3 / 2')):
        point=schema.add_element(pt,'PTAXI');point['attrs'].update(PAXI=direction,PDIS=distance)
    gm={'id':'geometry','name':'/TEST-GMSET','kind':'GMSET','revision':'01','elements':[],'paired_ptset_id':pt['id']}
    cylinder=schema.add_element(gm,'SCYL');cylinder['attrs'].update(PAXI='P2',PDIS='0',PHEI='PARAM 3',PDIA='PARAM 1')
    scom={'id':'part','name':'/TEST-PART','cate_id':data['cates'][0]['id'],'revision':'01','size':'100','ptset_id':pt['id'],'gmset_id':gm['id'],'values':{'P1':40,'P3':100}}
    data['definitions']=[pt,gm];data['scoms']=[scom]
    return data,pt,gm,scom,cylinder


class GeometrySceneTests(unittest.TestCase):
    def setUp(self):self.data,self.pt,self.gm,self.scom,self.cylinder=fixture()
    def scene(self):return geo.build_scene(self.data,self.gm,self.scom,True)
    def bounds(self,mesh):return [(min(p[i] for p in mesh.vertices),max(p[i] for p in mesh.vertices)) for i in range(3)]

    def test_axis_uses_point_position_and_direction_with_real_parameter_dimensions(self):
        scene=self.scene();self.assertEqual(scene.issues,[])
        self.assertEqual(scene.points[1][0],(-50,0,0));self.assertEqual(scene.points[2][0],(50,0,0))
        self.assertEqual(self.bounds(scene.meshes[0]),[(50,150),(-20,20),(-20,20)])
        self.cylinder['attrs']['PAXI']='P1';scene=self.scene()
        self.assertEqual(self.bounds(scene.meshes[0])[0],(-150,-50))

    def test_point_chains_cartesian_mixed_position_and_degree_directions(self):
        for kind in ('PTCAR','PTMIX','PTPOS'):
            point=schema.add_element(self.pt,kind)
            point['attrs'].update(PX='PARAM 1',PY='PARAM 3 / 2',PZ='0',PTCPOS='X (PARAM 1) Y (PARAM 3 / 2) Z 0',PAXI='P2',PTCDIR='X(ANGL / 2)Y45U')
        self.scom['component_attrs']={'ANGL':90};scene=self.scene();self.assertEqual(scene.issues,[])
        for number in (3,4,5):self.assertEqual(scene.points[number][0],(40,50,0))
        for actual,expected in zip(scene.points[3][1],(.5,.5,math.sqrt(.5))):self.assertAlmostEqual(actual,expected)
        self.assertEqual(scene.points[4][1],(1,0,0))
        self.pt['elements'][1]['attrs'].update(PAXI='P1',PDIS='10')
        self.assertEqual(self.scene().points[2][0],(-60,0,0))

    def test_cycle_missing_point_and_missing_values_never_invent_actual_geometry(self):
        invalid=copy.deepcopy(self.pt);invalid['elements'][1]['attrs']['NUMB']=invalid['elements'][0]['attrs']['NUMB']
        draft_data=copy.deepcopy(self.data);draft_data['definitions'][0]=invalid
        self.assertTrue(any('番号が不正・重複' in message for message in geo.build_scene(draft_data,draft_data['definitions'][1]).issues))
        self.pt['elements'][0]['attrs']['PAXI']='P2';self.pt['elements'][1]['attrs']['PAXI']='P1'
        scene=self.scene();self.assertEqual(scene.meshes,[]);self.assertTrue(any('循環' in s for s in scene.issues))
        self.pt['elements'][1]['attrs']['PAXI']='X';self.cylinder['attrs']['PAXI']='P99'
        self.assertIn('P99',self.scene().issues[-1])
        self.cylinder['attrs']['PAXI']='X';self.scom['values'].pop('P1')
        scene=self.scene();self.assertEqual(scene.meshes,[]);self.assertIn('未設定',scene.issues[-1])

    def test_draft_resize_has_no_effect_on_actual_dimensions_and_roundtrips(self):
        original=self.scene();attrs=copy.deepcopy(self.cylinder['attrs'])
        self.cylinder[geo.SCALE_KEY]=[2,3,4]
        draft=geo.build_scene(self.data,self.gm);self.assertEqual(draft.issues,[])
        self.assertEqual(self.cylinder['attrs'],attrs)
        self.assertEqual(self.scene().meshes[0].vertices,original.meshes[0].vertices)
        record=element_library.register(self.data,self.gm,'仮サイズ付き')
        self.assertEqual(record['elements'][0][geo.SCALE_KEY],[2,3,4])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'project.json';project.save(self.data,path)
            self.assertEqual(project.load(path),self.data)

    def test_scom_must_match_geometry_pointset_and_role_profile(self):
        for key,value in (('gmset_id','another'),('ptset_id','another'),('parameter_preset_id','missing')):
            with self.subTest(key=key):
                changed=copy.deepcopy(self.scom);changed[key]=value
                scene=geo.build_scene(self.data,self.gm,changed,True)
                self.assertEqual(scene.meshes,[]);self.assertTrue(scene.issues)
        scene=geo.build_scene(self.data,self.gm,None,True);self.assertEqual(scene.meshes,[])
        other=presets.add(self.data,'異なる規則');self.pt['parameter_preset_id']=other['id']
        self.assertEqual(self.scene().meshes,[])

    def test_insulation_and_design_contexts_are_explicit_and_word_values_rejected(self):
        self.cylinder['attrs']['PDIA']='SUM PARAM 1 IPARAM 1'
        self.assertEqual(self.scene().meshes,[])
        self.scom['expression_contexts']={'IPARAM':{'P1':10}}
        self.assertEqual(self.bounds(self.scene().meshes[0])[1],(-25,25))
        self.scom['expression_contexts']['IPARAM']['P1']='BW'
        self.assertEqual(self.scene().meshes,[])

    def test_fit_preserves_proportions_and_contains_all_points_at_many_scales(self):
        camera=geo.FitCamera();camera.fit([],240,260)
        self.assertEqual(camera.project(geo.ZERO,240,260),(120,130))
        self.assertLess(camera.zoom,240)
        reference=None
        for magnitude in (1e-310,1e-100,1e-9,1,1e9,1e100):
            points=[(magnitude*x,magnitude*y,magnitude*z) for x in (-2,3) for y in (-1,1) for z in (0,6)]
            for width,height in ((240,260),(600,700)):
                camera=geo.FitCamera();camera.fit(points,width,height)
                result=[camera.project(p,width,height) for p in points]
                for x,y in result:self.assertTrue(40<=x<=width-40 and 40<=y<=height-40)
                if width==600:
                    if reference:
                        for p,q in zip(result,reference):
                            self.assertAlmostEqual(p[0],q[0]);self.assertAlmostEqual(p[1],q[1])
                    reference=result
                camera.yaw=120;camera.pitch=-40;camera.fit(points,width,height)
                self.assertTrue(all(40<=x<=width-40 and 40<=y<=height-40 for x,y in (camera.project(p,width,height) for p in points)))

    def test_draft_supports_primitives_and_negative_wireframe_meshes(self):
        self.gm['elements']=[]
        for kind in list(schema.GM_TYPES)+list(schema.NEGATIVE_BASE):
            node=schema.add_element(self.gm,kind)
            if kind=='LINE':node['attrs']['PTS']='P1 P2'
        scene=geo.build_scene(self.data,self.gm)
        self.assertEqual(len(scene.meshes),32)  # NSRU is not defined by supplied attributes.
        self.assertEqual(len(scene.issues),1);self.assertIn('未対応',scene.issues[0])
        self.assertTrue(any(m.negative for m in scene.meshes))

    def test_cylinder_box_sphere_and_cone_dimensions(self):
        self.gm['elements']=[]
        inputs=(('LCYL',dict(PAXI='Z',PDIA='12',PBDI='-20',PTDI='30')),
                ('SBOX',dict(PXLE='10',PYLE='20',PZLE='30',PX='4',PY='5',PZ='6')),
                ('SSPH',dict(PAXI='X',PDIS='20',PDIA='10')),
                ('SCON',dict(PAXI='-X',PDIS='25',PDIA='8')))
        for kind,attrs in inputs:schema.add_element(self.gm,kind)['attrs'].update(attrs)
        scene=self.scene();self.assertEqual(scene.issues,[])
        self.assertEqual(self.bounds(scene.meshes[0]),[(-6,6),(-6,6),(-20,30)])
        self.assertEqual(self.bounds(scene.meshes[1]),[(-1,9),(-5,15),(-9,21)])
        self.assertEqual(self.bounds(scene.meshes[2]),[(15,25),(-5,5),(-5,5)])
        self.assertEqual(self.bounds(scene.meshes[3]),[(-25,0),(-4,4),(-4,4)])

    def test_line_uses_point_numbers_and_reports_unimplemented_tangent_curve(self):
        self.cylinder['type']='LINE';self.cylinder['attrs']={'PTS':'P1 P0 P2'}
        scene=self.scene();self.assertEqual(scene.issues,[])
        self.assertEqual(scene.meshes[0].vertices,[(-50,0,0),(0,0,0),(50,0,0)])
        self.cylinder['attrs']['PTS']='P1 T2';self.assertEqual(self.scene().meshes,[])
        self.assertIn('接線点',self.scene().issues[-1])

    def test_extrusion_and_revolution_follow_loop_and_reject_unimplemented_fillets(self):
        self.gm['elements']=[]
        extrusion=schema.add_element(self.gm,'SEXT');extrusion['attrs'].update(PX='0',PY='0',PZ='0',PAAX='X',PBAX='Y',PHEI='30')
        loop=schema.add_child(extrusion)
        for x,y in ((-10,0),(10,0),(10,5),(-10,5)):schema.add_child(loop)['attrs'].update(PX=str(x),PY=str(y),PRAD='0')
        scene=self.scene();self.assertEqual(scene.issues,[]);self.assertEqual(self.bounds(scene.meshes[0]),[(-10,10),(0,5),(0,30)])
        extrusion['type']='SREV';extrusion['attrs']['PANGLE']='360';scene=self.scene()
        self.assertEqual(scene.issues,[]);self.assertEqual(self.bounds(scene.meshes[0]),[(-10,10),(-5,5),(-5,5)])
        loop['children'][0]['attrs']['PRAD']='2';self.assertEqual(self.scene().meshes,[])

    def test_torus_uses_endpoints_and_face_normals_without_inventing_radius(self):
        self.pt['elements']=[]
        for x,y,direction in ((100,0,'-Y'),(0,100,'-X')):
            point=schema.add_element(self.pt,'PTCAR');point['attrs'].update(PX=str(x),PY=str(y),PZ='0',PTCDIR=direction)
        self.cylinder['type']='SCTO';self.cylinder['attrs']={'PAAX':'P1','PBAX':'P2','PDIA':'20'}
        scene=self.scene();self.assertEqual(scene.issues,[])
        bounds=self.bounds(scene.meshes[0]);self.assertAlmostEqual(bounds[0][1],110);self.assertEqual(bounds[2],(-10,10))
        self.cylinder['attrs']['PAAX']='X';self.cylinder['attrs']['PBAX']='Y'
        self.assertEqual(self.scene().meshes,[])

    def test_invalid_sizes_and_unsupported_design_dependent_shapes_are_reported(self):
        for diameter in ('-1','0','1e200','1 / 0'):
            self.cylinder['attrs']['PDIA']=diameter;self.assertEqual(self.scene().meshes,[])
        self.cylinder['type']='TUBE';self.assertIn('設計側',self.scene().issues[-1])
        self.cylinder['type']='SDSH';self.cylinder['attrs'].update(PDIA='10',PHEI='5',PDIS='0')
        self.assertIn('未対応',self.scene().issues[-1])

    def test_invalid_saved_resize_metadata_is_rejected(self):
        for value in ((0,1,1),(1,float('nan'),1),(1,1),[True,1,1]):
            self.cylinder[geo.SCALE_KEY]=value
            with self.assertRaises(ValueError):project.validate(self.data)
