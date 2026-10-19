import copy
import tempfile
import unittest
from pathlib import Path
from catalog_studio import macro_import as mi, macro_export as me, expressions, project

SAMPLE = Path(__file__).resolve().parents[1]/'examples'/'alp-creation-sample.mac'


class AlpMacroTests(unittest.TestCase):
    def test_observed_aliases_and_raw_expression_values(self):
        gm = mi.parse(SAMPLE.read_text()).definitions[0]
        self.assertEqual([e['type'] for e in gm['elements']], ['SCYL', 'SSPH', 'LINE', 'LSNO'])
        self.assertEqual(gm['elements'][2]['attrs']['PTS'], 'P1 P3')
        self.assertEqual(gm['elements'][0]['attrs']['PDIA'], 'SUM PARAM 2 IPARAM 1')
        self.assertEqual(gm['elements'][3]['attrs']['PTDI'], '( ATTRIB PARA[4 ] + 2 + ATTRIB DESP[1 ] )')
        self.assertEqual(gm['elements'][0]['attrs']['NAPP'], '0')
        self.assertTrue(all(r['macro_locked'] for r in [gm]+gm['elements']))
        contexts={'PARAM':{'P2':40,'P4':30},'IPARAM':{'P1':10},'DES PARAM':{'P1':5}}
        self.assertEqual(expressions.evaluate(gm['elements'][0]['attrs']['PDIA'], contexts), 50)
        self.assertEqual(expressions.evaluate(gm['elements'][1]['attrs']['PDIA'], contexts), 10)
        self.assertEqual(expressions.evaluate(gm['elements'][3]['attrs']['PTDI'], contexts), 37)

    def test_export_full_envelope_and_sjis_round_trip(self):
        records = mi.parse(SAMPLE.read_text()).definitions
        before=copy.deepcopy(records)
        source=me.creation_text(records)
        self.assertIn('INPUT BEGIN\nNEW GMSET /DEMO-ALP-SHAPES',source)
        self.assertIn('NEW SCYLINDER',source);self.assertIn('NEW LSNOUT',source)
        self.assertIn('SETP P1 P3',source);self.assertIn('CLFL true',source)
        self.assertIn('OLD SSPHERE 1 OF GMSET /DEMO-ALP-SHAPES\nLOCK',source)
        self.assertTrue(source.endswith('INPUT END GMSET /DEMO-ALP-SHAPES\n\nINPUT FINISH\n'))
        self.assertEqual(records,before)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'alp.mac';me.save(path,source)
            decoded,_=mi.read_text(path)
            imported=mi.parse(decoded).definitions[0]
        for old,new in zip(records[0]['elements'],imported['elements']):
            self.assertEqual(old['attrs'],new['attrs']);self.assertTrue(new['macro_locked'])

    def test_nested_type_ordinals_and_unlocked_elements(self):
        source='''INPUT BEGIN
NEW GMSET /NESTED
NEW SCYLINDER
PHEI 12
END
NEW SSPHERE
PDIA 8
END
NEW SCYLINDER
NEW NSCY
PHEI 2
END
END
END
OLD SCYLINDER 2 OF GMSET /NESTED
LOCK
OLD NSCY 1 OF SCYLINDER 2 OF GMSET /NESTED
LOCK
INPUT END GMSET /NESTED
INPUT FINISH'''
        gm=mi.parse(source).definitions[0]
        self.assertFalse(gm['macro_locked']);self.assertFalse(gm['elements'][0]['macro_locked'])
        self.assertTrue(gm['elements'][2]['macro_locked'])
        exported=me.creation_text([gm])
        self.assertNotIn('OLD SCYLINDER 1 OF GMSET',exported)
        self.assertIn('OLD NSCY 1 OF SCYLINDER 2 OF GMSET',exported)
        self.assertFalse(mi.parse(exported).definitions[0]['macro_locked'])

    def test_rename_import_and_project_reload_keep_locks(self):
        data=project.sample();parsed=mi.parse(SAMPLE.read_text())
        data['definitions'].append(copy.deepcopy(parsed.definitions[0]))
        candidate,added,renamed=mi.prepare_import(data,parsed,[parsed.definitions[0]['id']])
        self.assertTrue(renamed)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'project.json';project.save(candidate,path);loaded=project.load(path)
        record=next(d for d in loaded['definitions'] if d['id']==added[0]['id'])
        exported=me.creation_text([record]);mi.parse(exported)
        self.assertIn('OLD GMSET '+record['name']+'\nLOCK',exported)
        self.assertNotIn('OLD GMSET /DEMO-ALP-SHAPES\n',exported)

    def test_reject_invalid_envelopes_external_targets_and_commands(self):
        base=SAMPLE.read_text()
        cases=[base.replace('INPUT BEGIN','INPUT BEGIN\nINPUT BEGIN',1),
               base.replace('INPUT END GMSET /DEMO-ALP-SHAPES','INPUT END GMSET /OTHER'),
               base.replace('OLD LINE 1 OF GMSET','OLD LINE 2 OF GMSET'),
               base.replace('OLD GMSET /DEMO-ALP-SHAPES','OLD GMSET /EXTERNAL'),
               base.replace('OLD GMSET /DEMO-ALP-SHAPES\n',''),
               base.replace('INPUT FINISH',''),base.replace('INPUT END GMSET /DEMO-ALP-SHAPES',''),
               base+'\nNEW GMSET /AFTER',base.replace('LOCK','DELETE ALL',1),
               'INPUT FINISH','OLD GMSET /EXTERNAL\nLOCK',
               base.replace('NEW GMSET /DEMO-ALP-SHAPES','NEW GMSET /DEMO-ALP-SHAPES\nNEW GMSET /SECOND')]
        for source in cases:
            with self.subTest(source=source[:100]),self.assertRaises(ValueError):mi.parse(source)

    def test_multi_set_output_and_new_records_lock_default(self):
        records=mi.parse('NEW PTSET /POINTS\nNEW PTAXI\nNUMB 1\nEND\nEND\nNEW GMSET /SHAPES\nNEW SCYL\nPAXI P1\nEND\nEND').definitions
        output=me.creation_text(records)
        self.assertEqual(output.count('INPUT BEGIN'),2)
        self.assertEqual(output.count('INPUT FINISH'),1)
        parsed=mi.parse(output).definitions
        self.assertEqual(len(parsed),2)
        self.assertTrue(all(r['macro_locked'] for r in parsed))
