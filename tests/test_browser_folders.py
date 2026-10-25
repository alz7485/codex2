import copy
import tempfile
import unittest
from pathlib import Path
from catalog_studio import project, browser_folders as folders


class BrowserFolderTests(unittest.TestCase):
    def test_nested_move_roundtrip_does_not_change_records_or_names(self):
        data=project.sample();before=copy.deepcopy(data)
        top=folders.add(data,'ptset','配管');child=folders.add(data,'ptset','弁',top)
        folders.move(data,'ptset','definitions:pt-reducer',child)
        folders.update(data,child,name='手動弁');project.validate(data)
        for key in before:self.assertEqual(data[key],before[key])
        with tempfile.TemporaryDirectory() as path:
            target=Path(path)/'project.json';project.save(data,target);loaded=project.load(target)
        self.assertEqual(loaded['browser_folders'],data['browser_folders'])
        self.assertEqual(loaded['browser_placements'],data['browser_placements'])
        self.assertEqual(folders.choices(data,'ptset')['フォルダ：配管 / 手動弁'],child)

    def test_cycles_cross_page_duplicates_and_invalid_moves_are_atomic(self):
        data=project.sample();a=folders.add(data,'ptset','A');b=folders.add(data,'ptset','B',a);g=folders.add(data,'gmset','G')
        for action in (lambda:folders.update(data,a,parent=b),lambda:folders.update(data,a,parent=g),lambda:folders.add(data,'ptset','A'),lambda:folders.move(data,'ptset','definitions:pt-reducer',g),lambda:folders.add(data,'ptset','bad/name')):
            before=copy.deepcopy(data)
            with self.assertRaises(ValueError):action()
            self.assertEqual(data,before)

    def test_only_empty_folder_deleted_and_records_can_return_to_root(self):
        data=project.sample();a=folders.add(data,'ptset','A');folders.move(data,'ptset','definitions:pt-reducer',a)
        with self.assertRaises(ValueError):folders.remove(data,a)
        folders.move(data,'ptset','definitions:pt-reducer');folders.remove(data,a)
        self.assertEqual(data['browser_folders'],[]);self.assertEqual(data['browser_placements'],{})

    def test_catalogue_folder_move_preserves_owner_and_rejects_member_move(self):
        data=project.sample();before=copy.deepcopy(data['scoms']);f=folders.add(data,'catalog','配管')
        folders.move(data,'catalog','cates:cate-reducer',f)
        with self.assertRaises(ValueError):folders.move(data,'catalog','scoms:scom-65-40',f)
        self.assertEqual(data['scoms'],before)

    def test_old_project_still_valid_and_bad_metadata_is_rejected(self):
        data=project.sample();project.validate(data)
        data['browser_folders']=[dict(id='x',name='X',page='ptset',parent_id='x')]
        with self.assertRaises(ValueError):project.validate(data)
