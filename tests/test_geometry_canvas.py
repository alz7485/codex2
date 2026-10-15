import copy
import math
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from catalog_studio import geometry_scene as geo, element_schema as schema, project
from catalog_studio.integrated import IntegratedStudio
from test_geometry_scene import fixture


class GeometryCanvasTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest('GUI display unavailable: '+str(exc))
        self.errors=[];self.app.report_callback_exception=lambda kind,value,trace:self.errors.append(str(value))
        self.data,self.pt,self.gm,self.scom,self.node=fixture()
        self.app.data=self.data;self.app.definition_id=self.gm['id'];self.app.scom_id=self.scom['id']
        self.app.geometry('1440x960');self.app.switch('gmset');self.app.update()
        self.e=self.app.geometry_editor;self.view=self.e.geometry_view;self.canvas=self.view.canvas
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def actual(self):
        self.view.scom_choice.set(self.scom['name']);self.view.scom_choice.event_generate('<<ComboboxSelected>>');self.app.update()
    def drag(self,release=True):
        axis=next(i for i,h in self.view.handles.items() if math.hypot(h['screen'][0]-h['start'][0],h['screen'][1]-h['start'][1])>8)
        handle=self.view.handles[axis];x,y=handle['screen'];cx,cy=handle['start']
        self.canvas.event_generate('<Button-1>',x=round(x),y=round(y));self.app.update()
        self.canvas.event_generate('<B1-Motion>',x=round(x+(x-cx)*.45),y=round(y+(y-cy)*.45));self.app.update()
        if release:self.canvas.event_generate('<ButtonRelease-1>',x=round(x+(x-cx)*.45),y=round(y+(y-cy)*.45));self.app.update()

    def test_combined_preview_switches_to_scom_dimensions_and_preserves_data(self):
        before=copy.deepcopy(self.data)
        self.assertFalse(self.view.actual);self.assertTrue(self.view.handles)
        self.actual();self.assertTrue(self.view.actual);self.assertEqual(self.view.scene.issues,[])
        self.assertEqual(self.view.scene.points[2][0],(50,0,0))
        self.assertEqual(self.view.handles,{})
        self.assertTrue(self.canvas.find_withtag('mesh'));self.assertTrue(self.canvas.find_withtag('point:2'))
        self.assertIn('X 100',self.view.note['text']);self.assertEqual(self.data,before)
        self.assertEqual(self.errors,[])

    def test_drag_changes_only_draft_scale_on_release_and_is_saved_with_group(self):
        attrs=copy.deepcopy(self.node['attrs']);values=copy.deepcopy(self.scom['values']);self.app.dirty=False
        self.drag(release=False)
        self.assertIsNotNone(self.view.drag);self.assertNotIn(geo.SCALE_KEY,self.node)
        self.assertFalse(self.app.dirty)
        self.view.release();self.app.update()
        self.assertNotEqual(self.node[geo.SCALE_KEY],[1,1,1]);self.assertTrue(self.app.dirty)
        self.assertEqual(self.node['attrs'],attrs);self.assertEqual(self.scom['values'],values)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'project.json';project.save(self.data,path)
            restored=project.load(path);self.assertEqual(restored['definitions'][1]['elements'][0][geo.SCALE_KEY],self.node[geo.SCALE_KEY])
        self.assertEqual(self.errors,[])

    def test_escape_and_mode_change_discard_uncommitted_resize(self):
        before=copy.deepcopy(self.data);self.drag(release=False)
        self.canvas.focus_force();self.canvas.event_generate('<Escape>');self.app.update()
        self.assertIsNone(self.view.drag);self.assertEqual(self.data,before)
        self.drag(release=False);self.view.mode_buttons['SCOM 実寸'].invoke();self.app.update()
        self.assertIsNone(self.view.drag);self.assertEqual(self.data,before)
        self.assertEqual(self.errors,[])

    def test_actual_dimensions_follow_attribute_edits_without_dragging_scom_values(self):
        self.actual();before=copy.deepcopy(self.scom)
        self.e.tables['main'].begin_edit('PHEI');self.app.update();dialog=self.e.tables['main'].editing['dialog']
        dialog.variable.set('PARAM 3 / 2');dialog.confirm_button.invoke();self.app.update()
        mesh=self.view.scene.meshes[0]
        self.assertEqual(max(p[0] for p in mesh.vertices)-min(p[0] for p in mesh.vertices),50)
        self.assertEqual(self.scom,before)
        self.canvas.event_generate('<Button-1>',x=100,y=100);self.canvas.event_generate('<B1-Motion>',x=140,y=140);self.canvas.event_generate('<ButtonRelease-1>',x=140,y=140);self.app.update()
        self.assertNotIn(geo.SCALE_KEY,self.node);self.assertEqual(self.errors,[])

    def test_fit_contains_geometry_and_points_after_rotation_resize_and_size_changes(self):
        self.actual()
        for magnitude,size in ((1e-9,'1120x780'),(1e9,'1440x960')):
            self.scom['values'].update(P1=40*magnitude,P3=100*magnitude)
            self.app.geometry(size);self.app.update();self.view.redraw();self.app.update()
            for widget in self.view.mode_buttons.values():
                self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(),self.app.winfo_rootx()+self.app.winfo_width())
            for _ in range(2):
                w,h=self.canvas.winfo_width(),self.canvas.winfo_height()
                for point in self.view.scene.vertices():
                    x,y=self.view.camera.project(point,w,h);self.assertTrue(40<=x<=w-40 and 40<=y<=h-40)
                self.canvas.event_generate('<Button-3>',x=100,y=100);self.canvas.event_generate('<B3-Motion>',x=145,y=130);self.canvas.event_generate('<ButtonRelease-3>',x=145,y=130);self.app.update()
        self.assertEqual(self.errors,[])

    def test_picking_shapes_and_display_toggles_select_attributes_without_mutation(self):
        other=schema.add_element(self.gm,'SBOX');other['attrs'].update(PX='0',PY='0',PZ='0',PXLE='20',PYLE='20',PZLE='20')
        negative=schema.add_element(self.gm,'NSCY');negative['attrs'].update(PAXI='P2',PDIS='0',PHEI='PARAM 3',PDIA='PARAM 1 / 2')
        self.e.refresh();self.app.update();self.actual()
        mesh=next(m for m in self.view.scene.meshes if m.ident==other['id']);center=tuple(sum(p[i] for p in mesh.vertices)/len(mesh.vertices) for i in range(3));x,y=self.view.camera.project(center,self.canvas.winfo_width(),self.canvas.winfo_height())
        self.canvas.event_generate('<Button-1>',x=round(x),y=round(y));self.canvas.event_generate('<ButtonRelease-1>',x=round(x),y=round(y));self.app.update()
        self.assertEqual(self.e.element_id,other['id']);self.assertIn('PXLE',self.e.tables['main'].get_children())
        before=copy.deepcopy(self.data);self.assertTrue(self.canvas.find_withtag('negative'))
        self.view.show_negative.set(False);self.view.show_points.set(False);self.view.redraw()
        self.assertFalse(self.canvas.find_withtag('negative'));self.assertFalse(self.canvas.find_withtag('point'))
        self.assertEqual(self.data,before);self.assertEqual(self.errors,[])

    def test_scom_choice_filters_other_geometry_and_mismatch_has_no_fallback(self):
        unrelated=copy.deepcopy(self.scom);unrelated.update(id='unrelated',name='/OTHER',gmset_id='other')
        self.data['scoms'].append(unrelated);self.view.redraw();self.assertNotIn('/OTHER',self.view.scom_choice['values'])
        self.scom['values'].pop('P1');self.actual()
        self.assertEqual(self.view.scene.meshes,[]);self.assertIn('未設定',self.view.issue_label['text'])
        self.assertFalse(self.canvas.find_withtag('mesh'));self.assertEqual(self.errors,[])

    def test_pairing_changes_refresh_point_overlay_and_reports_incompatible_scom(self):
        other=copy.deepcopy(self.pt);other.update(id='other-pt',name='/OTHER-PTSET')
        other['elements'][0]['schematic_position']=[-1.7,0,0];self.data['definitions'].append(other)
        self.e.refresh();self.e.ptset_choice.set(other['name']);self.e.assign_ptset();self.app.update()
        self.assertEqual(self.view.scene.points[1][0],(-1.7,0,0))
        self.actual();self.assertEqual(self.view.scene.meshes,[])
        self.assertIn('PTSET',self.view.issue_label['text']);self.assertEqual(self.errors,[])
