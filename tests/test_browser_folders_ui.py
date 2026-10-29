import copy
import tkinter as tk
import unittest
from unittest.mock import patch
from catalog_studio import browser_folders as folders, project
from catalog_studio.integrated import IntegratedStudio


class FolderBrowserGuiTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.update();self.b=self.app.registered_browser
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def select(self,key):self.b.tree.selection_set(key);self.app.update()

    def test_folder_actions_search_and_selection_keep_definition_edits(self):
        def accept(title,fields,apply):
            values={k:str(v) for k,_,v,_ in fields};values['name']='配管部品';apply(values)
        with patch.object(self.app,'form',side_effect=accept):self.b.add_folder()
        self.app.mark();self.app.update()
        folder=self.app.data['browser_folders'][0]['id'];d=self.app.geometry_editor.definition();key='definitions:'+d['id']
        folders.move(self.app.data,'ptset',key,folder);self.app.mark();self.app.update()
        self.assertEqual(self.b.tree.parent(key),'folder:'+folder)
        self.b.search.set(d['name']);self.app.update()
        self.assertTrue(self.b.tree.exists('folder:'+folder));self.assertTrue(self.b.tree.exists(key))
        self.select(key);self.assertEqual(self.app.geometry_editor.definition_id,d['id'])
        self.assertEqual(self.errors,[])

    def test_catalog_add_icons_create_in_selected_cate_and_hide_on_other_pages(self):
        first=project.add_cate(self.app.data,'/ICON-FIRST')
        second=project.add_cate(self.app.data,'/ICON-SECOND')
        self.app.switch('catalog');self.app.update();self.select('cates:'+second['id'])
        for kind in ('SDTE','TEXT','SCOM'):
            with patch.object(self.app,'form') as form,patch.object(self.app,'scom_form') as modal:
                self.b.text_menu.invoke(1) if kind=='TEXT' else self.b.catalog_buttons[kind].invoke()
                self.app.update();form.assert_not_called();modal.assert_not_called()
            collection='scoms' if kind=='SCOM' else 'texts'
            record=self.app.data[collection][-1]
            self.assertEqual(record.get('type','SCOM'),kind)
            self.assertEqual(record.get('parent_id',record.get('cate_id')),second['id'])
            self.assertEqual(self.b.tree.selection(),(collection+':'+record['id'],))
            self.assertTrue(self.app.catalog_inspector.fields)
        self.b.folder_button.invoke();self.app.update()
        folder=self.b.tree.selection()[0]
        self.b.cate_menu.invoke(1);self.app.update()
        self.assertEqual(self.b.tree.parent(self.b.tree.selection()[0]),folder)
        self.assertIsNone(self.app.grab_current())
        self.assertTrue(self.b.macro_button.winfo_ismapped())
        self.assertEqual([self.b.macro_menu.entrycget(i,'label') for i in (0,1,3)],['読込','出力','登録先編集'])
        self.app.cate_id=None;self.b.refresh()
        self.assertEqual(str(self.b.catalog_buttons['CATE']['state']),'normal')
        self.assertTrue(all(str(b['state'])=='disabled' for k,b in self.b.catalog_buttons.items() if k!='CATE'))
        self.app.switch('ptset');self.app.update()
        self.assertTrue(all(not b.winfo_ismapped() for b in self.b.catalog_buttons.values()))
        self.assertEqual(self.errors,[])

    def test_catalogue_uses_left_tree_for_empty_cate_and_related_data(self):
        from catalog_studio.catalog_workspace import add_association
        cate=project.add_cate(self.app.data,'/EMPTY-CATE')
        prop=add_association(self.app.data,'PROP','/EMPTY-PROP',cate['id'])
        f=folders.add(self.app.data,'catalog','弁');folders.move(self.app.data,'catalog','cates:'+cate['id'],f)
        self.app.switch('catalog');self.app.update();self.select('cates:'+cate['id'])
        self.assertIs(self.app.catalog_tree,self.b.tree);self.assertEqual(len(self.app.catalog_panes.panes()),2)
        self.assertEqual(self.app.cate_id,cate['id']);self.assertIsNone(self.app.scom_id)
        self.select('catalog_props:'+prop['id']);self.assertTrue(self.app.catalog_inspector.winfo_ismapped())
        self.assertEqual(self.app.catalog_members.item()[1]['id'],prop['id'])
        self.b.search.set(prop['name']);self.app.update()
        self.assertTrue(self.b.tree.exists('folder:'+f));self.assertTrue(self.b.tree.exists('cates:'+cate['id']))
        self.assertEqual(self.errors,[])

    def test_spec_folders_select_correct_spec_and_preserve_entries(self):
        spec=project.add_spec(self.app.data,'/NEW-SPEC');old=copy.deepcopy(self.app.data['specs'])
        f=folders.add(self.app.data,'specs','炭素鋼');folders.move(self.app.data,'specs','specs:'+spec['id'],f)
        self.app.switch('specs');self.app.update();self.select('specs:'+spec['id'])
        self.assertIs(self.app.spec_tree,self.b.tree);self.assertEqual(self.app.spec_id,spec['id'])
        self.assertEqual(self.b.tree.parent('specs:'+spec['id']),'folder:'+f)
        self.assertEqual(self.app.data['specs'],old);self.assertEqual(self.errors,[])

    def test_collapsed_folder_is_preserved_when_editing_and_searching(self):
        f=folders.add(self.app.data,'ptset','配管');key='definitions:'+self.app.definition_id
        folders.move(self.app.data,'ptset',key,f);self.app.mark();self.app.update()
        node='folder:'+f;self.b.tree.item(node,open=False)
        self.app.geometry_editor.definition()['name']='/CHANGED-PTSET';self.app.mark();self.app.update()
        self.assertFalse(self.b.tree.item(node,'open'))
        self.b.search.set('/CHANGED-PTSET');self.app.update();self.assertTrue(self.b.tree.item(node,'open'))
        self.b.search.set('');self.app.update();self.assertFalse(self.b.tree.item(node,'open'))
        self.assertEqual(self.errors,[])

    def test_scom_table_selection_updates_integrated_tree(self):
        self.app.switch('catalog');self.app.update()
        record=next(s for s in self.app.data['scoms'] if s['cate_id']==self.app.cate_id and s['id']!=self.app.scom_id)
        self.app.scom_table.selection_set(record['id']);self.app.update()
        self.assertEqual(self.app.scom_id,record['id'])
        self.assertEqual(self.b.tree.selection(),('scoms:'+record['id'],))
        self.assertEqual(self.errors,[])

    def test_new_record_selection_takes_precedence_over_selected_folder(self):
        f=folders.add(self.app.data,'ptset','配管');self.app.mark();self.app.update()
        self.select('folder:'+f)
        record=dict(id='new-from-folder',name='/NEW-PTSET',kind='PTSET',revision='01',elements=[])
        self.app.data['definitions'].append(record);self.app.definition_id=record['id'];self.app.mark();self.app.update()
        self.assertEqual(self.b.tree.selection(),('definitions:'+record['id'],))
        self.assertEqual(self.errors,[])
