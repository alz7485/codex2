"""Synthetic actual/draft coverage for every primitive, including negative forms."""
import copy
import math
import unittest
from catalog_studio import geometry_scene as geo,element_schema as schema
from test_geometry_scene import fixture

CONFIGS={
 'SBOX':dict(PXLE='PARAM 3',PYLE='PARAM 1',PZLE='PARAM 1 / 2'),
 'SCON':dict(PAXI='X',PDIA='PARAM 1',PDIS='PARAM 3'),
 'LCYL':dict(PAXI='X',PDIA='PARAM 1',PBDI='0',PTDI='PARAM 3'),
 'SCYL':dict(PAXI='X',PDIA='PARAM 1',PDIS='0',PHEI='PARAM 3'),
 'SSLC':dict(PAXI='X',PDIA='PARAM 1',PDIS='0',PHEI='PARAM 3',PXTS='0',PYTS='0',PXBS='0',PYBS='0'),
 'SDIS':dict(PAXI='X',PDIA='PARAM 1',PDIS='0'),
 'SSPH':dict(PAXI='X',PDIA='PARAM 1',PDIS='0'),
 'LSNO':dict(PAAX='X',PBAX='',PBDI='0',PTDI='PARAM 3',PBDM='PARAM 1',PTDM='PARAM 1 / 2',POFF='0'),
 'LPYR':dict(PAAX='X',PBAX='Y',PCAX='Z',PBDI='0',PTDI='PARAM 3',PBBT='PARAM 1',PCBT='PARAM 1',PBTP='PARAM 1 / 2',PCTP='PARAM 1 / 2',PBOF='0',PCOF='0'),
 'SLINE':dict(PTSPOS='X 0 Y 0 Z 0',PTEPOS='X (PARAM 3) Y 0 Z 0'),
 'LINE':dict(PTS='P1 P2'),
 'SCTO':dict(PAAX='P1',PBAX='P2',PDIA='PARAM 1'),
 'SRTO':dict(PAAX='P1',PBAX='P2',PDIA='PARAM 1',PHEI='PARAM 1 / 2'),
 'SEXT':dict(PX='0',PY='0',PZ='0',PAAX='X',PBAX='Y',PHEI='PARAM 3'),
 'SREV':dict(PX='0',PY='0',PZ='0',PAAX='X',PBAX='Y',PANGLE='270'),
}
UNSUPPORTED={'BOXI','TUBE','SDSH'}

class ActualGeometryMatrix(unittest.TestCase):
 def setup_shape(self,kind):
  data,pt,gm,scom,_=fixture();gm['elements']=[]
  pt['elements']=[]
  for x,y,direction in ((100,0,'-Y'),(0,100,'-X')):
   p=schema.add_element(pt,'PTCAR');p['attrs'].update(PX=str(x),PY=str(y),PZ='0',PTCDIR=direction)
  node=schema.add_element(gm,kind);base=schema.positive(kind)
  node['attrs'].update(CONFIGS.get(base,{}))
  if base in ('SEXT','SREV'):
   loop=schema.add_child(node)
   for x,y in ((0,10),(20,10),(20,20),(0,20)):
    v=schema.add_child(loop);v['attrs'].update(PX=str(x),PY=str(y),PRAD='0')
  return data,gm,scom,node

 def test_every_supported_actual_primitive_and_negative_counterpart(self):
  self.assertEqual(set(schema.GM_TYPES),set(CONFIGS)|UNSUPPORTED)
  for kind in list(CONFIGS)+[k for k,v in schema.NEGATIVE_BASE.items() if v in CONFIGS]:
   with self.subTest(kind=kind):
    data,gm,scom,node=self.setup_shape(kind);before=copy.deepcopy(node)
    draft=geo.build_scene(data,gm,scom,False)
    actual=geo.build_scene(data,gm,scom,True)
    self.assertEqual(draft.issues,[]);self.assertEqual(len(draft.meshes),1)
    self.assertEqual(actual.issues,[]);self.assertEqual(len(actual.meshes),1)
    self.assertEqual(actual.meshes[0].negative,kind in schema.NEGATIVE_BASE)
    self.assertTrue(actual.meshes[0].vertices)
    self.assertTrue(all(math.isfinite(v) for p in actual.meshes[0].vertices for v in p))
    self.assertEqual(node,before)

 def test_axial_shapes_in_six_directions_with_scom_values(self):
  bases={'SCON','LCYL','SCYL','SSLC','SDIS','SSPH'}
  for kind in list(bases)+[k for k,v in schema.NEGATIVE_BASE.items() if v in bases]:
   for axis in ('X','-X','Y','-Y','Z','-Z'):
    with self.subTest(kind=kind,axis=axis):
     data,gm,scom,node=self.setup_shape(kind);node['attrs']['PAXI']=axis
     actual=geo.build_scene(data,gm,scom,True)
     self.assertEqual(actual.issues,[]);self.assertEqual(len(actual.meshes),1)
     self.assertTrue(all(math.isfinite(v) for p in actual.meshes[0].vertices for v in p))

 def test_lsno_and_negative_radius_mode_unset_diameter_and_six_axes(self):
  for kind in ('LSNO','NLSN'):
   for axis in ('X','-X','Y','-Y','Z','-Z'):
    with self.subTest(kind=kind,axis=axis):
     data,gm,scom,node=self.setup_shape(kind)
     node['attrs'].update(PAAX=axis,PTDM='unset',PBDM='unset',PTRA='PARAM 1 / 4',PBRA='PARAM 1 / 2')
     scene=geo.build_scene(data,gm,scom,True)
     self.assertEqual(scene.issues,[]);self.assertEqual(len(scene.meshes),1)
     i='XYZ'.index(axis[-1]);bounds=[(min(p[j] for p in scene.meshes[0].vertices),max(p[j] for p in scene.meshes[0].vertices)) for j in range(3)]
     self.assertEqual(bounds[i],(-100,0) if axis.startswith('-') else (0,100))
     for j in range(3):
      if j!=i:self.assertEqual(bounds[j],(-20,20))

 def test_unimplemented_actual_shapes_report_reason_including_negatives(self):
  for kind in list(UNSUPPORTED)+[k for k,v in schema.NEGATIVE_BASE.items() if v in UNSUPPORTED or v is None]:
   with self.subTest(kind=kind):
    data,gm,scom,node=self.setup_shape(kind)
    node['attrs'].update(PAXI='X',PDIA='PARAM 1',PHEI='PARAM 3',PDIS='0')
    scene=geo.build_scene(data,gm,scom,True)
    self.assertFalse(scene.meshes);self.assertTrue(scene.issues)
