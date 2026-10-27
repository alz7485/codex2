import copy
import json
import unittest
from catalog_studio import project, browser_folders as folders, element_schema as schema
from catalog_studio.browser_clipboard import Clipboard
from catalog_studio.valve_sample import standalone


class ClipboardTests(unittest.TestCase):
    def setUp(self):
        self.data=standalone()
        self.pt=next(r for r in self.data['definitions'] if r['kind']=='PTSET')
        self.gm=next(r for r in self.data['definitions'] if r['kind']=='GMSET')

    def test_copy_keeps_formulas_pairing_children_and_unique_ids(self):
        child=schema.add_element(self.gm,'SCYL');schema.add_child(child,'NSCY')
        original=copy.deepcopy(self.gm)
        clip=Clipboard(self.data,'gmset','definitions:'+self.gm['id'])
        key=clip.paste(self.data,'gmset');duplicate=project.get(self.data,'definitions',key.split(':')[1])
        self.assertEqual(self.gm,original)
        self.assertEqual(duplicate['paired_ptset_id'],self.pt['id'])
        old=list(schema.walk(original['elements']));new=list(schema.walk(duplicate['elements']))
        self.assertEqual([e['attrs'] for e in old],[e['attrs'] for e in new])
        self.assertFalse({e['id'] for e in old}&{e['id'] for e in new})
        another=clip.paste(self.data,'gmset')
        self.assertNotEqual(another,key)
        self.assertEqual(len({d['name'] for d in self.data['definitions']}),4)
        project.validate(json.loads(json.dumps(self.data)))

    def test_nested_folder_copy_and_cut_move_are_atomic(self):
        parent=folders.add(self.data,'ptset','配管');sub=folders.add(self.data,'ptset','弁',parent)
        folders.move(self.data,'ptset','definitions:'+self.pt['id'],sub)
        original=copy.deepcopy(self.pt)
        clip=Clipboard(self.data,'ptset','folder:'+parent)
        root=clip.paste(self.data,'ptset').split(':')[1]
        newsub=next(f['id'] for f in self.data['browser_folders'] if f['parent_id']==root)
        duplicate=self.data['definitions'][-1]
        self.assertEqual(self.data['browser_placements']['ptset|definitions:'+duplicate['id']],newsub)
        self.assertEqual(self.pt,original)
        cut=Clipboard(self.data,'ptset','folder:'+parent,cut=True);before=copy.deepcopy(self.data)
        with self.assertRaises(ValueError):cut.paste(self.data,'ptset',sub)
        self.assertEqual(self.data,before)
        cut.paste(self.data,'ptset',root)
        self.assertEqual(next(f['parent_id'] for f in self.data['browser_folders'] if f['id']==parent),root)
        self.assertEqual(self.pt,original)

    def test_cut_defers_move_preserves_refs_and_rejects_stale_project_or_page(self):
        target=folders.add(self.data,'ptset','コピー先');before=copy.deepcopy(self.data)
        clip=Clipboard(self.data,'ptset','definitions:'+self.pt['id'],cut=True)
        self.assertEqual(self.data,before)
        for data,page in ((copy.deepcopy(self.data),'ptset'),(self.data,'gmset')):
            with self.assertRaises(ValueError):clip.paste(data,page,target)
        self.assertEqual(self.data,before)
        clip.paste(self.data,'ptset',target)
        self.assertEqual(self.data['scoms'],before['scoms'])
        self.assertEqual(self.data['definitions'],before['definitions'])
        self.assertEqual(self.data['browser_placements']['ptset|definitions:'+self.pt['id']],target)
        clip.paste(self.data,'ptset')
        self.assertNotIn('ptset|definitions:'+self.pt['id'],self.data['browser_placements'])

    def test_copy_uses_snapshot_and_failed_validation_leaves_project_intact(self):
        clip=Clipboard(self.data,'ptset','definitions:'+self.pt['id'])
        self.pt['elements'][0]['attrs']['PDIS']='12'
        clip.paste(self.data,'ptset')
        self.assertNotEqual(self.data['definitions'][-1]['elements'][0]['attrs']['PDIS'],'12')
        self.data['parameter_presets'].clear();before=copy.deepcopy(self.data)
        with self.assertRaises(ValueError):clip.paste(self.data,'ptset')
        self.assertEqual(self.data,before)
