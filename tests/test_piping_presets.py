import copy
import unittest
from catalog_studio import project, element_library
from catalog_studio.piping_presets import add_presets

class PipingPresetsTests(unittest.TestCase):
    def test_separate_types_and_idempotence(self):
        data=project.sample();before=copy.deepcopy(data)
        self.assertEqual(add_presets(data),0);self.assertEqual(data,before)
        self.assertEqual([(r['name'],r['kind']) for r in data['element_presets']],
                         [('標準 PIPE','PTSET'),('標準 WELD','PTSET'),('標準 BEND','PTSET'),('標準 BEND','GMSET')])
        project.validate(data)

    def test_photo_attributes_and_recall(self):
        data=project.sample()
        lookup=lambda part,kind:element_library.get(data,'builtin-piping-'+part+'-'+kind)
        pipe=lookup('pipe','ptset');weld=lookup('weld','ptset');bend=lookup('bend','ptset');gm=lookup('bend','gmset')
        self.assertEqual(len(pipe['elements']),1)
        self.assertEqual([e['attrs']['PCON'] for e in weld['elements']],['PARAM 2','PARAM 3'])
        self.assertEqual([e['attrs']['PAXI'] for e in weld['elements']],['-X','X'])
        self.assertEqual(bend['elements'][1]['attrs']['PAXI'],'X DDANGLE Y')
        self.assertTrue(all(e['attrs']['PDIS']=='TANF PARAM 4 DDANGLE' for e in bend['elements']))
        self.assertEqual(gm['parameter_preset_id'],bend['parameter_preset_id'])
        self.assertEqual(gm['elements'][0]['attrs']['PTS'],'P1 TO P2')
        self.assertEqual(gm['elements'][1]['attrs']['PDIA'],'SUM PARAM 2 IPARAM 1')
        target={'id':'test','kind':'PTSET','elements':[]}
        element_library.recall(data,target,pipe['id'])
        self.assertEqual(target['elements'][0]['attrs']['PBOR'],'PARAM 1')
        self.assertNotEqual(target['elements'][0]['id'],pipe['elements'][0]['id'])

    def test_limit_failure_is_atomic(self):
        data=project.sample();data['element_presets']=[]
        data['parameter_presets']=[{'id':str(i)} for i in range(1000)]
        before=copy.deepcopy(data)
        with self.assertRaises(ValueError):add_presets(data)
        self.assertEqual(data,before)
