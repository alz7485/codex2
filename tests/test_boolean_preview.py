import copy
import unittest
from catalog_studio import geometry_scene as g,element_schema as s
from catalog_studio.boolean_preview import solid,subtract

class BooleanPreviewTests(unittest.TestCase):
 def setUp(self):
  try:import manifold3d,numpy
  except ImportError as exc:self.skipTest(str(exc))
 def mesh(self,kind,attrs):
  return g.build_mesh(dict(id=kind,name=kind,type=kind,attrs=attrs),g.Resolver({'parameters':[]},{},None,None,True,g.Scene()))
 def test_through_hole_reduces_volume_and_preserves_source(self):
  box=self.mesh('SBOX',dict(PXLE='2',PYLE='2',PZLE='2'))
  cut=self.mesh('NSCY',dict(PAXI='Z',PDIS='-2',PHEI='4',PDIA='1'))
  before=copy.deepcopy((box,cut));result=subtract(box,[cut])
  expected=8-2*24*.5**2*__import__('math').sin(2*__import__('math').pi/24)/2
  self.assertAlmostEqual(solid(result).volume(),expected,places=5)
  self.assertEqual((box,cut),before);self.assertEqual(result.ident,box.ident)
 def test_non_intersecting_cut_and_complete_removal(self):
  box=self.mesh('SBOX',dict(PXLE='1',PYLE='1',PZLE='1'))
  far=self.mesh('NSBO',dict(PX='10',PXLE='1',PYLE='1',PZLE='1'))
  self.assertAlmostEqual(solid(subtract(box,[far])).volume(),1.)
  big=self.mesh('NSBO',dict(PXLE='3',PYLE='3',PZLE='3'))
  self.assertEqual(subtract(box,[big]).faces,[])
 def test_open_mesh_is_reported_instead_of_claiming_a_cut(self):
  mesh=self.mesh('SCYL',dict(PAXI='Z',PHEI='1',PDIA='1',TVISI='FALSE'))
  with self.assertRaises(ValueError):solid(mesh)
 def test_all_napp_masks_follow_gmset_self_and_direct_owner(self):
  from catalog_studio.boolean_preview import apply
  a=self.mesh('SBOX',dict(PXLE='2',PYLE='2',PZLE='2'));a.ident='owner'
  b=copy.deepcopy(a);b.ident='other'
  cut=self.mesh('NSCY',dict(PAXI='Z',PDIS='-2',PHEI='4',PDIA='1'));cut.ident='cut'
  for mask in range(8):
   definition={'elements':[dict(id='owner',children=[dict(id='cut',attrs={'NAPP':str(mask)})]),dict(id='other')]}
   scene=g.Scene(meshes=[copy.deepcopy(a),copy.deepcopy(b),copy.deepcopy(cut)])
   before=copy.deepcopy(definition);apply(scene,definition)
   va,vb=[solid(m).volume() for m in scene.meshes[:2]]
   self.assertEqual(va<7.9,bool(mask&6));self.assertEqual(vb<7.9,bool(mask&4))
   self.assertEqual(definition,before);self.assertFalse(scene.issues)
 def test_root_negative_owner_has_no_target_but_self_does(self):
  from catalog_studio.boolean_preview import apply
  a=self.mesh('SBOX',dict(PXLE='2',PYLE='2',PZLE='2'));a.ident='a'
  c=self.mesh('NSBO',dict(PXLE='1',PYLE='1',PZLE='3'));c.ident='c'
  for mask,expected in [('2',8.),('1',8.),('4',6.)]:
   scene=g.Scene(meshes=[copy.deepcopy(a),copy.deepcopy(c)])
   apply(scene,{'elements':[{'id':'a'},{'id':'c','attrs':{'NAPP':mask}}]})
   self.assertAlmostEqual(solid(scene.meshes[0]).volume(),expected)
 def test_depth_buffer_resolves_intersecting_faces_per_pixel(self):
  from catalog_studio.surface_render import opaque_surface,visible_segments
  triangle=[(0,0),(10,0),(0,10)]
  image,depth=opaque_surface((12,12),[(triangle,[0,10,0],'#ff0000'),(triangle,[5,5,5],'#0000ff')])
  self.assertEqual(image.getpixel((1,1)),(0,0,255,255))
  self.assertEqual(image.getpixel((7,1)),(255,0,0,255))
  self.assertEqual(visible_segments((1,1),(2,1),0,0,depth),[])
