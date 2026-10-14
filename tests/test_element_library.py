import copy
import tempfile
import unittest
from pathlib import Path
from catalog_studio import element_library as library,element_schema as schema,project,presets,booklet


class ElementLibraryTests(unittest.TestCase):
    def setUp(self):
        self.data=project.sample()
        self.pt={'id':'pt-test','name':'/POINTS','kind':'PTSET','revision':'01','elements':[]}
        for number in (10,20):
            point=schema.add_element(self.pt,'PTAXI');point['attrs'].update(NUMB=str(number),PDIS='PARAM 3 / 2')
        self.pt['elements'][1]['attrs']['PAXI']='P10'
        self.gm={'id':'gm-test','name':'/GEOMETRY','kind':'GMSET','revision':'01','elements':[]}
        line=schema.add_element(self.gm,'LINE');line['attrs']['PTS']='P10 T20 P0';self.line=line
        self.data['definitions'].extend((self.pt,self.gm))
        self.data['scoms'][0].update(ptset_id=self.pt['id'],gmset_id=self.gm['id'])
    def target(self,kind='PTSET'):
        d={'id':'target-'+kind,'name':'/TARGET-'+kind,'kind':kind,'revision':'01','elements':[]}
        self.data['definitions'].append(d);return d
    def test_reorder_keeps_point_identity_and_rewrites_linked_line_and_axis(self):
        first,second=self.pt['elements'];first['attrs']['PDIS']='P1 / 2'
        self.assertTrue(library.reorder(self.data,self.pt,second['id'],0))
        self.assertEqual(self.pt['elements'],[second,first])
        self.assertEqual([p['attrs']['NUMB'] for p in self.pt['elements']],['1','2'])
        self.assertEqual(second['attrs']['PAXI'],'P2');self.assertEqual(first['attrs']['PDIS'],'P1 / 2')
        self.assertEqual(self.line['attrs']['PTS'],'P2 T1 P0')
    def test_shared_geometry_rejects_ambiguous_renumbering_without_any_change(self):
        self.data['scoms'][1]['gmset_id']=self.gm['id'];before=copy.deepcopy(self.data)
        with self.assertRaises(ValueError):library.reorder(self.data,self.pt,self.pt['elements'][0]['id'],1)
        self.assertEqual(self.data,before)
    def test_invalid_point_numbers_reject_reorder_atomically(self):
        self.pt['elements'][1]['attrs']['NUMB']='10';before=copy.deepcopy(self.data)
        with self.assertRaises(ValueError):library.reorder(self.data,self.pt,self.pt['elements'][0]['id'],1)
        self.assertEqual(self.data,before)
    def test_reorder_does_not_modify_saved_book(self):
        self.data['books'].append(booklet.snapshot(self.data,scom_ids=[self.data['scoms'][0]['id']],spec_ids=[]))
        frozen=copy.deepcopy(self.data['books'])
        library.reorder(self.data,self.pt,self.pt['elements'][0]['id'],1)
        self.assertEqual(self.data['books'],frozen)
    def test_register_and_repeated_recall_are_independent_complete_groups(self):
        record=library.register(self.data,self.pt,'二点の配置');saved=copy.deepcopy(record);target=self.target()
        self.pt['elements'][0]['attrs']['PDIS']='source changed'
        first=library.recall(self.data,target,record['id']);second=library.recall(self.data,target,record['id'])
        self.assertEqual(len(target['elements']),4)
        self.assertEqual([e['attrs']['NUMB'] for e in target['elements']],['1','2','3','4'])
        self.assertEqual(first[1]['attrs']['PAXI'],'P1');self.assertEqual(second[1]['attrs']['PAXI'],'P3')
        self.assertEqual(len({e['id'] for e in target['elements']}),4)
        first[0]['attrs']['PDIS']='called changed';self.assertEqual(record,saved)
        self.assertEqual(second[0]['attrs']['PDIS'],'PARAM 3 / 2')
    def test_group_edit_affects_future_calls_only_and_roundtrips(self):
        record=library.register(self.data,self.pt,'元の配置');target=self.target()
        earlier=library.recall(self.data,target,record['id']);before=copy.deepcopy(earlier)
        draft=copy.deepcopy(record);draft['elements'][0]['attrs']['PDIS']='PARAM 3'
        library.update(self.data,record['id'],draft,'更新した配置','説明')
        self.assertEqual(earlier,before);later=library.recall(self.data,target,record['id'])
        self.assertEqual(later[0]['attrs']['PDIS'],'PARAM 3')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'library.json';project.save(self.data,path);self.assertEqual(project.load(path),self.data)
    def test_geometry_group_preserves_loop_children_without_registering_numbers(self):
        extrusion=schema.add_element(self.gm,'SEXT');loop=schema.add_child(extrusion)
        for x,y in ((0,0),(1,0),(0,1)):
            schema.add_child(loop)['attrs'].update(PX=str(x),PY=str(y),PRAD='0')
        record=library.register(self.data,self.gm,'線と輪郭');target=self.target('GMSET')
        elements=library.recall(self.data,target,record['id'])
        self.assertEqual(len(elements[1]['children'][0]['children']),3)
        self.assertTrue(all('NUMB' not in e['attrs'] for e in schema.walk(elements)))
        self.assertTrue({e['id'] for e in schema.walk(elements)}.isdisjoint({e['id'] for e in schema.walk(record['elements'])}))
    def test_parameter_profile_is_kept_and_incompatible_calls_are_atomic(self):
        profile=presets.add(self.data,'配置の規則');presets.bind(self.data,self.pt,profile['id'])
        record=library.register(self.data,self.pt,'規則を持つ配置');target=self.target()
        library.recall(self.data,target,record['id']);self.assertEqual(presets.selected_id(self.data,target),profile['id'])
        other=presets.add(self.data,'別の規則');presets.bind(self.data,target,other['id']);before=copy.deepcopy(self.data)
        with self.assertRaises(ValueError):library.recall(self.data,target,record['id'])
        self.assertEqual(self.data,before)
    def test_parameter_names_rename_in_library_and_library_prevents_profile_deletion(self):
        profile=presets.add(self.data,'配置の規則');presets.bind(self.data,self.pt,profile['id'])
        self.pt['elements'][0]['attrs']['PDIS']='全長 / 2';record=library.register(self.data,self.pt,'名称を使う配置')
        self.data['definitions'].remove(self.pt)
        with self.assertRaises(ValueError):presets.remove(self.data,profile['id'])
        presets.rename(self.data,'P3','面間距離',profile['id'])
        self.assertEqual(record['elements'][0]['attrs']['PDIS'],'面間距離 / 2')
