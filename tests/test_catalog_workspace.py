import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from catalog_studio import booklet, catalog_workspace as workspace, project
from catalog_studio.integrated import IntegratedStudio
from catalog_studio.catalog_members_ui import bundle_form


class CatalogWorkspaceTests(unittest.TestCase):
    def bundle(self,data=None,**options):
        data=data or project.sample()
        return workspace.prepare_bundle(data,'/WORKSPACE',ptset_id='pt-reducer',gmset_id='gm-reducer',**options)

    def test_bundle_creates_members_and_separate_spec_choices_atomically(self):
        original=project.sample();before=copy.deepcopy(original)
        data,records=self.bundle(original,stext='Face-to-face length',rtex='Synthetic part',prop_attrs={'density':7800,'custom':{'unit':'kg/m3'}})
        self.assertEqual(original,before)
        self.assertEqual(set(records),{'CATE','SDTE','TEXT','SCOM','DETAIL','PROP'})
        for kind in ('SDTE','TEXT'):self.assertEqual(records[kind]['parent_id'],records['CATE']['id'])
        for kind in ('SCOM','DETAIL','PROP'):self.assertEqual(records[kind]['cate_id'],records['CATE']['id'])
        self.assertEqual(records['DETAIL']['sdte_id'],records['SDTE']['id'])
        self.assertEqual(records['PROP']['attrs']['custom'],{'unit':'kg/m3'})
        self.assertEqual(records['TEXT']['attrs'],{'STEXT':'Face-to-face length'})
        self.assertEqual(records['SCOM']['values'],{})
        self.assertEqual(data['scoms'][:-1],before['scoms'])
        self.assertNotIn('DETAIL',records['SCOM'].get('component_attrs',{}))

    def test_late_errors_leave_original_unchanged(self):
        data=project.sample();before=copy.deepcopy(data)
        for options in ({'names':{'PROP':'/REDUCER-CATE'}},{'prop_attrs':[]},{'names':{'TEXT':'/same','DETAIL':'/SAME'}},{'preset_id':'missing'}):
            with self.subTest(options=options),self.assertRaises(ValueError):self.bundle(data,**options)
            self.assertEqual(data,before)

    def test_spec_triple_is_frozen_with_detail_text_and_roundtrips(self):
        data,records=self.bundle()
        records['SCOM']['values']=copy.deepcopy(data['scoms'][0]['values'])
        spec=project.add_spec(data,'/SPEC-WORKSPACE')
        entry=project.add_spec_entry(data,spec,records['SCOM']['id'])
        entry.update(type='TEST',bore1='65',detail_id=records['DETAIL']['id'],prop_id=records['PROP']['id'])
        self.assertTrue(workspace.used(data,'catalog_details',records['DETAIL']['id']))
        self.assertTrue(workspace.used(data,'catalog_props',records['PROP']['id']))
        self.assertTrue(workspace.used(data,'texts',records['SDTE']['id']))
        self.assertEqual(workspace.issues(data),[])
        book=booklet.snapshot(data,[],[spec['id']]);frozen=copy.deepcopy(book)
        self.assertEqual(book['catalog_details'][0]['id'],records['DETAIL']['id'])
        self.assertEqual(book['catalog_props'][0]['id'],records['PROP']['id'])
        self.assertIn(records['SDTE']['id'],{item['id'] for item in book['texts']})
        records['DETAIL']['name']='/LATER';records['PROP']['attrs']['future']='changed'
        self.assertEqual(book,frozen);data['books'].append(book)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'project.json';project.save(data,path);self.assertEqual(project.load(path),data)
            pdf=Path(folder)/'book.pdf';booklet.generate_pdf(book,pdf);self.assertTrue(pdf.read_bytes().startswith(b'%PDF'))
        review=project.macro_text(data)
        self.assertIn('DETAIL → /LATER',review);self.assertIn('PROP → /WORKSPACE/PROP',review)
        self.assertTrue(all(line.startswith('$*') for line in review.splitlines()))

    def test_old_projects_remain_unchanged_and_new_refs_are_validated(self):
        data=project.sample();before=copy.deepcopy(data);project.validate(data);self.assertEqual(data,before)
        self.assertEqual(workspace.issues(data),[])
        entry=data['specs'][0]['entries'][0];entry.update(detail_id='',prop_id='missing')
        project.validate(data)
        self.assertEqual(len(workspace.issues(data)),2)
        with self.assertRaises(ValueError):booklet.snapshot(data)
        entry['detail_id']=123
        with self.assertRaises(ValueError):project.validate(data)

    def test_partial_combination_also_requires_the_other_reference(self):
        data,records=self.bundle();entry=data['specs'][0]['entries'][0]
        entry['detail_id']=records['DETAIL']['id']
        self.assertEqual(len(workspace.issues(data)),1)
        self.assertIn('PROP',workspace.issues(data)[0])
        with self.assertRaisesRegex(ValueError,'PROP'):booklet.snapshot(data)


class CatalogWorkspaceGuiTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v))
        self.app.switch('catalog');self.app.update()
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def accept_bundle(self,title,fields,apply):
        values={key:str(value) for key,_,value,_ in fields}
        values.update(cate='/GUI-CATALOG',pt='/REDUCER-POINTS',gm='/REDUCER-GEOM',rtex='Synthetic description',stext='Synthetic parameter names')
        apply(values)
    def create_bundle(self):
        with patch.object(self.app,'form',side_effect=self.accept_bundle):bundle_form(self.app)
        self.app.mark();self.app.render_page();self.app.update()
    def test_menu_tree_and_triple_selection(self):
        app=self.app;self.assertEqual(app.nav['catalog'].cget('text'),'カタログ作成')
        self.create_bundle()
        self.assertEqual(app.catalog_notebook.index('current'),1)
        self.assertGreater(app.catalog_panes.sashpos(0),100)
        self.assertEqual(len(app.catalog_panes.panes()),2)
        self.assertIs(app.catalog_tree,app.registered_browser.tree)
        self.assertEqual(len(app.catalog_members.table.get_children()),4)
        self.assertTrue(app.catalog_tree.exists('cates:'+app.cate_id))
        sdte=next(record for record in app.data['texts'] if record['parent_id']==app.cate_id and record['type']=='SDTE')
        app.catalog_tree.selection_set('texts:'+sdte['id']);app.update()
        self.assertEqual(app.catalog_notebook.index('current'),1)
        self.assertEqual(app.catalog_members.item()[1]['id'],sdte['id'])
        app.catalog_tree.selection_set('scoms:'+app.scom_id);app.update()
        self.assertEqual(app.catalog_notebook.index('current'),0)
        selected=app.scom_id
        spec=project.add_spec(app.data,'/GUI-SPEC');app.spec_id=spec['id'];app.switch('specs');app.update()
        seen={}
        def accept(title,fields,apply):
            values={key:str(value) for key,_,value,_ in fields};seen.update(values)
            values.update(type='TEST',bore1='80');apply(values)
        with patch.object(app,'form',side_effect=accept):app.entry_form()
        app.render_page();app.update();entry=spec['entries'][0]
        self.assertEqual(entry['scom_id'],selected)
        self.assertEqual(entry['detail_id'],app.catalog_detail_id)
        self.assertEqual(entry['prop_id'],app.catalog_prop_id)
        self.assertIn('/GUI-CATALOG/DETAIL',app.spec_table.item(entry['id'],'values'))
        self.assertEqual(self.errors,[])
    def test_individual_member_creation_scoping_and_cancel(self):
        app=self.app;before=copy.deepcopy(app.data)
        win=app.catalog_members.create('TEXT');app.update();win.destroy();app.update()
        self.assertEqual(app.data,before)
        def accept(title,fields,apply):
            values={key:str(value) for key,_,value,_ in fields};values.update(name='/GUI-SCOPED-TEXT');values['attr:STEXT']='Unchanged English';apply(values)
        with patch.object(app,'form',side_effect=accept):app.catalog_members.create('TEXT')
        app.render_page();app.update()
        item=app.catalog_members.item()[1];self.assertEqual(item['parent_id'],app.cate_id)
        self.assertEqual(item['attrs']['STEXT'],'Unchanged English')
        other=project.add_cate(app.data,'/OTHER-CATE');app.cate_id=other['id'];app.scom_id=None;app.render_page();app.update()
        self.assertEqual(app.catalog_members.table.get_children(),())
        self.assertEqual(self.errors,[])
    def test_used_prop_and_detail_text_cannot_be_deleted(self):
        app=self.app;self.create_bundle();prop=app.data['catalog_props'][0];detail=app.data['catalog_details'][0]
        app.data['specs'][0]['entries'][0].update(detail_id=detail['id'],prop_id=prop['id'])
        app.catalog_members.table.selection_set('catalog_props:'+prop['id']);app.update()
        before=copy.deepcopy(app.data)
        with patch('catalog_studio.catalog_members_ui.messagebox.showinfo') as notice,patch('catalog_studio.catalog_members_ui.messagebox.askyesno') as ask:
            app.catalog_members.delete();self.assertTrue(notice.called);ask.assert_not_called()
        self.assertEqual(app.data,before);self.assertEqual(self.errors,[])

    def test_property_edit_keeps_identity_payload_and_spec_reference(self):
        app=self.app;self.create_bundle();prop=app.data['catalog_props'][0]
        prop['attrs']={'nested':{'unit':'original','values':[1,2]},'unknown':True};prop['future_metadata']='keep'
        entry=app.data['specs'][0]['entries'][0];entry['prop_id']=prop['id']
        app.catalog_members.table.selection_set('catalog_props:'+prop['id']);app.update()
        def accept(title,fields,apply):
            values={key:str(value) for key,_,value,_ in fields};values['name']='/RENAMED-PROP';apply(values)
        with patch.object(app,'form',side_effect=accept):app.catalog_members.edit()
        self.assertEqual(prop['name'],'/RENAMED-PROP');self.assertEqual(entry['prop_id'],prop['id'])
        self.assertEqual(prop['attrs']['nested'],{'unit':'original','values':[1,2]})
        self.assertEqual(prop['future_metadata'],'keep');self.assertEqual(self.errors,[])

    def test_actions_are_visible_in_minimum_window(self):
        app=self.app;self.create_bundle();app.geometry('1120x780');app.update()
        for button in app.catalog_members.add_buttons.values():
            self.assertTrue(button.winfo_viewable())
            self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),app.catalog_members.winfo_rootx()+app.catalog_members.winfo_width())
        self.assertGreater(app.catalog_members.table.winfo_height(),60)
        self.assertGreater(app.catalog_members.attributes.winfo_height(),60)
        self.assertEqual(self.errors,[])

    def test_legacy_spec_edit_does_not_add_empty_combination_references(self):
        app=self.app;self.create_bundle();app.switch('specs');app.update()
        entry=app.spec_entry();self.assertNotIn('detail_id',entry)
        def accept(title,fields,apply):
            values={key:str(value) for key,_,value,_ in fields}
            self.assertEqual(values['detail_id'],'未設定');self.assertEqual(values['prop_id'],'未設定')
            values['description']='Legacy edit';apply(values)
        with patch.object(app,'form',side_effect=accept):app.entry_form(entry)
        self.assertNotIn('detail_id',entry);self.assertNotIn('prop_id',entry)
        self.assertEqual(entry['description'],'Legacy edit');self.assertEqual(self.errors,[])
