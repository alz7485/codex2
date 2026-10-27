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

    def test_compact_add_dialog_cancel_and_missing_anchor_leave_data_unchanged(self):
        before=copy.deepcopy(self.app.data)
        win=self.b.add_definition();self.app.update()
        self.assertLessEqual(win.winfo_width(),460);self.assertLessEqual(win.winfo_height(),330)
        def descendants(widget):
            for child in widget.winfo_children():yield child;yield from descendants(child)
        buttons={str(w['text']):w for w in descendants(win) if w.winfo_class()=='TButton'}
        self.assertTrue(buttons['適用'].winfo_ismapped());self.assertTrue(buttons['キャンセル'].winfo_ismapped())
        buttons['キャンセル'].invoke();self.app.update();self.assertEqual(self.app.data,before)
        selected=self.b.tree.selection()[0]
        def stale(title,fields,apply):
            values={k:str(v) for k,_,v,_ in fields};values['name']='/SHOULD-NOT-APPEAR'
            self.app.data['definitions'][:]=[d for d in self.app.data['definitions'] if 'definitions:'+d['id']!=selected]
            snapshot=copy.deepcopy(self.app.data)
            with self.assertRaises(ValueError):apply(values)
            self.assertEqual(self.app.data,snapshot)
        with patch.object(self.app,'form',side_effect=stale):self.b.add_definition()
        self.assertEqual(self.errors,[])
