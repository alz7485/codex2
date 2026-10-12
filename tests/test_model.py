import copy
import tempfile
import unittest
from pathlib import Path
from catalog_studio import model

class ModelTests(unittest.TestCase):
    def setUp(self): self.data = model.sample()
    def test_arithmetic(self):
        for expr, expected in [('全長 / 2',60), ('(P1 - P2) * 2 + 5',105), ('-P3 / 2',-60), ('全長+大径側外径',220)]:
            self.assertEqual(model.evaluate(expr, self.data['parameters']), expected)
    def test_invalid_and_executable_expressions(self):
        for expr in ['P3 / 0', 'unknown', '(P1', 'P1 ** 2', '__import__("os")', 'P1.real', '[P1]', 'True', '1e309']:
            with self.subTest(expr=expr), self.assertRaises(ValueError): model.evaluate(expr, self.data['parameters'])
    def test_rename_preserves_references(self):
        model.rename_parameter(self.data, 'P1', '外径')
        self.assertEqual(self.data['elements'][0]['attrs']['大径'], '外径')
        self.assertEqual(model.evaluate('外径 / 2',self.data['parameters']),50)
        with self.assertRaises(ValueError): model.rename_parameter(self.data, 'P1', '全長')
    def test_duplicate_is_independent(self):
        original=self.data['elements'][0]; new=model.duplicate_element(self.data, original)
        new['attrs']['大径']='20'
        self.assertNotEqual(new['id'],original['id']); self.assertEqual(original['attrs']['大径'],'大径側外径')
    def test_all_element_types_and_checks(self):
        for kind in model.SCHEMAS: model.add_element(self.data,kind)
        self.assertEqual(model.issues(self.data),[])
        self.data['elements'][0]['attrs']['長さ']='-1'
        self.assertTrue(any('正の値' in issue for issue in model.issues(self.data)))
    def test_roundtrip_and_bad_import(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'project.json';model.save(self.data,p)
            self.assertEqual(model.load(p),self.data)
            p.write_text('{"format":"bad"}')
            with self.assertRaises(ValueError):model.load(p)
    def test_duplicate_parameter_rejected(self):
        bad=copy.deepcopy(self.data);bad['parameters'].append(copy.deepcopy(bad['parameters'][0]))
        with self.assertRaises(ValueError):model.validate(bad)
    def test_macro_is_only_comments(self):
        self.assertTrue(all(not line or line.startswith('$*') for line in model.macro_text(self.data).splitlines()))

if __name__=='__main__':unittest.main()
