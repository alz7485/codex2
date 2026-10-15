import copy
import unittest
from catalog_studio import geometry_scene as geo, project, element_schema as schema
from catalog_studio.surface_render import alpha_surface, feature_edges, inside_polygon


class SurfaceRenderTests(unittest.TestCase):
    def test_alpha_compositing_reveals_rear_colour_in_overlapping_faces(self):
        polygons=[([(2,2),(18,2),(18,18),(2,18)],'#ff0000'),([(8,8),(24,8),(24,24),(8,24)],'#0000ff')]
        image=alpha_surface((30,30),polygons,.5)
        red,green,blue,alpha=image.getpixel((10,10))
        self.assertTrue(red>0 and blue>red and green==0)
        self.assertTrue(180<alpha<205)
        self.assertEqual(image.getpixel((0,0)),(0,0,0,0))

    def test_opacity_endpoints_and_offscreen_faces_are_clipped(self):
        polygons=[([(-1000,-1000),(1000,-1000),(1000,1000),(-1000,1000)],'#ff0000'),([(2,2),(8,2),(8,8),(2,8)],'#0000ff')]
        self.assertIsNone(alpha_surface((10,10),polygons,0).getbbox())
        opaque=alpha_surface((10,10),polygons,1)
        self.assertEqual(opaque.getpixel((5,5)),(0,0,255,255))
        self.assertEqual(opaque.getpixel((0,0)),(255,0,0,255))
        self.assertIsNone(alpha_surface((10,10),[([(20,20),(30,20),(30,30)],'#ff0000')],.5).getbbox())

    def mesh(self,kind):
        data=project.sample();definition={'id':'test','name':'/SHAPES','kind':'GMSET','elements':[]}
        node=schema.add_element(definition,kind)
        return geo.build_scene(data,definition).meshes[0]

    def test_cylinder_hides_side_divisions_and_keeps_end_rims_and_contour(self):
        mesh=self.mesh('SCYL');before=copy.deepcopy(mesh);edges=feature_edges(mesh,(.4,.3,.7))
        axial=[(a,b) for a,b in edges if abs(mesh.vertices[a][0]-mesh.vertices[b][0])>.5]
        self.assertEqual(len(axial),2)
        self.assertEqual(len(edges),50)  # 2 circular rims of 24 segments, 2 silhouette edges.
        self.assertEqual(mesh,before)
        self.assertNotEqual(set(edges),set(feature_edges(mesh,(.4,-.7,.3))))

    def test_coplanar_diagonals_are_hidden_but_box_corners_remain(self):
        mesh=self.mesh('SBOX');triangles=[]
        for a,b,c,d in mesh.faces:triangles.extend(((a,b,c),(a,c,d)))
        mesh.faces=triangles
        self.assertEqual(len(feature_edges(mesh,(.4,.3,.7))),12)
        sphere=self.mesh('SSPH');self.assertLess(len(feature_edges(sphere,(.4,.3,.7))),80)

    def test_transparent_face_hit_testing_handles_concavity_and_empty_faces(self):
        points=[(0,0),(10,0),(10,4),(4,4),(4,10),(0,10)]
        self.assertTrue(inside_polygon(2,8,points));self.assertFalse(inside_polygon(8,8,points))
        self.assertFalse(inside_polygon(3,3,[]))
