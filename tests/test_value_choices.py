import copy
import unittest
from unittest.mock import patch
from catalog_studio import element_schema as schema, pairing, value_choices


class ValueChoicesTests(unittest.TestCase):
    def setUp(self):
        self.pt = self.definition('points', '/PART-PTSET', 'PTSET')
        self.gm = self.definition('geometry', '/PART-GMSET', 'GMSET')
        self.ngm = self.definition('negative', '/PART-NGMSET', 'NGMSET')
        self.data = {'definitions': [self.pt, self.gm, self.ngm], 'scoms': []}
        self.element = {'id': 'cylinder', 'type': 'SCYL', 'attrs': {}}

    @staticmethod
    def definition(ident, name, kind):
        return {'id': ident, 'name': name, 'kind': kind, 'elements': []}

    def point(self, number, kind='PTAXI', pointset=None):
        pointset = self.pt if pointset is None else pointset
        point = {'id': 'point-' + str(len(pointset['elements'])), 'type': kind, 'attrs': {'NUMB': number}}
        pointset['elements'].append(point)
        return point

    def choices(self, key='PAXI', definition=None, element=None):
        return value_choices.point_choices(self.data, self.gm if definition is None else definition,
                                           self.element if element is None else element, key)

    def test_existing_numbers_are_sorted_without_filling_gaps_or_inventing_defaults(self):
        for number, kind in (('12', 'PTMIX'), ('3', 'PTCAR'), ('7', 'PTPOS')):
            self.point(number, kind)
        self.assertEqual(self.choices(), ('P0', 'P3', 'P7', 'P12'))
        self.pt['elements'].append({'id': 'missing-number', 'type': 'PTAXI', 'attrs': {}})
        self.assertEqual(self.choices(), ('P0', 'P3', 'P7', 'P12'))

    def test_invalid_duplicate_and_nonpoint_numbers_are_not_candidates(self):
        for number in ('0', '-1', '2.5', 'bad', '', True, None, '4', '04', '9'):
            self.point(number)
        self.point('8', 'SBOX')
        self.assertEqual(self.choices(), ('P0', 'P9'))

    def test_current_point_is_excluded_after_duplicate_detection(self):
        current = self.point('1')
        self.point('3')
        self.assertEqual(self.choices(definition=self.pt, element=current), ('P0', 'P3'))
        self.point('1')
        self.assertEqual(self.choices(definition=self.pt, element=current), ('P0', 'P3'))

    def test_only_point_reference_attributes_have_candidates(self):
        self.point('2')
        for key in ('PAXI', 'PAAX', 'PBAX', 'PCAX', 'PTCDIR', 'PTCD'):
            with self.subTest(key=key):
                self.assertEqual(self.choices(key), ('P0', 'P2'))
        for key in ('PLAXI', 'PDIS', 'PDIA', 'PBDI', 'PTDI', 'PX', 'PTCPOS', 'PTSPOS', 'PTEPOS', 'DESC', 'PTS'):
            with self.subTest(key=key):
                self.assertIsNone(self.choices(key))
        line = {'id': 'line', 'type': 'LINE', 'attrs': {}}
        self.assertEqual(self.choices('PTS', element=line), ('P0', 'P2'))
        with patch.dict(schema.NEGATIVE_BASE, {'TEST_NEGATIVE_LINE': 'LINE'}):
            line['type'] = 'TEST_NEGATIVE_LINE'
            self.assertEqual(self.choices('PTS', element=line), ('P0', 'P2'))

    def test_ambiguous_or_unset_geometry_pairing_offers_only_origin(self):
        self.point('2')
        other = self.definition('other', '/PART-PTSET', 'PTSET')
        self.data['definitions'].append(other)
        self.point('7', pointset=other)
        self.assertEqual(self.choices(), ('P0',))
        pairing.assign(self.data, self.gm, other['id'])
        self.assertEqual(self.choices(), ('P0', 'P7'))
        pairing.assign(self.data, self.gm, '')
        self.assertEqual(self.choices(), ('P0',))

    def test_conflicting_component_links_are_not_resolved_arbitrarily(self):
        self.point('2')
        self.data['scoms'] = [{'gmset_id': self.gm['id'], 'ptset_id': self.pt['id']},
                              {'gmset_id': self.gm['id'], 'ptset_id': 'missing'}]
        self.assertEqual(self.choices(), ('P0',))

    def test_negative_set_requires_unique_explicit_component_pointset(self):
        self.point('2')
        self.assertEqual(self.choices(definition=self.ngm), ('P0',))
        self.data['scoms'] = [{'ngmset_id': self.ngm['id'], 'ptset_id': self.pt['id']},
                              {'ngmset_id': self.ngm['id'], 'ptset_id': self.pt['id']}]
        self.assertEqual(self.choices(definition=self.ngm), ('P0', 'P2'))
        self.data['scoms'].append({'ngmset_id': self.ngm['id'], 'ptset_id': 'missing'})
        self.assertEqual(self.choices(definition=self.ngm), ('P0',))
        self.data['scoms'] = [{'ngmset_id': self.ngm['id'], 'ptset_id': 'missing'}]
        self.assertEqual(self.choices(definition=self.ngm), ('P0',))

    def test_unknown_set_has_no_point_selector_and_queries_do_not_mutate_data(self):
        self.point('4')
        before = copy.deepcopy(self.data)
        for definition in self.data['definitions']:
            self.choices(definition=definition)
        for kind in ('PTSSET', 'GMSSET', 'OTHER'):
            self.assertIsNone(self.choices(definition=self.definition('unknown', '/UNKNOWN', kind)))
        self.assertIsNone(value_choices.point_choices(self.data, None, self.element, 'PAXI'))
        self.assertIsNone(value_choices.point_choices(self.data, self.pt, None, 'PAXI'))
        self.assertEqual(self.data, before)


if __name__ == '__main__':
    unittest.main()
