import copy
import math
import unittest
from catalog_studio import expressions as e, project, geometry_scene as geo, element_library
from catalog_studio.piping_samples import add_samples
from catalog_studio.point_preview import PointPreview

class TanfTests(unittest.TestCase):
    def test_prefix_and_function_forms_refs_and_export(self):
        for angle in (0,45,90,-45):
            expected=152*math.tan(math.radians(angle/2))
            for text in (f'TANF 152 {angle}',f'TANF(152,{angle})'):
                self.assertAlmostEqual(e.evaluate(text),expected)
        text='TANF PARAM 4 DDANGLE'
        contexts={'PARAM':{'P4':152}}
        self.assertAlmostEqual(e.evaluate(text,contexts,{'DDANGLE':45}),62.96046148071044)
        root=e.parse(text)
        self.assertEqual(e.refs(root),{('PARAM','P4')})
        self.assertEqual(e.attribute_refs(root),{'DDANGLE'})
        for output in (e.normalized(text),e.e3d(text)):
            self.assertIn('TANF',output)
            self.assertAlmostEqual(e.evaluate(output,contexts,{'DDANGLE':90}),152)
        self.assertAlmostEqual(e.evaluate('(TANF(152,45) + TANF 152 90)'),214.96046148071044)

    def test_units_missing_values_and_singularities(self):
        self.assertAlmostEqual(e.evaluate('TANF(0.152m,90deg)',expected='DIST'),152)
        self.assertAlmostEqual(e.evaluate('TANF(152,90)',expected='DIST'),152)
        for text in ('TANF(152,180)','TANF(152,-180)','TANF(152,540)',
                     'TANF(90deg,45deg)','TANF(152mm,20mm)',"TANF('word',90)",
                     'TANF(152)','TANF(152,90,45)','TANF PARAM 4 DDANGLE'):
            with self.subTest(text=text),self.assertRaises(ValueError):e.evaluate(text)

    def test_bend_preview_radius_and_point_positions_at_two_angles(self):
        data=project.sample();add_samples(data)
        gm=next(d for d in data['definitions'] if d.get('sample')=='piping-bend' and d['kind']=='GMSET')
        pt=project.get(data,'definitions',gm['paired_ptset_id'])
        before=copy.deepcopy(data)
        for angle in (45,90):
            pt['model_settings']['DDANGLE']=gm['model_settings']['DDANGLE']=angle
            preview=PointPreview(data,pt)
            length=1.5*math.tan(math.radians(angle/2))
            self.assertAlmostEqual(preview.point(1)[0][0],-length)
            self.assertAlmostEqual(preview.point(2)[0][0],length*math.cos(math.radians(angle)))
            self.assertAlmostEqual(preview.point(2)[0][1],length*math.sin(math.radians(angle)))
            scene=geo.build_scene(data,gm)
            self.assertEqual(scene.issues,[])
            mesh=next(m for m in scene.meshes if m.kind=='SCTO')
            centers=[tuple(sum(v[i] for v in mesh.vertices[j:j+24])/24 for i in range(3)) for j in range(0,600,24)]
            start,end=scene.points[1][0],scene.points[2][0]
            for actual,expected in zip(centers[0],start):self.assertAlmostEqual(actual,expected)
            for actual,expected in zip(centers[-1],end):self.assertAlmostEqual(actual,expected)
            center=(start[0],1.5,0.)
            for p in centers:self.assertAlmostEqual(math.dist(p,center),1.5)
        pt['model_settings']['DDANGLE']=gm['model_settings']['DDANGLE']=90.
        self.assertEqual(data,before)

    def test_recalled_bend_presets_have_design_angle(self):
        data=project.sample()
        for kind in ('PTSET','GMSET'):
            target={'id':'test','name':'/TEST-'+kind,'kind':kind,'elements':[]}
            element_library.recall(data,target,'builtin-piping-bend-'+kind.lower())
            self.assertEqual(target['model_settings']['DDANGLE'],90)

    def test_macro_roundtrip_preserves_tanf_semantics(self):
        from catalog_studio import macro_export, macro_import
        data=project.sample();add_samples(data)
        point=next(d for d in data['definitions'] if d.get('sample')=='piping-bend' and d['kind']=='PTSET')
        text=macro_export.creation_text([point])
        self.assertIn('TANF',text)
        loaded=macro_import.parse(text).definitions[0]
        for node in loaded['elements']:
            self.assertAlmostEqual(e.evaluate(node['attrs']['PDIS'],{'PARAM':{'P4':152}},{'DDANGLE':90}),152)

    def test_preview_does_not_replace_singularity_with_provisional_value(self):
        data=project.sample();add_samples(data)
        gm=next(d for d in data['definitions'] if d.get('sample')=='piping-bend' and d['kind']=='GMSET')
        pt=project.get(data,'definitions',gm['paired_ptset_id'])
        pt['model_settings']['DDANGLE']=gm['model_settings']['DDANGLE']=180.
        scene=geo.build_scene(data,gm)
        self.assertTrue(scene.issues)
        self.assertFalse(any(m.kind=='SCTO' for m in scene.meshes))
