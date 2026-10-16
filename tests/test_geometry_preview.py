import copy
import tempfile
import unittest
from pathlib import Path
from catalog_studio import project, presets, element_schema as schema, element_library, geometry_scene as geo
from catalog_studio.geometry_preview import GeometryPreview, remember, store
from catalog_studio.point_preview import PointPreview, remember as remember_points
from catalog_studio.point_geometry import LAYOUT_KEY, DIMENSIONS_KEY
from test_geometry_scene import fixture


class GeometryPreviewTests(unittest.TestCase):
    def setUp(self):self.data,self.pt,self.gm,self.scom,self.node=fixture()

    def extent(self,scene,ident,axis):
        mesh=next(m for m in scene.meshes if m.ident==ident)
        return max(p[axis] for p in mesh.vertices)-min(p[axis] for p in mesh.vertices)

    def test_geometry_uses_the_points_existing_shared_values_without_mutating_data(self):
        self.pt['elements'][0][LAYOUT_KEY]=[-1,0,0];remember_points(self.data,self.pt)
        before=copy.deepcopy(self.data);scene=geo.build_scene(self.data,self.gm)
        self.assertAlmostEqual(self.extent(scene,self.node['id'],0),2)
        self.assertEqual(scene.points[2][0],(1,0,0));self.assertEqual(self.data,before)

    def test_later_shape_reuses_the_existing_parameter_and_coefficient(self):
        remember(self.data,self.gm)
        other=schema.add_element(self.gm,'SCYL');other['attrs'].update(PAXI='X',PDIS='0',PDIA='ATTRIB PARA[1] / 2',PHEI='PARAM 3 / 2')
        scene=geo.build_scene(self.data,self.gm)
        self.assertAlmostEqual(self.extent(scene,other['id'],1),self.extent(scene,self.node['id'],1)/2)
        self.assertAlmostEqual(self.extent(scene,other['id'],0),self.extent(scene,self.node['id'],0)/2)

    def test_either_shape_resize_updates_all_shapes_and_points_and_preserves_real_data(self):
        self.pt['elements'][0][LAYOUT_KEY]=[-1,0,0];remember_points(self.data,self.pt)
        other=schema.add_element(self.gm,'SCYL');other['attrs'].update(PAXI='-X',PDIS='0',PDIA='PARAM 1',PHEI='PARAM 3 / 2')
        attrs=copy.deepcopy([n['attrs'] for n in self.gm['elements']]);scoms=copy.deepcopy(self.data['scoms'])
        preview=GeometryPreview(self.data,self.gm);state=preview.resize(other['id'],0,1.5)
        store(self.data,self.gm,state);scene=geo.build_scene(self.data,self.gm)
        self.assertAlmostEqual(self.extent(scene,self.node['id'],0),3)
        self.assertAlmostEqual(scene.points[2][0][0],1.5);self.assertAlmostEqual(PointPreview(self.data,self.pt).point(1)[0][0],-1.5)
        state=GeometryPreview(self.data,self.gm).resize(self.node['id'],0,2)
        store(self.data,self.gm,state);scene=geo.build_scene(self.data,self.gm)
        self.assertAlmostEqual(self.extent(scene,other['id'],0),1)
        self.assertEqual([n['attrs'] for n in self.gm['elements']],attrs);self.assertEqual(self.data['scoms'],scoms)
        actual=geo.build_scene(self.data,self.gm,self.scom,True)
        self.assertEqual(self.extent(actual,self.node['id'],0),100)

    def test_changes_from_point_preview_are_reflected_in_both_paired_geomsets(self):
        remember(self.data,self.gm)
        other=copy.deepcopy(self.gm);other['id']='another-geometry';other['name']='/ANOTHER-GMSET';self.data['definitions'].append(other)
        state=GeometryPreview(self.data,self.gm).resize(self.node['id'],0,3)
        store(self.data,self.gm,state)
        self.assertAlmostEqual(self.extent(geo.build_scene(self.data,other),self.node['id'],0),3)
        current=PointPreview(self.data,self.pt);working=copy.deepcopy(self.pt);working['elements'][0][LAYOUT_KEY]=[-2,0,0]
        changed=current.moved(working,self.pt['elements'][0]['id'],'XY');self.pt[DIMENSIONS_KEY]=changed.snapshot();remember_points(self.data,self.pt)
        self.assertAlmostEqual(self.extent(geo.build_scene(self.data,self.gm),self.node['id'],0),4)
        self.assertAlmostEqual(self.extent(geo.build_scene(self.data,other),self.node['id'],0),4)

    def test_unpaired_geomset_saves_shared_values_and_presets_reuse_existing_values(self):
        self.gm['paired_ptset_id']='';self.node['attrs']['PAXI']='X';remember(self.data,self.gm)
        state=GeometryPreview(self.data,self.gm).resize(self.node['id'],1,1.8);store(self.data,self.gm,state)
        record=element_library.register(self.data,self.gm,'共有仮寸法の形状')
        target=project.add_definition(self.data,'GMSET');target.update(elements=[],paired_ptset_id='')
        nodes=element_library.recall(self.data,target,record['id'])
        self.assertAlmostEqual(self.extent(geo.build_scene(self.data,target),nodes[0]['id'],1),1.8)
        state=GeometryPreview(self.data,target).resize(nodes[0]['id'],1,.9);store(self.data,target,state)
        added=element_library.recall(self.data,target,record['id']);scene=geo.build_scene(self.data,target)
        for node in nodes+added:self.assertAlmostEqual(self.extent(scene,node['id'],1),.9)
        nodes=element_library.recall(self.data,target,record['id'],replace=True)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'draft.json';project.save(self.data,path);loaded=project.load(path)
            self.assertAlmostEqual(self.extent(geo.build_scene(loaded,project.get(loaded,'definitions',target['id'])),nodes[0]['id'],1),1.8)

    def test_zero_offset_does_not_establish_a_zero_height(self):
        self.gm['paired_ptset_id']='';self.node['attrs'].update(PAXI='X',PDIS='PARAM 3',PHEI='PARAM 3')
        scene=geo.build_scene(self.data,self.gm);self.assertFalse(scene.issues)
        self.assertAlmostEqual(self.extent(scene,self.node['id'],0),1.2)

    def test_negative_shapes_and_parameter_families_share_only_the_same_reference(self):
        other=schema.add_element(self.gm,'NSCY');other['attrs'].update(PAXI='X',PDIS='0',PHEI='PARAM 3',PDIA='IPARAM 1')
        scene=geo.build_scene(self.data,self.gm);old=self.extent(scene,self.node['id'],1)
        state=scene.preview.resize(other['id'],1,1.1);store(self.data,self.gm,state)
        scene=geo.build_scene(self.data,self.gm)
        self.assertAlmostEqual(self.extent(scene,other['id'],1),1.1);self.assertAlmostEqual(self.extent(scene,self.node['id'],1),old)

    def test_ambiguous_oblique_resize_is_rejected_without_modifying_saved_data(self):
        self.node['attrs']['PAXI']='X45Y';remember(self.data,self.gm);before=copy.deepcopy(self.data)
        with self.assertRaisesRegex(ValueError,'一意に決められません'):GeometryPreview(self.data,self.gm).resize(self.node['id'],0,3)
        self.assertEqual(self.data,before)

    def test_first_parameter_assignment_uses_the_previously_resized_draft(self):
        self.gm['paired_ptset_id']='';self.node['attrs'].update(PAXI='X',PDIA='',PHEI='')
        self.node[geo.SCALE_KEY]=[2,3,3];remember(self.data,self.gm)
        self.node['attrs'].update(PDIA='PARAM 1',PHEI='PARAM 3');remember(self.data,self.gm)
        scene=geo.build_scene(self.data,self.gm)
        self.assertAlmostEqual(self.extent(scene,self.node['id'],0),2.4)
        self.assertAlmostEqual(self.extent(scene,self.node['id'],1),1.95)

    def test_invalid_known_expressions_report_errors_without_overwriting_shared_values(self):
        remember(self.data,self.gm);saved=copy.deepcopy(self.pt[DIMENSIONS_KEY])
        self.node['attrs']['PDIA']='PARAM 3 / 0';scene=geo.build_scene(self.data,self.gm)
        self.assertFalse(scene.meshes);self.assertIn('ゼロ',scene.issues[0]);self.assertEqual(self.pt[DIMENSIONS_KEY],saved)

    def test_unset_angle_and_missing_point_do_not_get_guessed_draft_dimensions(self):
        self.node['attrs']['PDIA']='PARAM 99 * TAN(ANGL / 2)'
        scene=geo.build_scene(self.data,self.gm);self.assertFalse(scene.meshes);self.assertIn('ANGL',scene.issues[0])
        self.node['attrs'].update(PDIA='PARAM 1',PAXI='P999')
        scene=geo.build_scene(self.data,self.gm);self.assertFalse(scene.meshes);self.assertIn('P999',scene.issues[0])

    def test_recalling_a_preset_with_a_new_profile_preserves_the_matching_points_values(self):
        profile=presets.add(self.data,'別のPARAM規則');presets.bind(self.data,self.pt,profile['id']);remember_points(self.data,self.pt)
        expected=self.pt[DIMENSIONS_KEY]['values']['PARAM']['P3']
        source=copy.deepcopy(self.gm);source.update(id='source',paired_ptset_id='',parameter_preset_id=profile['id'])
        source['elements'][0]['attrs']['PAXI']='X';remember(self.data,source)
        state=GeometryPreview(self.data,source).resize(source['elements'][0]['id'],0,3);store(self.data,source,state)
        record=element_library.register(self.data,source,'別規則の形状')
        self.gm['elements']=[];nodes=element_library.recall(self.data,self.gm,record['id'])
        self.assertEqual(presets.selected_id(self.data,self.gm),profile['id'])
        self.assertAlmostEqual(self.extent(geo.build_scene(self.data,self.gm),nodes[0]['id'],0),expected)
