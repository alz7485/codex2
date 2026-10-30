import copy
import tkinter as tk
import unittest
from catalog_studio import project
from catalog_studio.catalog_inspector import edit_value

class SdteCmptUiTests(unittest.TestCase):
 def test_navigation_creation_editing_and_preserved_associations(self):
  from catalog_studio.integrated import IntegratedStudio
  try:app=IntegratedStudio()
  except tk.TclError as exc:self.skipTest(str(exc))
  try:
   errors=[];app.report_callback_exception=lambda k,v,t:errors.append(str(v))
   keys=list(app.nav);self.assertEqual(keys[keys.index('catalog')+1],'sdte_cmpt')
   self.assertEqual(app.nav['catalog'].cget('text'),'CATE作成')
   specs=copy.deepcopy(app.data['specs'])
   app.switch('sdte_cmpt');app.update();editor=app.sdte_cmpt_editor
   self.assertFalse(app.registered_browser.winfo_manager())
   editor.add('SDTE');app.update();key=editor.tree.selection()[0]
   col,r,_=editor.rows[key];self.assertEqual(col,'catalog_details')
   edit_value(app.data,col,key,('attrs','RTEX'),'Sample detail')
   editor.add('CMPT');app.update();prop_id=editor.tree.selection()[0]
   editor.add('CMPDATA');app.update();child_id=editor.tree.selection()[0]
   col,prop,index=editor.rows[child_id];self.assertEqual(prop['id'],prop_id)
   edit_value(app.data,col,prop_id,('children',index,'attrs','CWEI'),'9.1')
   self.assertEqual(prop['children'][index]['attrs']['CWEI'],9.1)
   editor.select();app.update()
   iid=next(i for i,f in editor.fields.items() if f[2][-1]=='CWEI')
   x,y,w,h=editor.attrs.bbox(iid,'value')
   from types import SimpleNamespace
   editor.click(SimpleNamespace(x=x+w//2,y=y+h//2));editor.editing[1].set('invalid')
   app.switch('catalog');self.assertEqual(app.page,'sdte_cmpt')
   editor.editing[1].set('12.5');self.assertTrue(editor.finish())
   self.assertEqual(prop['children'][index]['attrs']['CWEI'],12.5)
   project.validate(app.data);self.assertEqual(app.data['specs'],specs)
   app.switch('catalog');app.update();self.assertTrue(app.registered_browser.winfo_manager())
   app.switch('sdte_cmpt');app.update();self.assertIn(child_id,app.sdte_cmpt_editor.rows)
   self.assertEqual(errors,[])
  finally:app.destroy()
