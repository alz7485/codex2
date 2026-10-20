import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from catalog_studio import macro_export, macro_import

SAMPLE = Path(__file__).resolve().parents[1]/'examples'/'creation-import-sample.mac'


class MacroExportTests(unittest.TestCase):
    def test_compact_attributes_keep_unknown_text_and_nested_structure(self):
        records = self.records()
        records[0]['attrs'].update(DESC=" O'Brien PCON PBOR ", **{':EXTRA':"'NEW END'"})
        records[1]['elements'][0]['attrs'][':CUSTOM'] = '42'
        before = copy.deepcopy(records)
        output = macro_export.creation_text(records)
        self.assertIn('NUMB 1 PAXI -X PDIS (PARA[3] / 2) PBOR (PARA[1])', output)
        self.assertIn("\n:EXTRA 'NEW END'\n", output)
        self.assertIn('\n:CUSTOM 42\n', output)
        self.assertFalse(any(line.startswith(('INPUT ', 'OLD ', '$*')) or line == 'LOCK' for line in output.splitlines()))
        self.assertEqual(records, before)
        result = macro_import.parse(output).definitions
        self.assertEqual(result[0]['attrs'], records[0]['attrs'])
        self.assertEqual(result[1]['elements'][0]['attrs'], records[1]['elements'][0]['attrs'])

    def test_optional_lock_uses_current_element_after_children(self):
        records = macro_import.parse('NEW GMSET /NESTED\nNEW SCYL\nPHEI 30\nNEW NSCY\nPHEI 10\nEND\nEND\nEND').definitions
        output = macro_export.creation_text(records, lock_created=True)
        self.assertNotIn('OLD ', output); self.assertNotIn('INPUT ', output)
        self.assertIn('PHEI 10\nLOCK\nEND\nLOCK\nEND\nLOCK\nEND', output)
        root = macro_import.parse(output).definitions[0]
        self.assertTrue(root['macro_locked'])
        self.assertTrue(root['elements'][0]['macro_locked'])
        self.assertTrue(root['elements'][0]['children'][0]['macro_locked'])

    def records(self):
        return macro_import.parse(SAMPLE.read_text()).definitions

    def test_round_trip_expressions_signed_height_and_metadata(self):
        records = self.records()
        records[1]['preview_params'] = {'1': 987654}
        records[1]['elements'][0]['attrs']['PDIS'] = '(APARA[2] + IPARA[1] + OPARA[3])'
        before = copy.deepcopy(records)
        text = macro_export.creation_text(records)
        parsed = macro_import.parse(text).definitions
        self.assertEqual(records, before)
        self.assertIn('PHEI (-PARA[3])', text)
        self.assertNotIn('987654', text)
        for old, new in zip(records, parsed):
            self.assertEqual(old['attrs'], new['attrs'])
            self.assertEqual([e['attrs'] for e in old['elements']], [e['attrs'] for e in new['elements']])

    def test_nested_negatives_outline_and_names(self):
        records = macro_import.parse('''NEW GMSET /TEST
NEW SCYL /TEST/CYL
PHEI -100
NEW NSCY
PHEI -80
END
END
NEW SEXT
NEW SLOO
NEW SVER
PX 1
PY 2
END
NEW SVER
PX 3
PY 4
END
END
END
END''').definitions
        result = macro_import.parse(macro_export.creation_text(records)).definitions[0]
        self.assertEqual(result['elements'][0]['name'], '/TEST/CYL')
        self.assertEqual(result['elements'][0]['children'][0]['attrs']['PHEI'], '-80')
        self.assertEqual([e['attrs']['PX'] for e in result['elements'][1]['children'][0]['children']], ['1', '3'])

    def test_text_quotes_extra_attributes_and_unset(self):
        records = self.records()[:1]
        attrs = records[0]['attrs']
        attrs.update(DESC=" 日本語 O'Brien ", PURP='example', PSKEY='unset', **{':CUSTOM':'42'})
        result = macro_import.parse(macro_export.creation_text(records)).definitions[0]
        self.assertEqual(result['attrs']['DESC'], attrs['DESC'])
        self.assertEqual(result['attrs'][':CUSTOM'], '42')
        self.assertNotIn('PSKEY', result['attrs'])

    def test_reject_ambiguous_or_executable_values_and_names(self):
        for value in ('100\nDELETE ALL', '100, PHEI 20', '100 $*lost', '100 PHEI 20', '!secret', '1;DELETE ALL'):
            records = self.records()
            records[1]['elements'][0]['attrs']['PDIS'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                macro_export.creation_text(records)
        for name in ('no-slash', '/bad name', '/bad\nDELETE', '/bad,DELETE', '/bad$*'):
            records = self.records(); records[0]['name'] = name
            with self.subTest(name=name), self.assertRaises(ValueError):
                macro_export.creation_text(records)

    def test_reject_legacy_types_duplicate_aliases_and_invalid_hierarchy(self):
        records = self.records()
        records[1]['elements'][0]['type'] = 'cylinder'
        with self.assertRaises(ValueError): macro_export.creation_text(records)
        records = self.records()
        records[0]['elements'][0]['attrs']['NUMBER'] = '9'
        with self.assertRaises(ValueError): macro_export.creation_text(records)
        records = self.records()
        records[0]['elements'].append(records[1]['elements'][0])
        with self.assertRaises(ValueError): macro_export.creation_text(records)

    def test_tube_diameter_alias_and_point_references(self):
        records = macro_import.parse('''NEW PTSET /PTS
NEW PTCAR
NUMB 1
PTCDIR X45Y
PX (PARA[1])
END
END
NEW GMSET /GMS
NEW TUBE
PDIAM (PARA[2])
NEW NTUB
PDIAM (PARA[3])
END
END
NEW SCYL
PAXI P1
END
END''').definitions
        parsed = macro_import.parse(macro_export.creation_text(records)).definitions
        self.assertEqual(parsed[1]['elements'][0]['attrs'], {'PDIAM':'(PARA[2])'})
        self.assertEqual(parsed[1]['elements'][0]['children'][0]['attrs'], {'PDIAM':'(PARA[3])'})
        self.assertEqual(parsed[1]['elements'][1]['attrs'], {'PAXI':'P1'})

    def test_public_straight_cylinder_sample(self):
        records = macro_import.parse(SAMPLE.with_name('creation-export-sample.mac').read_text()).definitions
        self.assertEqual([e['attrs']['NUMB'] for e in records[0]['elements']], ['1', '2'])
        self.assertEqual(records[1]['elements'][0]['attrs']['PHEI'], '-200')
        self.assertIn('PDIA 89.1', macro_export.creation_text(records))

    def test_atomic_save_failure_preserves_existing_file_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'test.mac'; path.write_text('original')
            with patch('catalog_studio.macro_export.os.replace', side_effect=OSError('failure')):
                with self.assertRaises(OSError): macro_export.save(path, 'NEW PTSET /X\nEND\n')
            self.assertEqual(path.read_text(), 'original')
            self.assertEqual(list(Path(folder).iterdir()), [path])
            macro_export.save(path, macro_export.creation_text(self.records()))
            text, encoding = macro_import.read_text(path)
            self.assertEqual(path.read_bytes(), text.replace('\r\n', '\n').replace('\n', '\r\n').encode('cp932'))
            self.assertEqual(len(macro_import.parse(text).definitions), 2)

    def test_sjis_japanese_names_descriptions_and_cp932_extensions(self):
        records = self.records()[:1]
        records[0]['name'] = '/接続点サンプル'
        records[0]['attrs']['DESC'] = '日本語の説明①'
        source = macro_export.creation_text(records)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'sample.mac'
            macro_export.save(path, source)
            self.assertEqual(path.read_bytes(), source.replace('\n', '\r\n').encode('cp932'))
            text, encoding = macro_import.read_text(path)
            self.assertEqual(encoding, 'cp932')
            imported = macro_import.parse(text).definitions[0]
            self.assertEqual(imported['name'], records[0]['name'])
            self.assertEqual(imported['attrs']['DESC'], records[0]['attrs']['DESC'])

    def test_unencodable_character_preserves_existing_file_without_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'sample.mac'
            path.write_bytes(b'original')
            with self.assertRaisesRegex(ValueError, 'Shift-JIS.*CP932'):
                macro_export.save(path, "NEW PTSET /TEST\nDESC '説明😀'\nEND\n")
            self.assertEqual(path.read_bytes(), b'original')
            self.assertEqual(list(Path(folder).iterdir()), [path])
            path.unlink()
            with self.assertRaises(ValueError): macro_export.save(path, '😀')
            self.assertFalse(path.exists())
