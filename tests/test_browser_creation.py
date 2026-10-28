import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from catalog_studio import browser_folders as folders, project
from catalog_studio.browser_clipboard import Clipboard
from catalog_studio.valve_sample import standalone
from catalog_studio.integrated import IntegratedStudio


class InsertionTests(unittest.TestCase):
    def test_mixed_folder_item_order_and_roundtrip(self):
        data=standalone();pt=next(d for d in data['definitions'] if d['kind']=='PTSET');key='definitions:'+pt['id']
        f=folders.add(data,'ptset','直後のフォルダ',selected=key)
        self.assertEqual(folders.ordered_keys(data,'ptset'),[key,'folder:'+f])
        child=folders.add(data,'ptset','子フォルダ',selected='folder:'+f)
        new=copy.deepcopy(pt);new.update(id='new-pointset',name='/NEW-PTSET')
        folders.place_created(data,'ptset','definitions:'+new['id'],'folder:'+f);data['definitions'].append(new)
        self.assertEqual(folders.ordered_keys(data,'ptset'),[key,'folder:'+f,'definitions:'+new['id'],'folder:'+child])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'project.json';project.save(data,path);loaded=project.load(path)
        self.assertEqual(folders.ordered_keys(data,'ptset'),folders.ordered_keys(loaded,'ptset'))
        self.assertEqual([d['id'] for d in data['definitions']],[d['id'] for d in loaded['definitions']])

    def test_invalid_anchor_and_failed_folder_creation_are_atomic(self):
        data=standalone();before=copy.deepcopy(data)
        for selected in ('folder:gone','definitions:gone'):
            with self.assertRaises(ValueError):folders.add(data,'ptset','失敗',selected=selected)
            self.assertEqual(data,before)
        bad=copy.deepcopy(data);bad['browser_order']={'ptset':['folder:a','folder:a']}
        with self.assertRaises(ValueError):project.validate(bad)

    def test_copy_retains_mixed_child_order_with_fresh_ids(self):
        data=standalone();pt=next(d for d in data['definitions'] if d['kind']=='PTSET');key='definitions:'+pt['id']
        parent=folders.add(data,'ptset','親');folders.move(data,'ptset',key,parent)
        folders.add(data,'ptset','後ろ',selected=key)
        clip=Clipboard(data,'ptset','folder:'+parent);newkey=clip.paste(data,'ptset')
        order=folders.ordered_keys(data,'ptset');newkeys=order[order.index(newkey):]
        self.assertTrue(newkeys[1].startswith('definitions:'));self.assertTrue(newkeys[2].startswith('folder:'))
        project.validate(data)


class CreationUiTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.update();self.b=self.app.registered_browser
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def accept(self,name):
        def form(title,fields,apply):
            values={k:str(v) for k,_,v,_ in fields};values['name']=name;apply(values)
            self.app.mark();self.app.render_page();self.app.update()
        return form

    def test_sidebar_order_and_selected_placement_in_both_pages(self):
        for page in ('ptset','gmset'):
            self.app.switch(page);self.app.update();original=self.app.geometry_editor.definition();key='definitions:'+original['id']
            self.b.tree.selection_set(key);self.app.update()
            self.assertLess(self.b.heading.winfo_rooty(),self.b.add_button.winfo_rooty())
            self.assertLess(self.b.add_button.winfo_rooty(),self.b.search_entry.winfo_rooty())
            self.assertLess(self.b.search_entry.winfo_rooty(),self.b.tree.winfo_rooty())
            self.assertTrue(self.b.add_button['image']);self.assertEqual(str(self.b.folder_button['compound']),'none')
            with patch.object(self.app,'form',side_effect=self.accept('挿入フォルダ')):self.b.add_folder()
            folder=self.app.data['browser_folders'][-1]['id'];root=self.b.tree.get_children('')
            self.assertEqual(root[root.index(key)+1],'folder:'+folder)
            self.b.tree.selection_set('folder:'+folder);self.app.update()
            with patch.object(self.app,'form',side_effect=self.accept('/INSERTED-'+page)):self.b.add_definition()
            newkey='definitions:'+self.app.definition_id
            self.assertEqual(self.b.tree.get_children('folder:'+folder)[0],newkey)
            with patch.object(self.app,'form',side_effect=self.accept('アイテム直後')):self.b.add_folder()
            self.assertEqual(self.b.tree.get_children('folder:'+folder)[1],'folder:'+self.app.data['browser_folders'][-1]['id'])
        self.assertEqual(self.errors,[])

    def test_immediate_creation_names_inline_rename_and_cancel(self):
        with patch.object(self.app,'form') as form:
            self.b.add_definition();self.app.update()
            self.assertEqual(self.app.geometry_editor.definition()['name'],'新しいアイテム(1)')
            self.b.add_definition();self.app.update()
            self.assertEqual(self.app.geometry_editor.definition()['name'],'新しいアイテム(2)')
            self.b.add_folder();self.app.update()
            self.assertEqual(self.app.data['browser_folders'][-1]['name'],'新しいフォルダ(1)')
            form.assert_not_called()
        self.b.rename_item();self.app.update()
        self.b.renaming['variable'].set('変更したフォルダ')
        self.assertTrue(self.b.finish_rename());self.app.update()
        self.assertEqual(self.app.data['browser_folders'][-1]['name'],'変更したフォルダ')
        self.b.rename_item();self.b.renaming['variable'].set('取り消す')
        self.b.cancel_rename();self.app.update()
        self.assertEqual(self.app.data['browser_folders'][-1]['name'],'変更したフォルダ')
        self.b.add_definition();self.app.update();record=self.app.geometry_editor.definition()
        before=copy.deepcopy(record)
        self.b.rename_item();self.b.renaming['variable'].set('新しいアイテム(1)')
        self.assertFalse(self.b.finish_rename());self.assertEqual(record,before)
        self.b.renaming['variable'].set('/RENAMED');self.assertTrue(self.b.finish_rename());self.app.update()
        self.assertEqual(record['name'],'/RENAMED')
        self.assertGreaterEqual(self.b.winfo_width(),250)
        self.assertEqual(self.errors,[])
