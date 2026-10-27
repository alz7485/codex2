import copy
import tkinter as tk
import unittest
from unittest.mock import patch
from catalog_studio.integrated import IntegratedStudio
from catalog_studio import browser_folders as folders, project, element_library


class WorkspaceUiTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.update()
        self.b=self.app.registered_browser
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def pick(self,key):self.b.tree.selection_set(key);self.app.update()

    def test_compact_layout_camera_and_reference_selectors_preserve_data(self):
        for page in ('ptset','gmset'):
            self.app.definition_id=next(d['id'] for d in self.app.data['definitions'] if d.get('sample')=='manual-valve' and d['kind']==page.upper())
            self.app.switch(page);self.app.update();e=self.app.geometry_editor
            before=copy.deepcopy(self.app.data)
            view=e.point_canvas if page=='ptset' else e.geometry_view
            view.view_buttons['立体'].invoke();self.app.update()
            right,up=view.camera.basis()
            self.assertGreater(right[0],0);self.assertLess(right[1],0)
            self.assertGreater(up[0],0);self.assertGreater(up[1],0)
            self.assertFalse(hasattr(e,'workspace_header'))
            self.assertTrue(self.b.macro_button.winfo_ismapped())
            self.assertLess(e.preset_choice.winfo_rooty(),e.tables['main'].winfo_rooty())
            self.assertLess(e.tables['main'].winfo_rooty()-e.preset_choice.winfo_rooty(),50)
            self.assertEqual(int(view.toolbar.grid_info()['row']),0)
            self.assertGreater(view.selection_label.winfo_rooty(),view.canvas.winfo_rooty())
            if page=='gmset':
                self.assertTrue(e.ptset_choice.winfo_ismapped());self.assertTrue(view.scom_choice.winfo_ismapped())
                self.assertGreater(view.scom_choice.winfo_rooty(),view.canvas.winfo_rooty()+view.canvas.winfo_height())
            self.app.geometry('1120x780');self.app.update()
            self.assertGreater(view.canvas.winfo_height(),100)
            self.assertTrue(view.toolbar_scroll.winfo_ismapped())
            view.toolbar_viewport.xview_moveto(1);self.app.update()
            self.assertLessEqual(view.focus_button.winfo_rootx()+view.focus_button.winfo_width(),view.toolbar_viewport.winfo_rootx()+view.toolbar_viewport.winfo_width())
            view.open_details();self.app.update();self.assertTrue(view.details.winfo_ismapped())
            view.close_details();self.app.update();self.app.geometry('1440x960');self.app.update()
            self.assertEqual(self.app.data,before)
        self.assertFalse(hasattr(self.b,'organize_button'))
        self.assertEqual(self.b.add_button.winfo_y(),self.b.folder_button.winfo_y())
        self.assertEqual(self.errors,[])

    def test_cut_paste_root_folder_copy_keyboard_and_project_boundary(self):
        f=folders.add(self.app.data,'ptset','弁');self.app.mark();self.app.update()
        record=self.app.geometry_editor.definition();key='definitions:'+record['id']
        self.pick(key);self.b.tree.focus_force();self.b.tree.event_generate('<Control-x>');self.app.update()
        self.assertIsNotNone(self.b.clipboard)
        self.assertEqual(self.b.tree.parent(key),'')
        self.pick('folder:'+f);self.b.paste_item();self.app.update()
        self.assertEqual(self.b.tree.parent(key),'folder:'+f);self.assertIsNone(self.b.clipboard)
        self.b.copy_item();self.b.paste_item();self.app.update()
        newkey=self.b.tree.selection()[0];self.assertNotEqual(newkey,key)
        duplicate=project.get(self.app.data,'definitions',newkey.split(':')[1])
        self.assertEqual([e['attrs'] for e in record['elements']],[e['attrs'] for e in duplicate['elements']])
        self.b.copy_item();self.app.data=copy.deepcopy(self.app.data);before=copy.deepcopy(self.app.data)
        self.b.paste_item();self.assertEqual(self.app.data,before)
        self.assertIn('プロジェクト',self.app.status['text']);self.assertEqual(self.errors,[])

    def test_gmset_preset_dropdown_recalls_independent_elements(self):
        self.app.switch('gmset');self.app.update();e=self.app.geometry_editor
        source=e.definition();preset=element_library.register(self.app.data,source,'形状プリセット')
        e.refresh();self.app.update();old=source['elements'][0]['id']
        e.element_preset_choice.set(preset['name'])
        from catalog_studio.element_presets_ui import select_ptset_preset
        with patch('catalog_studio.element_presets_ui.messagebox.askyesno',return_value=True):select_ptset_preset(e)
        self.app.update();self.assertNotEqual(e.definition()['elements'][0]['id'],old)
        self.assertEqual(e.definition()['element_preset_id'],preset['id']);self.assertEqual(self.errors,[])
