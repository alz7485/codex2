import copy
import math
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from catalog_studio import element_schema as s,expressions as ex,macro_export,macro_import,project

class PhotoRules(unittest.TestCase):
 def test_expressions_defaults_and_explicit_clear(self):
  for source in ('PARAM 3 / 2','DIFFERENCE PARAM 3 PARAM 1','0.5 TIMES PARAM 1','DIV - PARAM 26 2'):
   target=ex.e3d(source)
   self.assertEqual(ex.parse(source),ex.parse(target))
   self.assertIn('ATTRIB PARA[',target)
  self.assertEqual(ex.e3d('PARAM[3]'),'PARAM 3')
  self.assertEqual(ex.e3d('IPARA 1'),'(ATTRIB IPARA[1])')
  self.assertEqual(ex.e3d_embedded('X(PARAM[3] / 2)Y'),'X(ATTRIB PARA[3] / 2)Y')
  d={'kind':'GMSET','name':'/DEMO','elements':[]}
  n=s.add_element(d,'SCYL');n['attrs'].update(PHEI='PARAM 1 / 2',PDIA='PARAM 2',PAXI='')
  before=copy.deepcopy(d);text=macro_export.creation_text([d]);parsed=macro_import.parse(text).definitions[0]
  self.assertNotIn('LEVEL',text);self.assertNotIn('NAPP',text);self.assertIn("PAXI ''",text)
  self.assertEqual(parsed['elements'][0]['attrs']['PAXI'],'')
  self.assertEqual(d,before)
 def test_lpy_axis_and_insulation_ratio(self):
  from catalog_studio.editor_rules import derived_axes
  n={'type':'LPYR','attrs':s.default_attrs('LPYR')};self.assertEqual(n['attrs']['PAAX'],'Z')
  n['attrs'].update(PBAX='Y',PCAX='Z');derived_axes(n);self.assertEqual(n['attrs']['PAAX'],'X')
  from catalog_studio.point_preview import preview_parse
  self.assertEqual(ex.evaluate(ex.normalized('IPARA 1'),{'IPARAM':{'P1':2}}),2)
  root=preview_parse('IPARA 2');self.assertEqual(root,ex.parse('0.5 * IPARA 1'))

class PhotoUi(unittest.TestCase):
 def test_direction_drag_rotates_in_each_plane_without_changing_position_values(self):
  from catalog_studio.integrated import IntegratedStudio
  from catalog_studio.point_geometry import PLANES,DIMENSIONS_KEY
  from catalog_studio.point_preview import PointPreview
  try:app=IntegratedStudio()
  except tk.TclError as exc:self.skipTest(str(exc))
  try:
   app.update();e=app.geometry_editor;v=e.point_canvas
   for plane,(a,b) in PLANES.items():
    for kind,key in [('PTAXI','PAXI'),('PTMIX','PAXI'),('PTCAR','PTCDIR'),('PTPOS','PTCDIR')]:
     n=s.add_element(e.definition(),kind)
     n['attrs'].update({key:'XYZ'[a]})
     if kind=='PTAXI':n['attrs']['PDIS']='PARAM 3'
     elif kind=='PTPOS':n['attrs']['PTCPOS']='X 0 Y 0 Z 0'
     else:n['attrs'].update(PX='PARAM 3',PY='0',PZ='0')
     e.element_id=n['id'];e.refresh();app.update();v.plane.set(plane);v.plane_changed();v.camera.face(plane);v.redraw()
     before=copy.deepcopy(n['attrs']);dims=copy.deepcopy(e.definition().get(DIMENSIONS_KEY));sc=copy.deepcopy(app.data['scoms'])
     original_model=PointPreview(e.data,e.definition());pivot=original_model.location(n['id']);original_values=copy.deepcopy(original_model.values);target=list(pivot)
     target[a]+=math.cos(math.radians(33));target[b]+=math.sin(math.radians(33))
     v.press_position=v.camera.project(pivot,v.canvas.winfo_width(),v.canvas.winfo_height())
     x,y=v.camera.project(target,v.canvas.winfo_width(),v.canvas.winfo_height())
     v.propose_rotation(x,y,n['id']);self.assertIsNotNone(v.pending,v.error_message)
     self.assertEqual(n['attrs'],before);v.apply();app.update()
     vector=PointPreview(e.data,e.definition()).axis(n['attrs'][key])[1]
     self.assertAlmostEqual(vector[a],math.cos(math.radians(35)),places=7)
     self.assertAlmostEqual(vector[b],math.sin(math.radians(35)),places=7)
     self.assertEqual({k:x for k,x in n['attrs'].items() if k!=key},{k:x for k,x in before.items() if k!=key})
     self.assertEqual(e.definition().get(DIMENSIONS_KEY),dims);self.assertEqual(app.data['scoms'],sc)
     if kind=='PTAXI':
      actual=PointPreview(e.data,e.definition())
      for ref,value in original_values.items():self.assertAlmostEqual(actual.values[ref],value)
  finally:app.destroy()

 def test_parameter_position_input_uses_virtual_distance_without_real_values(self):
  from catalog_studio.integrated import IntegratedStudio
  from catalog_studio.point_geometry import LAYOUT_KEY
  try:app=IntegratedStudio()
  except tk.TclError as exc:self.skipTest(str(exc))
  try:
   app.update();e=app.geometry_editor
   for kind,key in [('PTAXI','PDIS'),('PTCAR','PX')]:
    n=s.add_element(e.definition(),kind);n[LAYOUT_KEY]=[0.,0.,0.]
    n['attrs'].update(PAXI='X')
    if kind=='PTCAR':n['attrs'].update(PX='0',PY='0',PZ='0')
    e.element_id=n['id'];e.refresh();app.update();before=copy.deepcopy(app.data['scoms'])
    self.assertAlmostEqual(e.point_canvas.positions[n['id']][0],0.)
    context=e.inline_context(key,'main');context['commit']('PARAM 29');e.refresh();app.update()
    self.assertGreater(abs(e.point_canvas.positions[n['id']][0]),.1)
    self.assertEqual(n['attrs'][key],'PARAM 29');self.assertEqual(app.data['scoms'],before)
  finally:app.destroy()

 def test_optional_attributes_hidden_in_both_editors_without_data_loss(self):
  from catalog_studio.integrated import IntegratedStudio
  try:app=IntegratedStudio()
  except tk.TclError as exc:self.skipTest(str(exc))
  try:
   for page,kind,hidden in [('ptset','PTAXI',('DESC','PURP')),('gmset','SCYL',('DESC','GTYP','PURP'))]:
    app.switch(page);app.update();e=app.geometry_editor
    node=s.add_element(e.definition(),kind);node['attrs'].update({k:'saved-'+k for k in hidden})
    before=copy.deepcopy(node);e.element_id=node['id'];e.refresh();app.update()
    self.assertTrue(e.optional_attrs_button.winfo_ismapped())
    for k in hidden:self.assertNotIn(k,e.tables['main'].get_children())
    e.optional_attrs_button.invoke();app.update()
    for k in hidden:self.assertIn(k,e.tables['main'].get_children())
    e.optional_attrs_button.invoke();e.refresh();app.update()
    for k in hidden:self.assertNotIn(k,e.tables['main'].get_children())
    self.assertEqual(node['attrs'],before['attrs'])
  finally:app.destroy()

 def test_sphere_uniform_resize_and_point_position_picker(self):
  from catalog_studio.integrated import IntegratedStudio
  from catalog_studio.geometry_scene import SCALE_KEY
  try:app=IntegratedStudio()
  except tk.TclError as exc:self.skipTest(str(exc))
  try:
   app.switch('gmset');app.update();e=app.geometry_editor
   node=s.add_element(e.definition(),'SSPH');e.element_id=node['id'];e.refresh();app.update();v=e.geometry_view
   h=v.handles[0];x,y=h['screen'];a,b=h['start']
   v.press(SimpleNamespace(x=x,y=y));v.move(SimpleNamespace(x=x+(x-a)*.4,y=y+(y-b)*.4));v.release();app.update()
   self.assertIn(SCALE_KEY,node)
   self.assertAlmostEqual(node[SCALE_KEY][0],node[SCALE_KEY][1]);self.assertAlmostEqual(node[SCALE_KEY][1],node[SCALE_KEY][2])
   node=s.add_element(e.definition(),'LPYR');e.element_id=node['id'];e.refresh();app.update()
   self.assertIsNone(e.inline_context('PAAX','main'))
   app.switch('ptset');app.update();e=app.geometry_editor
   p=s.add_element(e.definition(),'PTPOS');e.element_id=p['id'];e.refresh();app.update()
   table=e.tables['main'];table.begin_edit('PTCPOS');app.update();dialog=table.editing['dialog']
   self.assertIn('P1',dialog.points)
   dialog.point_picker.set('P1');dialog.insert_point();self.assertEqual(dialog.variable.get(),'PP 1')
   dialog.confirm_button.invoke();app.update();self.assertEqual(p['attrs']['PTCPOS'],'PP 1')
  finally:app.destroy()

 def test_drag_multiselect_defaults_toggles_and_navigation(self):
  from catalog_studio.integrated import IntegratedStudio
  from catalog_studio import preview_preferences
  with patch.object(preview_preferences,'load',return_value=(copy.deepcopy(preview_preferences.FACTORY),'')):
   try:app=IntegratedStudio()
   except tk.TclError as exc:self.skipTest(str(exc))
   try:
    errors=[];app.report_callback_exception=lambda k,v,t:errors.append(str(v));app.update()
    e=app.geometry_editor;d=e.definition();n=s.add_element(d,'PTAXI');e.element_id=n['id'];e.refresh();app.update()
    self.assertEqual(n['attrs']['PAXI'],'');self.assertEqual(n['attrs']['PDIS'],'')
    self.assertNotIn('DESC',e.tables['main'].get_children());self.assertFalse(e.element_preset_choice.winfo_ismapped())
    e.optional_attrs_button.invoke();app.update();self.assertIn('DESC',e.tables['main'].get_children())
    v=e.point_canvas;v.propose(v.canvas.winfo_width()*.7,v.canvas.winfo_height()*.4,n['id']);self.assertIsNotNone(v.pending)
    v.apply();app.update();self.assertTrue(n['attrs']['PAXI']);self.assertEqual(n['attrs']['PDIS'],'')
    ids=e.elements.get_children()[:2];e.elements.selection_set(ids);app.update()
    self.assertEqual(len(e.elements.selection()),2);self.assertIsNone(e.element())
    snapshot=copy.deepcopy(app.data)
    v.press(SimpleNamespace(x=10,y=10));v.move(SimpleNamespace(x=100,y=100));v.release(SimpleNamespace(x=100,y=100))
    self.assertEqual(app.data,snapshot)
    with patch('catalog_studio.construction_ui.messagebox.askyesno',return_value=True):e.delete_element()
    self.assertFalse(any(n['id'] in ids for n in d['elements']))
    app.switch('gmset');app.update();e=app.geometry_editor;v=e.geometry_view
    self.assertEqual(v.render_mode.get(),'ワイヤー')
    before=copy.deepcopy(app.data);a=(v.camera.yaw,v.camera.pitch)
    v.canvas.event_generate('<Button-2>',x=50,y=50);v.canvas.event_generate('<B2-Motion>',x=90,y=70);v.canvas.event_generate('<ButtonRelease-2>',x=90,y=70);app.update()
    self.assertNotEqual(a,(v.camera.yaw,v.camera.pitch));self.assertEqual(app.data,before)
    e.tables['main'].begin_edit('CLFLA');app.update();self.assertEqual(e.element()['attrs']['CLFLA'],'TRUE')
    self.assertIsNone(e.tables['main'].editing)
    self.assertFalse(errors,errors)
   finally:app.destroy()
