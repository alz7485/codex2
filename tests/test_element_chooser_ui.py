import copy
import tkinter as tk
import unittest
from unittest.mock import patch
from catalog_studio import element_schema as schema

class ElementChooserUiTests(unittest.TestCase):
 def test_explanatory_diagrams_buttons_and_creation_for_both_sets(self):
  from catalog_studio.integrated import IntegratedStudio
  try:app=IntegratedStudio()
  except tk.TclError as exc:self.skipTest(str(exc))
  errors=[];app.report_callback_exception=lambda k,v,t:errors.append(str(v))
  try:
   for page in ('ptset','gmset'):
    with self.subTest(page=page):
     app.definition_id='ui-ptset' if page=='ptset' else 'ui-gmset';app.switch(page);app.update();e=app.geometry_editor
     self.assertEqual(e.add_button.cget('style'),'AttributeTool.TButton')
     before=copy.deepcopy(app.data)
     e.toggle_create();app.update()
     for negative in ((False,True) if page=='gmset' else (False,)):
      e.negative.set(negative);e.populate_library();app.update()
      if page=='gmset':
       self.assertEqual(e.shape_tabs.index(e.shape_tabs.select()),int(negative))
       self.assertEqual(e.library.yview(),(0.0,1.0))
       self.assertIsNotNone(e.library.bbox(e.library.size()-1))
       sizes=[(b.winfo_width(),b.winfo_height()) for b in e.shape_tab_buttons]
       self.assertEqual(sizes[0],sizes[1])
       if not negative:tab_sizes=sizes
       else:self.assertEqual(sizes,tab_sizes)
      for i in range(e.library.size()):
       e.library.selection_clear(0,'end');e.library.selection_set(i);e.describe_selected_type();app.update()
       self.assertTrue(e.guide_canvas.find_all())
       labels=[e.guide_canvas.itemcget(item,'text') for item in e.guide_canvas.find_all() if e.guide_canvas.type(item)=='text']
       if page=='ptset':
        self.assertIn('立体図',labels);self.assertIn('平面図（XY）',labels);self.assertEqual(labels.count('P1'),2)
       elif e.library.get(i).split()[0] in ('LSNO','NLSN'):
        self.assertIn('P1（下端）',labels);self.assertIn('P2（上端）',labels)
     self.assertEqual(app.data,before)
     e.negative.set(False);e.populate_library();e.library.selection_clear(0,'end');e.library.selection_set(0)
     e.describe_selected_type();old=len(e.definition()['elements']);e.add_element();app.update()
     self.assertEqual(len(e.definition()['elements']),old+1)
     self.assertTrue(e.recall_preset_button.winfo_exists());self.assertTrue(e.register_preset_button.winfo_exists())
     with patch('catalog_studio.element_presets_ui.register_current') as register:
      e.register_preset_button.invoke();register.assert_called_once_with(e)
   self.assertEqual(errors,[])
  finally:app.destroy()
