import copy
import tempfile
import unittest
from pathlib import Path
from catalog_studio import project,scom_sheet as sheet
from catalog_studio.valve_sample import prepare

class ScomSheetTests(unittest.TestCase):
 def setUp(self):
  self.data,_=prepare(project.sample());self.seed=next(s for s in self.data['scoms'] if s['name']=='/SAMPLE-VALVE-80');self.cate=self.seed['cate_id']
 def test_transactional_update_and_add_with_stable_id_and_references(self):
  before=copy.deepcopy(self.data);one=sheet.row(self.data,self.seed);one['P3']='300'
  two=dict(one);two.pop('id');two['NAME']='/NEW-PART';two['P3']='450'
  candidate,ids=sheet.apply(self.data,self.cate,[one,two],self.seed['id'])
  self.assertEqual(self.data,before);self.assertEqual(ids[0],self.seed['id'])
  self.assertEqual(project.get(candidate,'scoms',ids[0])['values']['P3'],300)
  self.assertEqual(project.get(candidate,'scoms',ids[1])['values']['P3'],450)
  self.assertEqual(project.get(candidate,'scoms',ids[1])['ptset_id'],self.seed['ptset_id'])
  two['P3']='invalid'
  with self.assertRaises(ValueError):sheet.apply(self.data,self.cate,[one,two],self.seed['id'])
  self.assertEqual(self.data,before)
 def test_stext_columns_and_text_creation_are_staged_without_overwrite(self):
  from catalog_studio import presets
  profile=presets.selected_id(self.data,self.seed)
  for p in presets.rules(self.data,self.seed):p['english_name']='Dimension '+p['id']
  before=copy.deepcopy(self.data)
  working,labels=sheet.text_columns(self.data,self.cate,profile,True)
  self.assertEqual(self.data,before);self.assertEqual(labels['NAME'],'名前');self.assertEqual(labels['P3'],'Dimension P3')
  count=len(working['texts']);again,labels2=sheet.text_columns(working,self.cate,profile,True)
  self.assertEqual(len(again['texts']),count);self.assertEqual(labels,labels2)
  existing=next(t for t in again['texts'] if t.get('parameter_text_source',{}).get('parameters')=='P3')
  existing['attrs']['STEXT']='Face to face'
  _,labels3=sheet.text_columns(again,self.cate,profile,False);self.assertEqual(labels3['P3'],'Face to face')

 def test_excel_values_headers_and_formula_rejection(self):
  from openpyxl import Workbook
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'parts.xlsx';w=Workbook();s=w.active;s.append(['SCOM名','PA3']);s.append(['/EXCEL-PART',250]);w.save(path);w.close()
   rows,names=sheet.read_excel(path);self.assertEqual(rows,[{'NAME':'/EXCEL-PART','P3':250}])
   w=Workbook();w.active.append(['Cover']);parts=w.create_sheet('Parts');parts.append(['NAME','P3']);parts.append(['/SHEET-PART',270]);w.save(path);w.close()
   self.assertEqual(sheet.sheet_names(path),['Sheet','Parts'])
   self.assertEqual(sheet.read_excel(path,'Parts')[0],[{'NAME':'/SHEET-PART','P3':270}])
   w=Workbook();s=w.active;s.append(['NAME','P3']);s.append(['/FORMULA','=1+1']);w.save(path);w.close()
   with self.assertRaises(ValueError):sheet.read_excel(path)
