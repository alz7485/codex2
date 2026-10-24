import copy
import tempfile
import unittest
from pathlib import Path
from catalog_studio import project, valve_sample, pairing, geometry_scene, macro_export, macro_import


class ValveSampleTests(unittest.TestCase):
    def test_independent_rules_pairing_and_real_dimensions(self):
        data=valve_sample.standalone();pt,gm=data['definitions'];scom=data['scoms'][0]
        self.assertEqual(project.issues(data),[])
        self.assertEqual(pairing.resolve(data,gm)['pointset']['id'],pt['id'])
        self.assertEqual(pt['parameter_preset_id'],gm['parameter_preset_id'])
        scene=geometry_scene.build_scene(data,gm,scom,True)
        self.assertFalse(scene.issues);self.assertEqual(len(scene.meshes),7)
        self.assertEqual(scene.points[1][0],(-120.,0.,0.))
        self.assertEqual(scene.points[2][0],(120.,0.,0.))
        self.assertEqual(scene.points[3][0],(0.,0.,230.))
        heights=[vertex[2] for mesh in scene.meshes for vertex in mesh.vertices]
        self.assertAlmostEqual(max(heights)-min(heights),scom['values']['P7'])
        scom['values']['P3']=300
        changed=geometry_scene.build_scene(data,gm,scom,True)
        self.assertEqual(changed.points[1][0],(-150.,0.,0.))
        self.assertEqual(changed.points[2][0],(150.,0.,0.))

    def test_shared_schematic_preview_and_export_do_not_use_scom_values(self):
        data=valve_sample.standalone();pt,gm=data['definitions'];before=copy.deepcopy(data)
        scene=geometry_scene.build_scene(data,gm)
        self.assertFalse(scene.issues);self.assertEqual(len(scene.meshes),7)
        self.assertAlmostEqual(scene.points[2][0][0]-scene.points[1][0][0],2.4)
        text=macro_export.creation_text([pt,gm]);parsed=macro_import.parse(text).definitions
        self.assertEqual(len(parsed[0]['elements']),3)
        self.assertEqual(len(parsed[1]['elements']),7)
        self.assertIn('PHEI (-PARAM[3])',text)
        self.assertNotIn('89.1',text)
        self.assertEqual(data,before)

    def test_adding_twice_does_not_change_existing_data_or_conflict(self):
        original=project.sample();before=copy.deepcopy(original)
        first,ids=valve_sample.prepare(original);second,other=valve_sample.prepare(first)
        self.assertEqual(original,before)
        for key in ('definitions','scoms','cates'):
            self.assertEqual(second[key][:len(first[key])],first[key])
            names=[r['name'] for r in second[key]]
            self.assertEqual(len(names),len(set(names)))
        self.assertNotEqual(ids['ptset_id'],other['ptset_id'])
        self.assertNotEqual(ids['preset_id'],other['preset_id'])
        self.assertEqual(second['parameters'],original['parameters'])
        self.assertEqual(project.issues(second),[])

    def test_json_and_sjis_macro_roundtrip(self):
        data=valve_sample.standalone()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'valve.json';project.save(data,path)
            self.assertEqual(project.load(path),data)
            path=Path(folder)/'valve.mac';macro_export.save(path,macro_export.creation_text(data['definitions']))
            text,_=macro_import.read_text(path)
            self.assertEqual(len(macro_import.parse(text).definitions),2)
