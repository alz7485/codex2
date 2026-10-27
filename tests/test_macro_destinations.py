import copy
import tempfile
import unittest
from pathlib import Path
from catalog_studio import macro_destinations as md, macro_export, macro_import, project


class MacroDestinationTests(unittest.TestCase):
    def test_destination_lists_migrate_validate_and_keep_failed_edits_atomic(self):
        data={md.KEY:{'PTSET':'LEGACY'}}
        self.assertEqual(md.options(data,'PTSET'),['/LEGACY'])
        md.save_options(data,'PTSET',['A','/B','A',''])
        self.assertEqual(md.options(data,'PTSET'),['/A','/B'])
        before=copy.deepcopy(data)
        with self.assertRaises(ValueError):md.save_options(data,'PTSET',['/C','BAD;DELETE'])
        self.assertEqual(data,before)
        for invalid in ([1],['/A','/A'],['BAD'],['/A;LOCK']):
            candidate=copy.deepcopy(data);candidate[md.LIST_KEY]['PTSET']=invalid
            with self.assertRaises(ValueError):md.validate_storage(candidate)
        md.save_options(data,'PTSET',[]);self.assertEqual(md.options(data,'PTSET'),[])

    def test_normalize_prefix_and_reject_command_injection(self):
        for raw, expected in [('PT-ROOT','/PT-ROOT'), (' /GM-ROOT ', '/GM-ROOT'), ('CAT/POINTS','/CAT/POINTS'), ('','')]:
            self.assertEqual(md.normalize(raw), expected)
            self.assertEqual(md.normalize(expected), expected)
        for raw in ['/', 'ROOT NAME', 'ROOT\nDELETE ALL', '/ROOT,DELETE', '/ROOT$*', '/ROOT;LOCK', '/ROOT|', '/ROOT\tNEXT']:
            with self.subTest(raw=raw), self.assertRaises(ValueError): md.normalize(raw)

    def test_each_kind_selects_its_own_folder_before_new_and_round_trips(self):
        records = macro_import.parse('NEW PTSET /POINTS\nNEW PTAXIS\nNUMB 1\nEND\nEND\nNEW GMSET /SHAPES\nNEW SCYL\nPAXI P1\nEND\nEND').definitions
        folders = {'PTSET':'POINTS-ROOT', 'GMSET':'/SHAPES-ROOT'}
        before = copy.deepcopy((records, folders))
        source = macro_export.creation_text(records, destinations=folders, lock_created=True)
        self.assertTrue(source.startswith('/POINTS-ROOT\nNEW PTSET /POINTS'))
        self.assertIn('/SHAPES-ROOT\nNEW GMSET /SHAPES',source)
        parsed = macro_import.parse(source).definitions
        self.assertEqual([r['macro_destination'] for r in parsed], ['/POINTS-ROOT','/SHAPES-ROOT'])
        self.assertTrue(all(r['macro_locked'] for r in parsed))
        self.assertEqual((records, folders),before)

    def test_legacy_blank_destinations_and_no_redundant_reselection(self):
        records = macro_import.parse('NEW PTSET /A\nEND\nNEW PTSET /B\nEND').definitions
        self.assertTrue(macro_export.creation_text(records).startswith('NEW PTSET /A'))
        source = macro_export.creation_text(records, destinations={'PTSET':'ROOT'})
        self.assertEqual(source.splitlines().count('/ROOT'),1)
        self.assertEqual([r['macro_destination'] for r in macro_import.parse(source).definitions], ['/ROOT','/ROOT'])

    def test_destination_settings_save_reload_and_import_does_not_override(self):
        data=project.sample();data[md.KEY]={'PTSET':'/PT-ROOT','GMSET':'/GM-ROOT'}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'project.json';project.save(data,path)
            loaded=project.load(path)
        self.assertEqual(loaded[md.KEY],data[md.KEY])
        parsed=macro_import.parse('/OTHER-ROOT\nNEW GMSET /IMPORTED\nEND')
        candidate,added,_=macro_import.prepare_import(loaded,parsed,[parsed.definitions[0]['id']])
        self.assertEqual(candidate[md.KEY],data[md.KEY])
        self.assertEqual(added[0]['macro_destination'],'/OTHER-ROOT')
        for bad in ([], {'PTSET':4}, {'GMSET':None}):
            candidate=copy.deepcopy(data);candidate[md.KEY]=bad
            with self.assertRaises(ValueError):project.validate(candidate)

    def test_bare_selection_is_only_accepted_outside_definitions(self):
        for text in ('NEW GMSET /G\n/OTHER\nEND','/ROOT LOCK\nNEW GMSET /G\nEND', 'INPUT BEGIN\n/ROOT\nNEW GMSET /G\nEND\nINPUT END GMSET /G\nINPUT FINISH'):
            with self.subTest(text=text), self.assertRaises(ValueError):macro_import.parse(text)
        with self.assertRaises(ValueError):
            macro_export.creation_text(macro_import.parse('NEW PTSET /P\nEND').definitions, destinations={'PTSET':'/P\nDELETE ALL'})
