import copy
import tempfile
import unittest
from pathlib import Path

from catalog_studio import model, project


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.data = project.sample()

    def test_numbers_only_belong_to_scom(self):
        self.assertEqual(project.issues(self.data), [])
        self.assertTrue(all('value' not in p for p in self.data['parameters']))
        params = project.parameters_for(self.data, self.data['scoms'][0])
        self.assertEqual(model.evaluate('全長 / 2', params), 44.5)
        self.assertEqual(self.data['definitions'][0]['elements'][0]['attrs']['長さ'], '全長')
        self.data['parameters'][0]['value'] = 42
        with self.assertRaises(ValueError):
            project.validate(self.data)

    def test_shared_definitions_evaluate_per_scom(self):
        definition = self.data['definitions'][0]
        attrs = copy.deepcopy(definition['elements'][0]['attrs'])
        lengths = [model.evaluate(attrs['長さ'], project.parameters_for(self.data, scom))
                   for scom in self.data['scoms']]
        self.assertEqual(lengths, [89, 89, 102])
        self.data['scoms'][0]['values']['P3'] = 140
        self.assertEqual(model.evaluate(attrs['長さ'], project.parameters_for(self.data, self.data['scoms'][0])), 140)
        self.assertEqual(definition['elements'][0]['attrs'], attrs)
        self.assertEqual(self.data['scoms'][1]['values']['P3'], 89)

    def test_roundtrip_preserves_metadata_and_unknown_elements(self):
        self.data['vendor_metadata'] = {'source': '既存カタログ'}
        self.data['definitions'][0]['elements'].append(
            {'id': 'unknown', 'type': 'future-primitive', 'name': '原文', 'attrs': {'RAW': '特殊構文'}, 'extra': [1, 2]})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'catalog.json'
            project.save(self.data, path)
            loaded = project.load(path)
        self.assertEqual(loaded, self.data)
        self.assertTrue(any('未対応の要素型' in issue for issue in project.issues(loaded)))

    def test_v1_migration_preserves_expressions_and_moves_numbers(self):
        legacy = model.sample()
        legacy['source_note'] = '旧ファイルのメモ'
        migrated = project.migrate(legacy)
        self.assertEqual(migrated['source_note'], legacy['source_note'])
        self.assertEqual(migrated['scoms'][0]['values'], {'P1': 100, 'P2': 50, 'P3': 120})
        elements = [e for d in migrated['definitions'] for e in d['elements']]
        self.assertEqual(elements, legacy['elements'])
        self.assertTrue(all('value' not in p for p in migrated['parameters']))
        self.assertEqual(project.issues(migrated), [])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'legacy.json'
            model.save(legacy, path)
            self.assertEqual(project.load(path)['version'], 2)

    def test_missing_values_are_reported_not_filled(self):
        self.data['scoms'][0]['values'].pop('P3')
        with self.assertRaises(ValueError):
            project.parameters_for(self.data, self.data['scoms'][0])
        messages = project.issues(self.data)
        self.assertTrue(any('P3 全長の実数値がありません' in message for message in messages))
        self.assertNotIn('P3', self.data['scoms'][0]['values'])

    def test_references_duplicates_and_invalid_expressions(self):
        self.data['scoms'][0]['gmset_id'] = self.data['definitions'][1]['id']
        self.data['scoms'][1]['cate_id'] = 'missing'
        self.data['specs'][0]['entries'][0]['scom_id'] = 'missing'
        self.data['scoms'][1]['name'] = self.data['scoms'][2]['name'].lower()
        self.data['definitions'][0]['elements'][0]['attrs']['大径'] = 'unknown + 1'
        messages = project.issues(self.data)
        for text in ['GMSETの参照先', '所属 CATE', '選択行の SCOM', '名前が重複', '未定義のパラメータ']:
            self.assertTrue(any(text in message for message in messages), text)

    def test_each_scom_and_orphan_definition_get_expression_checks(self):
        self.data['definitions'][0]['elements'][0]['attrs']['長さ'] = '全長 / (P1 - P2)'
        self.data['scoms'][1]['values']['P1'] = self.data['scoms'][1]['values']['P2']
        self.assertTrue(any('/REDUCER-80X50' in issue and 'ゼロで除算' in issue for issue in project.issues(self.data)))
        orphan = project.add_definition(self.data)
        orphan['elements'][0]['attrs']['長さ'] = '__import__("os")'
        self.assertTrue(any(orphan['name'] in issue and '四則演算' in issue for issue in project.issues(self.data)))

    def test_add_and_duplicate_keep_numerical_data_independent(self):
        cate = project.add_cate(self.data)
        scom = project.add_scom(self.data, cate['id'])
        self.assertEqual(scom['values'], {})
        self.assertEqual(scom['cate_id'], cate['id'])
        original = self.data['scoms'][0]
        duplicated = project.duplicate_scom(self.data, original)
        duplicated['values']['P1'] = 999
        self.assertEqual(original['values']['P1'], 76.3)
        self.assertNotEqual(original['id'], duplicated['id'])
        self.assertEqual(original['gmset_id'], duplicated['gmset_id'])
        spec = project.add_spec(self.data)
        entry = project.add_spec_entry(self.data, spec, original['id'])
        self.assertEqual(entry['scom_id'], original['id'])
        self.assertEqual(entry['bore1'], '65')

    def test_default_definitions_use_reference_expressions(self):
        for kind in ('GMSET', 'PTSET'):
            definition = project.add_definition(self.data, kind)
            for element in definition['elements']:
                for attr, expr in element['attrs'].items():
                    if attr not in ('位置', '方向'):
                        self.assertIn(expr, [p['role'] for p in self.data['parameters']])
        with self.assertRaises(ValueError):
            project.add_element(self.data, self.data['definitions'][0], 'point')

    def test_spec_bores_follow_roles_not_parameter_number(self):
        self.data['parameters'][3]['role'] = '別の寸法'
        self.data['parameters'].append({'id': 'P9', 'role': '大径側呼び径', 'unit': 'mm'})
        self.data['scoms'][0]['values']['P9'] = 125
        entry = project.add_spec_entry(self.data, self.data['specs'][0], self.data['scoms'][0]['id'])
        self.assertEqual(entry['bore1'], '125')

    def test_role_rename_does_not_rewrite_direction_tokens(self):
        self.data['parameters'][0]['role'] = 'Z'
        self.data['definitions'][0]['elements'][0]['attrs']['大径'] = 'Z'
        project.rename_parameter(self.data, 'P1', '外径')
        element = self.data['definitions'][0]['elements'][0]
        self.assertEqual(element['attrs']['大径'], '外径')
        self.assertEqual(element['attrs']['方向'], 'Z')

    def test_role_rename_preserves_parameter_numbers_and_book_snapshot(self):
        snapshot = copy.deepcopy(self.data)
        self.data['books'].append({'name': '発行済み', 'snapshot': snapshot})
        values = copy.deepcopy(self.data['scoms'][0]['values'])
        project.rename_parameter(self.data, 'P1', '外径')
        self.assertEqual(self.data['definitions'][0]['elements'][0]['attrs']['大径'], '外径')
        self.assertEqual(self.data['scoms'][0]['values'], values)
        self.assertEqual(self.data['books'][0]['snapshot']['parameters'][0]['role'], '大径側外径')
        with self.assertRaises(ValueError):
            project.rename_parameter(self.data, 'P2', '全長')

    def test_comments_report_cannot_emit_commands_from_multiline_names(self):
        self.data['name'] = 'カタログ\nNEW SCOM /UNEXPECTED'
        self.data['definitions'][0]['elements'][0]['attrs']['長さ'] = '全長\nDELETE ALL'
        self.assertTrue(all(line.startswith('$*') for line in project.macro_text(self.data).splitlines()))

    def test_bad_numerical_values_and_identifiers_rejected(self):
        for value in (float('nan'), float('inf'), True, '100', 10 ** 1000):
            bad = copy.deepcopy(self.data)
            bad['scoms'][0]['values']['P1'] = value
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                project.validate(bad)
        self.data['specs'][0]['entries'].append(copy.deepcopy(self.data['specs'][0]['entries'][0]))
        with self.assertRaises(ValueError):
            project.validate(self.data)


if __name__ == '__main__':
    unittest.main()

class BookStorageTests(unittest.TestCase):
    def test_bad_or_duplicate_snapshot_is_rejected(self):
        from catalog_studio.booklet import snapshot
        data=project.sample()
        data['books']=[{'id':'broken','created_at':123}]
        with self.assertRaises(ValueError):project.validate(data)
        book=snapshot(project.sample())
        data['books']=[book,copy.deepcopy(book)]
        with self.assertRaises(ValueError):project.validate(data)
    def test_snapshot_validation_is_independent_of_live_records(self):
        from catalog_studio.booklet import snapshot
        data=project.sample();data['books']=[snapshot(data)]
        for key in ('cates','definitions','scoms','specs'):data[key]=[]
        self.assertEqual(project.validate(data),data)
