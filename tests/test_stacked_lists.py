import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from catalog_studio import element_schema as schema,project,presets
from catalog_studio.integrated import IntegratedStudio
from catalog_studio.point_preview import remember


class StackedListTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest('GUI display unavailable: '+str(exc))
        self.errors=[];self.app.report_callback_exception=lambda kind,value,tb:self.errors.append(str(value));self.app.update();self.editor=self.app.geometry_editor

    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
        self.assertEqual(self.errors,[])

    def test_stacked_name_and_type_and_edit_confirm_cancel_save(self):
        e=self.editor;point=e.element();before=copy.deepcopy(point);view=e.elements
        name=view.find_withtag('name:'+point['id'])[0];kind=view.find_withtag('type:'+point['id'])[0]
        self.assertLess(view.coords(name)[1],view.coords(kind)[1]);self.assertLess(view.type_font.cget('size'),view.name_font.cget('size'))
        self.assertTrue(view.begin_edit(point['id']));self.app.update();self.assertTrue(view.editing['entry'].winfo_ismapped())
        view.editing['variable'].set('取消した名前');view.cancel_edit();self.app.update();self.assertEqual(point,before)
        view.begin_edit(point['id']);view.editing['variable'].set('入口接続点')
        with tempfile.TemporaryDirectory() as folder:
            self.app.path=str(Path(folder)/'names.json');self.assertTrue(self.app.save_project())
            loaded=project.get(project.load(self.app.path),'definitions',e.definition_id)
            self.assertEqual(loaded['elements'][0]['name'],'入口接続点')
        self.app.update();self.assertEqual(view.item(point['id'],'text'),'入口接続点');self.assertEqual(point['type'],before['type']);self.assertEqual(point['attrs'],before['attrs'])

    def test_pending_attribute_and_name_edits_commit_to_their_own_element(self):
        e=self.editor;remember(self.app.data,e.definition())
        first=e.element();second=e.definition()['elements'][1];unchanged=copy.deepcopy(second)
        table=e.tables['main'];table.begin_edit('PDIS');table.editing['variable'].set('PARAM 3 / 4')
        e.elements.begin_edit(first['id']);self.assertEqual(first['attrs']['PDIS'],'PARAM 3 / 4')
        e.elements.editing['variable'].set('編集した入口');e.elements.selection_set(second['id']);self.app.update()
        self.assertEqual(first['name'],'編集した入口');self.assertEqual(second,unchanged);self.assertEqual(e.element_id,second['id'])

    def test_empty_duplicate_and_stale_names_do_not_overwrite_records(self):
        e=self.editor;point=e.element();other=e.definition()['elements'][1];view=e.elements;original=point['name']
        for value in ('',other['name']):
            view.begin_edit(point['id']);view.editing['variable'].set(value);self.assertFalse(view.finish_edit());self.assertEqual(point['name'],original);view.cancel_edit()
        view.begin_edit(point['id']);view.editing['variable'].set('入力中');point['name']='別の変更'
        self.assertFalse(view.finish_edit());self.assertEqual(point['name'],'別の変更');view.cancel_edit()

    def test_all_point_attributes_aliases_and_raw_extra_share_one_list(self):
        e=self.editor;point=schema.add_element(e.definition(),'PTPOS');point['attrs'].pop('PTCDIR',None)
        point['attrs'].update(PTCD='X45U',EXTRA='PARAM 3 を含む保持データ');e.element_id=point['id'];e.refresh();self.app.update()
        table=e.tables['main'];self.assertEqual(set(e.tables),{'main'});self.assertNotIsInstance(e.tabs,ttk.Notebook)
        self.assertEqual(table.get_children(),schema.fields('PTPOS')+schema.PT_DETAIL+('EXTRA',))
        self.assertFalse(table.begin_edit('EXTRA'));self.assertFalse(table.canvas.find_withtag('caption:EXTRA'))
        table.begin_edit('PTCDIR');table.editing['variable'].set('Y');table.finish_edit();self.assertEqual(point['attrs']['PTCD'],'Y');self.assertNotIn('PTCDIR',point['attrs'])
        table.begin_edit('DESC');table.editing['variable'].set('PARAM 3 の説明');table.finish_edit();self.app.update()
        self.assertEqual(point['attrs']['DESC'],'PARAM 3 の説明');self.assertFalse(table.canvas.find_withtag('caption:DESC'))
        self.assertEqual(point['attrs']['EXTRA'],'PARAM 3 を含む保持データ');self.assertEqual(point['attrs']['PSKEY'],'unset')

    def test_right_preset_updates_labels_and_negative_attributes_stay_editable(self):
        app=self.app;app.switch('gmset');app.update();e=app.geometry_editor
        negative=schema.add_element(e.definition(),'NSCY');negative['attrs'].update(PHEI='PARAM 3',OBST='0',NAPP='1');e.element_id=negative['id'];e.refresh();app.update()
        table=e.tables['main'];self.assertEqual(table.get_children(),schema.fields('NSCY')+schema.GM_COMMON+schema.NEGATIVE_EXTRA)
        self.assertIs(e.preset_choice.master,e.attribute_pane);self.assertLess(e.preset_choice.winfo_rooty()+e.preset_choice.winfo_height(),table.winfo_rooty())
        profile=presets.add(app.data,'別の規則');next(p for p in profile['parameters'] if p['id']=='P3')['role']='胴長'
        e.refresh();app.update();e.preset_choice.set(profile['name']);e.preset_choice.event_generate('<<ComboboxSelected>>');app.update()
        self.assertEqual(table.canvas.itemcget(table.canvas.find_withtag('caption:PHEI')[0],'text'),'胴長')
        for attr,value in (('OBST','2'),('NAPP','6')):
            table.begin_edit(attr);table.editing['variable'].set(value);self.assertTrue(table.finish_edit())
        self.assertEqual(negative['attrs']['OBST'],'2');self.assertEqual(negative['attrs']['NAPP'],'6');self.assertEqual(negative['attrs']['PHEI'],'PARAM 3')

    def test_scroll_and_nested_element_renaming_keep_hierarchy(self):
        app=self.app;app.switch('gmset');app.update();e=app.geometry_editor
        extrusion=schema.add_element(e.definition(),'SEXT');loop=schema.add_child(extrusion)
        vertices=[schema.add_child(loop) for _ in range(30)];e.element_id=vertices[0]['id'];e.refresh();app.update();view=e.elements
        view.focus_force();view.event_generate('<End>');app.update();last=vertices[-1]
        self.assertEqual(e.element_id,last['id']);self.assertEqual(view.parent(last['id']),loop['id']);self.assertTrue(view.bbox(last['id']))
        view.begin_edit(last['id']);view.editing['variable'].set('終端の頂点');view.finish_edit();app.update()
        self.assertEqual(last['name'],'終端の頂点');self.assertIs(extrusion['children'][0],loop);self.assertEqual(view.item(last['id'],'values')[2],'SVER')
        header_top=view.coords(view.find_withtag('header')[0])[1];self.assertAlmostEqual(header_top,view.canvasy(0))
        view.event_generate('<Home>');app.update();self.assertLessEqual(view.canvasy(0),1)
