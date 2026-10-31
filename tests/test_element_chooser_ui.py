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
      for i in range(e.library.size()):
       e.library.selection_clear(0,'end');e.library.selection_set(i);e.describe_selected_type();app.update()
       self.assertTrue(e.guide_canvas.find_all())
     self.assertEqual(app.data,before)
     e.negative.set(False);e.populate_library();e.library.selection_clear(0,'end');e.library.selection_set(0)
     e.describe_selected_type();old=len(e.definition()['elements']);e.add_element();app.update()
     self.assertEqual(len(e.definition()['elements']),old+1)
     self.assertTrue(e.recall_preset_button.winfo_exists());self.assertTrue(e.register_preset_button.winfo_exists())
     with patch('catalog_studio.element_presets_ui.register_current') as register:
      e.register_preset_button.invoke();register.assert_called_once_with(e)
   self.assertEqual(errors,[])
  finally:app.destroy()
