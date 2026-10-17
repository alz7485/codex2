import copy
import tempfile
import unittest
from pathlib import Path

from catalog_studio import element_schema as schema, macro_import as mi, presets, project


SAMPLE = '''$* Synthetic creation text; no private catalogue data.
NEW PTSET /DEMO-READ-PT
DESC |Test points, not a command: END GMSET|
NEW PTAX
NUM 1 PAXI-Y PDIS (PARA[3] / 2) PCON (PARA[7]) PBOR (PARA[1])
NEW PTCAR /DEMO-READ-P2
NUMBER 2 PX (PARA[3]) PY 0 PZ 0 PTCDIRECTION X45Y
END PTSE
NEW GMSE /DEMO-READ-GM
NEW SCYL
PAXI -Y PDIS (PARA[3] / 2) PHEIGHT (-PARA[3]) PDIAMETER (PARA[2])
OBST 2 TUFL TRUE CLFL FALSE
NEW SEXT
PHEI (PARA[3])
NEW SLOOP
NEW SVERTEX
PX 0 PY 0
NEW SVER
PX 20 PY 0
END SLOO
NEW NSCY
PHEI 30 PDIA 4 NAPP 4
END SEXT
NEW LINE
PTS P1 P2
END GMSET
'''


class MacroImportTests(unittest.TestCase):
    def test_inline_aliases_expressions_and_sibling_hierarchy(self):
        parsed = mi.parse(SAMPLE)
        pt, gm = parsed.definitions
        self.assertEqual((pt['kind'], gm['kind']), ('PTSET','GMSET'))
        self.assertEqual(len(pt['elements']), 2)
        self.assertEqual(pt['elements'][0]['attrs'], {'NUMB':'1','PAXI':'-Y','PDIS':'(PARA[3] / 2)', 'PCON':'(PARA[7])','PBOR':'(PARA[1])'})
        self.assertEqual(pt['elements'][1]['attrs']['PTCDIR'], 'X45Y')
        self.assertNotIn('PAXI', pt['elements'][1]['attrs'])
        self.assertEqual(gm['elements'][0]['attrs']['PHEI'], '(-PARA[3])')
        self.assertEqual(gm['elements'][0]['attrs']['TUFLA'], 'TRUE')
        self.assertEqual([e['type'] for e in gm['elements']], ['SCYL','SEXT','LINE'])
        extrusion = gm['elements'][1]
        self.assertEqual([e['type'] for e in extrusion['children']], ['SLOO','NSCY'])
        self.assertEqual(len(extrusion['children'][0]['children']), 2)
        self.assertEqual(gm['elements'][2]['attrs']['PTS'], 'P1 P2')
        self.assertIn('END GMSET', pt['attrs']['DESC'])
        self.assertEqual(parsed.warnings, [])

    def test_comments_quoted_text_commas_multiline_and_continuation(self):
        parsed = mi.parse('''$( ignored NEW GMSET /BAD $( nested $) $)
new ptse /CASE
new ptax, num 1, pdis (2 *
 PARA[3]), paxi Z $* ignored NEW SCYL
DESC 'A, END ''quoted'' $* text'
PCON BW $
PBOR 80
FUTURE_ATTR |future: NEW, END|
''')
        point = parsed.definitions[0]['elements'][0]
        self.assertEqual(point['attrs']['PDIS'], '(2 *\n PARA[3])')
        self.assertEqual(point['attrs']['PCON'], 'BW')
        self.assertEqual(point['attrs']['PBOR'], '80')
        self.assertEqual(point['attrs']['DESC'], "A, END 'quoted' $* text")
        self.assertEqual(point['attrs']['FUTURE_ATTR'], '|future: NEW, END|')
        self.assertTrue(any('FUTURE_ATTR' in item for item in parsed.warnings))

    def test_no_defaults_and_unset_is_explicit(self):
        point = mi.parse('NEW PTSET /P\nNEW PTAX\nNUM 1\nUNSET PAXI').definitions[0]['elements'][0]
        self.assertEqual(point['attrs'], {'NUMB':'1', 'PAXI':''})

    def test_explicit_units_and_user_defined_attributes_are_preserved(self):
        parsed = mi.parse('NEW GMSET /G\nNEW SCYL\nPDIA 3 mm PHEI (2 inch)\n:LOCAL_NOTE |unit text|')
        self.assertEqual(parsed.definitions[0]['elements'][0]['attrs'], {'PDIA':'3 mm', 'PHEI':'(2 inch)', ':LOCAL_NOTE':'|unit text|'})
        self.assertTrue(any(':LOCAL_NOTE' in warning for warning in parsed.warnings))

    def test_set_and_element_names_and_reassignment(self):
        parsed = mi.parse('NEW PTSET\nNAME /RENAMED\nNEW PTAX\nNAME /POINT\nNUM 1\nPDIS 3\nPDIS 4')
        self.assertEqual(parsed.definitions[0]['name'], '/RENAMED')
        self.assertEqual(parsed.definitions[0]['elements'][0]['name'], '/POINT')
        self.assertEqual(parsed.definitions[0]['elements'][0]['attrs']['PDIS'], '4')
        self.assertTrue(any('再代入' in item for item in parsed.warnings))

    def test_known_wrappers_typed_end_and_tube_diameter(self):
        parsed = mi.parse('NEW CATA /C\nNEW SECT /S\nNEW CATE /A\nDESC |ignored owner|\nNEW PTSET /P\nNEW PTAX\nNUM 1\nEND PTSET\nNEW GMSET /G\nNEW TUBE\nPDIAM 20\nEND GMSET\nEND CATE\nEND SECT\nEND CATA')
        self.assertEqual(len(parsed.definitions), 2)
        self.assertEqual(parsed.definitions[1]['elements'][0]['attrs'], {'PDIAM':'20'})
        self.assertEqual(len(parsed.warnings), 3)

    def test_invalid_or_executable_input_is_rejected_with_line(self):
        for suffix in ['NEW UNKNOWN /X', 'DELETE ALL', '!x = 20', '$M /other.mac',
                       'PDIS (!value)', 'PDIS 5 DELETE ALL', 'PDIS (PARA[3]',
                       "DESC 'unclosed", 'END GMSET', 'NEW SVER', 'PDIS', 'IF TRUE',
                       'PDIS 5; DELETE ALL', 'PDIS NEW SCYL', 'PDIS PAXI X', '$( unclosed']:
            with self.subTest(suffix=suffix), self.assertRaises(mi.MacroImportError) as caught:
                mi.parse('NEW PTSET /P\nNEW PTAX\n' + suffix)
            self.assertIn('行目', str(caught.exception))
        with self.assertRaises(ValueError): mi.parse('$* NEW PTSET /comment only')
        with self.assertRaises(ValueError): mi.parse('END')

    def test_import_subset_atomicity_names_and_new_parameter_rules(self):
        data = project.sample(); original = copy.deepcopy(data)
        parsed = mi.parse(SAMPLE); source = copy.deepcopy(parsed)
        data['definitions'][0]['name'] = '/demo-read-gm'
        original = copy.deepcopy(data)
        candidate, added, renamed = mi.prepare_import(data, parsed, [parsed.definitions[1]['id']])
        self.assertEqual(data, original); self.assertEqual(parsed, source)
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]['name'], '/DEMO-READ-GM-IMPORT-2')
        self.assertEqual(renamed, [('/DEMO-READ-GM','/DEMO-READ-GM-IMPORT-2')])
        self.assertEqual(candidate['definitions'][:-1], original['definitions'])
        self.assertEqual(candidate['scoms'], original['scoms'])
        self.assertEqual(candidate['parameters'], original['parameters'])
        self.assertEqual(candidate.get('active_parameter_preset_id'), original.get('active_parameter_preset_id'))
        self.assertEqual(presets.rules(candidate, added[0]), [])
        self.assertNotEqual(added[0]['id'], parsed.definitions[1]['id'])
        self.assertFalse({e['id'] for e in schema.walk(added[0]['elements'])} & {e['id'] for e in schema.walk(parsed.definitions[1]['elements'])})
        for invalid in [[], ['unknown']]:
            with self.assertRaises(ValueError): mi.prepare_import(data, parsed, invalid)
        self.assertEqual(data, original)

    def test_repeated_import_and_save_reload_preserve_expressions(self):
        parsed = mi.parse(SAMPLE)
        candidate, added, _ = mi.prepare_import(project.sample(), parsed, [d['id'] for d in parsed.definitions])
        second, again, _ = mi.prepare_import(candidate, parsed, [d['id'] for d in parsed.definitions])
        self.assertNotEqual(added[0]['parameter_preset_id'], again[0]['parameter_preset_id'])
        self.assertEqual(added[0]['parameter_preset_id'], added[1]['parameter_preset_id'])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'saved.json'; project.save(second, path)
            loaded = project.load(path)
        self.assertEqual(loaded, second)

    def test_strict_decoding_and_size_limit(self):
        text = 'NEW PTSET /日本語\nNEW PTAX\nNUM 1'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'source.mac'
            for encoding in ['utf-8-sig', 'cp932', 'utf-16']:
                path.write_bytes(text.encode(encoding))
                decoded, _ = mi.read_text(path)
                self.assertEqual(decoded, text)
                self.assertEqual(mi.parse(decoded).definitions[0]['name'], '/日本語')
            path.write_bytes(b'\x00\x00\x00')
            with self.assertRaises(ValueError): mi.read_text(path)
            path.write_bytes(b'x' * (mi.MAX_BYTES + 1))
            with self.assertRaises(ValueError): mi.read_text(path)

    def test_element_count_limit(self):
        with self.assertRaises(ValueError): mi.parse('NEW PTSET /P\n' + 'NEW PTAX\nNUM 1\n' * 201)
