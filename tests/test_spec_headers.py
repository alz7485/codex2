import copy
import json
import tkinter as tk
import unittest
from catalog_studio import spec_headers as schema,project,spec_table_ui

class HeaderTests(unittest.TestCase):
 def test_exact_profiles_and_text_everywhere(self):
  expected={
   'TUBE':'PBOR0 TEXT SHOP','BEND':'PBOR0 STYP RADI TEXT SHOP',
   'WELD':'PBOR0 STYP EDGE ALLO TEXT SHOP','ELBO':'PBOR0 STYP TEXT SHOP',
   'TEE':'PBOR0 PBOR3 STYP HEIG TEXT SHOP','REDU':'PBOR1 PBOR2 STYP TEXT SHOP',
   'OLET':'PBOR0 PBOR3 STYP HEIG ANGL TEXT SHOP','CAP':'PBOR0 STYP TEXT SHOP',
   'FLAN':'PBOR0 STYP TEXT SHOP','BOLT':'PBOR1 PBOR2 STYP TEXT SHOP',
   'GASK':'PBOR0 STYP TEXT SHOP','PCOM':'PBOR0 STYP HEIG TEXT SHOP',
   'INST':'PBOR0 STYP HEIG ANGL TEXT SHOP','VALV':'PBOR1 PBOR2 STYP HEIG TEXT SHOP'}
  self.assertEqual(set(expected),set(schema.SELECTORS))
  for kind,fields in expected.items():
   self.assertEqual(schema.headings(kind),('TYPE','NAME',*fields.split(),*schema.REFERENCES))
   self.assertEqual(schema.headings(kind).count('TEXT'),1)
   self.assertLessEqual(len(schema.headings(kind)),20)

 def test_switch_keeps_inapplicable_values_and_saves_new_fields(self):
  from catalog_studio.integrated import IntegratedStudio
  try:app=IntegratedStudio()
  except tk.TclError as exc:self.skipTest(str(exc))
  try:
   app.switch('specs');app.update()
   entry=app.spec()['entries'][0]
   entry.update(type='TEE',bore0='50mm',bore3='25mm',height='40mm',text='説明',radius='99mm')
   before=copy.deepcopy(app.data)
   for kind in ('TEE','TUBE','OLET','BOLT','REDU'):
    app.spec_type_filter.set(kind);spec_table_ui.populate(app);app.update()
    self.assertEqual(tuple(app.spec_table['displaycolumns']),schema.columns(kind))
    self.assertIn('text',app.spec_table['displaycolumns'])
   self.assertEqual(app.data,before)
   project.validate(json.loads(json.dumps(app.data)))
  finally:app.destroy()
