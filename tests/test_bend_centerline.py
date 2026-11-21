import copy
import math
import unittest
from catalog_studio import project, geometry_scene as geo
from catalog_studio.piping_samples import add_samples

class BendCenterlineTests(unittest.TestCase):
    def test_line_follows_torus_center_in_preview_and_actual_modes(self):
        data=project.sample();add_samples(data)
        gm=next(d for d in data['definitions'] if d.get('sample')=='piping-bend' and d['kind']=='GMSET')
        pt=project.get(data,'definitions',gm['paired_ptset_id'])
        scom=copy.deepcopy(next(s for s in data['scoms'] if s.get('sample')=='piping-bend'))
        scom['expression_contexts']={'IPARAM':{'P1':0}}
        for angle in (45,90):
            gm['model_settings']['DDANGLE']=pt['model_settings']['DDANGLE']=angle
            for actual in (False,True):
                for points in ('P1 TO P2','P1 P2','P2 P1'):
                    with self.subTest(angle=angle,actual=actual,points=points):
                        gm['elements'][0]['attrs']['PTS']=points
                        scene=geo.build_scene(data,gm,scom,actual)
                        self.assertEqual(scene.issues,[])
                        line=next(m for m in scene.meshes if m.kind=='LINE')
                        torus=next(m for m in scene.meshes if m.kind=='SCTO')
                        centers=[tuple(sum(v[i] for v in torus.vertices[j:j+24])/24 for i in range(3)) for j in range(0,600,24)]
                        if points=='P2 P1':centers.reverse()
                        self.assertEqual(len(line.vertices),25)
                        for point,center in zip(line.vertices,centers):
                            for a,b in zip(point,center):self.assertAlmostEqual(a,b)
                        self.assertEqual(line.lines,[tuple(range(25))])

    def test_straight_skew_and_non_circular_pairs_keep_straight_segments(self):
        data=project.sample();add_samples(data)
        gm=next(d for d in data['definitions'] if d.get('sample')=='piping-bend' and d['kind']=='GMSET')
        pt=project.get(data,'definitions',gm['paired_ptset_id']);gm['elements']=gm['elements'][:1]
        for axes in (('-X','X'),('-X','Z')):
            for node,axis in zip(pt['elements'],axes):node['attrs'].update(PDIS='100',PAXI=axis)
            # Unequal radial distances also must not invent an arc.
            if axes[1]=='Z':pt['elements'][1]['attrs']['PDIS']='70'
            scene=geo.build_scene(data,gm)
            self.assertEqual(scene.issues,[])
            self.assertEqual(len(scene.meshes[0].vertices),2)
