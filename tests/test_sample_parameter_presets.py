import unittest
from catalog_studio import project,presets,scom_sheet
from catalog_studio.sample_parameter_presets import ITEMS

class ReferencePresetTests(unittest.TestCase):
 def test_transcribed_numbers_types_labels_and_text_columns(self):
  data=project.sample();project.validate(data)
  rule=presets.get(data,'sample-valve-reference-29')
  self.assertEqual(len(rule['parameters']),29)
  self.assertEqual([p['id'] for p in rule['parameters']],['P'+str(i) for i in range(1,30)])
  self.assertEqual([p['english_name'] for p in rule['parameters']],[item[0] for item in ITEMS])
  self.assertEqual(rule['parameters'][19]['english_name'],'BONNET HIGHT')
  self.assertEqual([p['id'] for p in rule['parameters'] if p['value_type']=='word'],['P4','P5','P6'])
  candidate,labels=scom_sheet.text_columns(data,data['cates'][0]['id'],rule['id'],True)
  self.assertEqual(len(labels),30);self.assertIn('NOM BORE',labels['P1']);self.assertNotEqual(labels['P1'],labels['P2'])
  self.assertEqual(len(data['texts']),0);self.assertEqual(len(candidate['texts']),29)
  self.assertNotIn('P30',[p['id'] for p in rule['parameters']])

 def test_add_to_existing_project_does_not_rebind_or_overwrite(self):
  import copy
  from catalog_studio.sample_parameter_presets import add_reference_preset
  data=project.sample();data['parameter_presets']=[];original=copy.deepcopy(data)
  record,added=add_reference_preset(data);self.assertTrue(added)
  before=copy.deepcopy(data);record2,added=add_reference_preset(data)
  self.assertFalse(added);self.assertEqual(data,before);self.assertIs(record2,record)
  without=copy.deepcopy(data);without['parameter_presets']=[];self.assertEqual(without,original)
