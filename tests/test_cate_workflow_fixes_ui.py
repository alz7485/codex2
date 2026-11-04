import copy
import tkinter as tk
import unittest
from unittest.mock import patch
from catalog_studio import project,catalogue

class CateWorkflowTests(unittest.TestCase):
 def test_table_add_save_delete_and_plane_sync(self):
  from catalog_studio.integrated import IntegratedStudio
  from catalog_studio.scom_sheet_ui import open_sheet
  try:app=IntegratedStudio()
  except tk.TclError as exc:self.skipTest(str(exc))
  try:
   app.update();s=next(s for s in app.data['scoms'] if s['name']=='/SAMPLE-VALVE-80');app.cate_id=s['cate_id'];app.scom_id=s['id'];app.switch('catalog');app.update()
   from catalog_studio import presets
   for parameter in presets.rules(app.data,s):parameter['english_name']='Dimension '+parameter['id']
   win=open_sheet(app);app.update()
   with patch('catalog_studio.scom_sheet_ui.messagebox.askyesno',return_value=True):win.choose_preset()
   self.assertEqual(win.labels['P3'],'Dimension P3')
   original_label=win.labels['P3'];long_label='Very long STEXT description for the face to face dimension'
   win.labels['P3']=long_label;win.configure_headers();app.update()
   heading=win.tree.heading('P3','text');self.assertEqual(heading.split('\n')[0],'PA3');self.assertTrue(heading.endswith('…'))
   self.assertEqual(win.tree.column('P3','width'),108)
   self.assertTrue(win.rules.lines)
   self.assertGreater(win.winfo_width(),1100)
   win.header_hint.key='P3';win.header_hint.position=(20,20);win.header_hint.show();app.update()
   self.assertEqual(win.header_hint.window.winfo_children()[0].cget('text'),'PA3\n'+long_label)
   win.header_hint.hide();win.labels['P3']=original_label;win.configure_headers()
   self.assertEqual(win.columns,['NAME']+[p['id'] for p in presets.rules(app.data,s)])
   self.assertFalse(any(t.get('parameter_text_source',{}).get('preset_id')==s.get('parameter_preset_id') for t in app.data['texts']))
   import tempfile
   from pathlib import Path
   from openpyxl import Workbook
   with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'parts.xlsx';book=Workbook();ws=book.active;ws.append(['名前','Dimension P3']);ws.append(['/EXCEL-NEW',280]);book.save(path);book.close()
    with patch('catalog_studio.scom_sheet_ui.filedialog.askopenfilename',return_value=str(path)):win.load_excel()
   self.assertFalse(any(s['name']=='/EXCEL-NEW' for s in app.data['scoms']))
   self.assertTrue(any(r['NAME']=='/EXCEL-NEW' for r in win.rows))
   win.add_button.invoke();app.update();win.rows[-1]['NAME']='/TABLE-NEW'
   win.save_button.invoke();app.update();self.assertEqual(next(s for s in app.data['scoms'] if s['name']=='/EXCEL-NEW')['values']['P3'],280)
   created=next(s for s in app.data['scoms'] if s['name']=='/TABLE-NEW')
   b=app.registered_browser;b.tree.selection_set('scoms:'+created['id']);b.select();app.update()
   with patch('catalog_studio.integrated.messagebox.askyesno',return_value=True):b.delete_item()
   app.update();self.assertIsNone(project.get(app.data,'scoms',created['id']))
   text=catalogue.add_record(app.data,'texts','TEXT','/DELETE-TEXT',app.cate_id);app.render_page();app.update();b.tree.selection_set('texts:'+text['id']);b.select();app.update()
   with patch('catalog_studio.catalog_members_ui.messagebox.askyesno',return_value=True):b.delete_item()
   self.assertIsNone(project.get(app.data,'texts',text['id']))
   empty=project.add_cate(app.data,'/EMPTY-CATE');app.cate_id=empty['id'];app.scom_id=None;app.render_page();app.update()
   b.tree.selection_set('cates:'+empty['id']);b.select();app.update()
   with patch('catalog_studio.integrated.messagebox.askyesno',return_value=True):b.delete_item()
   self.assertIsNone(project.get(app.data,'cates',empty['id']))
   app.definition_id='ui-ptset';app.switch('ptset');app.update();view=app.geometry_editor.point_canvas
   for name in ('XZ','YZ','XY'):
    view.view.set(name);view.view_changed();self.assertEqual(view.plane.get(),name)
   view.view.set('XZ');view.view_changed();self.assertEqual(view.plane.get(),'XZ')
   view.view.set('立体');view.view_changed();self.assertEqual(view.plane.get(),'XY')
  finally:app.destroy()
