import copy
import math
import unittest
from catalog_studio import project, element_schema as schema, element_library, geometry_scene
from catalog_studio.point_geometry import LAYOUT_KEY, Camera
from catalog_studio.point_preview import PointPreview


class PointPreviewTests(unittest.TestCase):
    def setUp(self):
        self.data=project.sample();self.pt=project.add_definition(self.data,'PTSET');self.pt['elements']=[]

    def add(self,kind,seed,**attrs):
        point=schema.add_element(self.pt,kind);point['attrs'].update(attrs);point[LAYOUT_KEY]=list(seed);return point

    def check(self,actual,expected):
        for a,b in zip(actual,expected):self.assertAlmostEqual(a,b,places=8)

    def test_same_parameter_and_aliases_share_the_first_points_dimension(self):
        first=self.add('PTAXI',(1.4,0,0),PAXI='X',PDIS='PARAM 3')
        second=self.add('PTAXI',(.3,0,0),PAXI='X',PDIS='ATTRIB PARA[3]')
        before=copy.deepcopy(self.data);view=PointPreview(self.data,self.pt)
        self.check(view.location(first['id']),(1.4,0,0));self.check(view.location(second['id']),(1.4,0,0))
        self.assertEqual(view.sources(second['id']),[('PARAM','P3',1)]);self.assertEqual(self.data,before)

    def test_smallest_numb_is_the_source_even_if_it_is_last_in_the_list(self):
        large=self.add('PTAXI',(1.4,0,0),NUMB='10',PAXI='X',PDIS='PARAM 3')
        small=self.add('PTAXI',(.7,0,0),NUMB='2',PAXI='X',PDIS='PARAM 3')
        view=PointPreview(self.data,self.pt)
        self.check(view.location(large['id']),(.7,0,0));self.assertEqual(view.sources(small['id']),[('PARAM','P3',2)])

    def test_coefficients_and_opposite_axes_share_lengths(self):
        first=self.add('PTAXI',(.6,0,0),PAXI='X',PDIS='PARAM 3 / 2')
        second=self.add('PTAXI',(-.3,0,0),PAXI='W',PDIS='全長')
        view=PointPreview(self.data,self.pt)
        self.check(view.location(first['id']),(.6,0,0));self.check(view.location(second['id']),(-1.2,0,0))

    def test_cartesian_position_constraints_do_not_use_the_orientation_as_position(self):
        first=self.add('PTCAR',(1.6,.9,0),PX='PARAM 3',PY='-PARAM 3 / 2',PZ='0',PTCDIR='X45Y')
        second=self.add('PTMIX',(.1,.7,0),PX='0',PY='0.5 TIMES PARAM 3',PZ='0',PAXI='-X')
        view=PointPreview(self.data,self.pt)
        self.check(view.location(first['id']),(1.6,-.8,0));self.check(view.location(second['id']),(0,.8,0))
        self.check(view.point(1)[1],(math.sqrt(.5),math.sqrt(.5),0))

    def test_diagonal_axis_and_camera_projection_keep_the_point_on_45_degrees(self):
        point=self.add('PTAXI',(1,1,0),PAXI='X45Y',PDIS='PARAM 3')
        view=PointPreview(self.data,self.pt);origin,vector=view.axis('X45Y');camera=Camera();camera.face('XY')
        x,y=camera.project((1.2,.2,0),800,600);projected=camera.unproject_axis(x,y,800,600,origin,vector)
        self.check(projected,(.7,.7,0));point[LAYOUT_KEY]=list(projected)
        self.check(PointPreview(self.data,self.pt).location(point['id']),(.7,.7,0))

    def test_reference_point_axis_keeps_the_origin_and_shared_offset(self):
        self.add('PTCAR',(0,0,0),PX='0',PY='0',PZ='0',PTCDIR='Y')
        first=self.add('PTAXI',(0,1.2,0),PAXI='P1',PDIS='PARAM 3')
        second=self.add('PTAXI',(0,4,0),PAXI='P2',PDIS='PARAM 3')
        view=PointPreview(self.data,self.pt)
        self.check(view.location(first['id']),(0,1.2,0));self.check(view.location(second['id']),(0,2.4,0))

    def test_position_expressions_and_distinct_parameter_families(self):
        first=self.add('PTPOS',(1,.4,0),PTCPOS='X (PARAM 3) Y (IPARAM 3) Z 0',PTCDIR='-Y')
        second=self.add('PTCAR',(.2,.2,0),PX='IPARA[3]',PY='PARAM 3 / 2',PZ='0',PTCDIR='X')
        view=PointPreview(self.data,self.pt)
        self.check(view.location(first['id']),(1,.4,0));self.check(view.location(second['id']),(.4,.5,0))

    def test_combined_expression_is_shared_without_inventing_its_individual_parameters(self):
        first=self.add('PTAXI',(1.3,0,0),PAXI='X',PDIS='SUM PARAM 3 IPARAM 1')
        second=self.add('PTAXI',(.4,0,0),PAXI='X',PDIS='PARAM 3 + IPARAM 1')
        self.add('PTAXI',(.2,0,0),PAXI='X',PDIS='PARAM 3')
        view=PointPreview(self.data,self.pt)
        self.check(view.location(first['id']),(1.3,0,0));self.check(view.location(second['id']),(1.3,0,0))
        self.assertNotIn(('PARAM','P3'),view.values);self.assertIn(3,view.problems)
        second['attrs']['PDIS']='(PARAM 3 + IPARAM 1) / 2'
        self.check(PointPreview(self.data,self.pt).location(second['id']),(.65,0,0))

    def test_numeric_constants_have_a_common_unitless_scale(self):
        first=self.add('PTAXI',(1,0,0),PAXI='X',PDIS='100')
        second=self.add('PTAXI',(.8,0,0),PAXI='X',PDIS='50')
        view=PointPreview(self.data,self.pt)
        self.check(view.location(first['id']),(1,0,0));self.check(view.location(second['id']),(.5,0,0))

    def test_source_move_updates_dependents_without_changing_scom_or_formulas(self):
        first=self.add('PTAXI',(1,0,0),PAXI='X',PDIS='PARAM 3')
        second=self.add('PTAXI',(.3,0,0),PAXI='X',PDIS='PARAM 3 / 2')
        first[LAYOUT_KEY]=[1.8,0,0];view=PointPreview(self.data,self.pt)
        self.check(view.location(second['id']),(.9,0,0))
        self.data['scoms'][0]['values']['P3']=9000
        self.check(PointPreview(self.data,self.pt).location(second['id']),(.9,0,0))
        self.assertEqual(second['attrs']['PDIS'],'PARAM 3 / 2')

    def test_save_reopen_and_element_preset_keep_the_reference_layout(self):
        self.add('PTAXI',(1.7,0,0),PAXI='X',PDIS='PARAM 3')
        self.add('PTAXI',(.2,0,0),PAXI='X',PDIS='PARAM 3')
        record=element_library.register(self.data,self.pt,'共有仮寸法');target=project.add_definition(self.data,'PTSET');target['elements']=[]
        recalled=element_library.recall(self.data,target,record['id']);view=PointPreview(self.data,target)
        self.check(view.location(recalled[1]['id']),(1.7,0,0));project.validate(self.data)

    def test_unresolved_angle_and_cycles_cannot_supply_a_guessed_axis(self):
        self.add('PTAXI',(1,1,0),PAXI='X(ANGL / 2)Y',PDIS='PARAM 3')
        view=PointPreview(self.data,self.pt)
        with self.assertRaises(ValueError):view.axis('X(ANGL / 2)Y')
        self.assertIn(1,view.problems)
        self.pt['elements'][0]['attrs']['PAXI']='P1'
        with self.assertRaises(ValueError):PointPreview(self.data,self.pt).axis('P1')

    def test_gmset_draft_uses_the_same_shared_point_positions(self):
        first=self.add('PTAXI',(.9,0,0),PAXI='X',PDIS='PARAM 3')
        second=self.add('PTAXI',(.2,0,0),PAXI='X',PDIS='PARAM 3 / 2')
        gm=project.add_definition(self.data,'GMSET');gm['elements']=[];gm['paired_ptset_id']=self.pt['id']
        scene=geometry_scene.build_scene(self.data,gm)
        self.check(scene.points[1][0],(.9,0,0));self.check(scene.points[2][0],(.45,0,0))

    def test_preview_dimensions_are_local_to_each_ptset(self):
        first=self.add('PTAXI',(1.4,0,0),PAXI='X',PDIS='PARAM 3')
        other=copy.deepcopy(self.pt);other['elements'][0][LAYOUT_KEY]=[.7,0,0]
        self.check(PointPreview(self.data,self.pt).location(first['id']),(1.4,0,0))
        self.check(PointPreview(self.data,other).location(first['id']),(.7,0,0))
