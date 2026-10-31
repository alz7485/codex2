import copy
import tempfile
import unittest
from pathlib import Path
from catalog_studio import companion_macro as macros,project,macro_export,macro_import,macro_destinations

SOURCE="""INPUT BEGIN
NEW SDTEXT /DEMO-DETAIL
SKEY 'VGBW'
RTEX '弁 BW BW'
END
OLD SDTEXT /DEMO-DETAIL
LOCK
INPUT END SDTEXT /DEMO-DETAIL
INPUT FINISH
"""
PROP="""NEW CMPTYPE /DEMO-PROP
NEW CMPDATA /DEMO-PROP-A
CWEI (9.1)
END
NEW CMPDATA /DEMO-PROP-B
CWEI (0)
LOCK
END
END
"""
class CompanionMacroTests(unittest.TestCase):
 def test_alp_and_compact_roundtrip_destinations_and_sjis(self):
  for text,col,kind in ((SOURCE,'catalog_details','SDTE'),(PROP,'catalog_props','CMPT')):
   with self.subTest(kind=kind):
    data=project.sample();cate=data['cates'][0]['id'];before=copy.deepcopy(data)
    candidate,targets=macros.import_text(data,text,cate);self.assertEqual(data,before)
    self.assertEqual(targets[0][0],col);record=project.get(candidate,col,targets[0][1])
    output=macros.creation_text(candidate,col,record['id'],'DEMO-OWNER')
    self.assertTrue(output.startswith('/DEMO-OWNER\nNEW '));self.assertNotIn('INPUT',output);self.assertNotIn('OLD ',output)
    other,ids=macros.import_text(data,output,cate);restored=project.get(other,col,ids[0][1])
    self.assertEqual(restored['name'],record['name']);self.assertEqual(restored['attrs'],record['attrs'])
    self.assertEqual(restored.get('macro_locked'),record.get('macro_locked'))
    self.assertEqual([(r['name'],r['attrs'],r.get('macro_locked')) for r in restored.get('children',[])],[(r['name'],r['attrs'],r.get('macro_locked')) for r in record.get('children',[])])
    with tempfile.TemporaryDirectory() as tmp:
     path=Path(tmp)/'sample.mac';macro_export.save(path,output)
     self.assertEqual(macro_import.read_text(path)[0].replace('\r\n','\n'),output)
    macro_destinations.save_options(candidate,kind,['OWNER1','/OWNER2'])
    project.validate(candidate);self.assertEqual(macro_destinations.options(candidate,kind),['/OWNER1','/OWNER2'])
 def test_unknown_attributes_and_other_roots_rejected_without_partial_import(self):
  data=project.sample();cate=data['cates'][0]['id'];before=copy.deepcopy(data)
  with self.assertRaises(ValueError):macros.import_text(data,'NEW CATE /OTHER\nEND',cate)
  self.assertEqual(data,before)
  candidate,ids=macros.import_text(data,PROP,cate);r=project.get(candidate,'catalog_props',ids[0][1]);r['children'][0]['attrs']['UNKNOWN']='retain me'
  with self.assertRaises(ValueError):macros.creation_text(candidate,'catalog_props',r['id'])
