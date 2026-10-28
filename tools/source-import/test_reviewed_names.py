import unittest
from copy import deepcopy
from import_reviewed_names import prepare


class ReviewedNamesTest(unittest.TestCase):
    def setUp(self):
        self.catalog = {'minerals': [{'id': 'ima-one', 'name_en': 'One'}, {'id': 'ima-two', 'name_en': 'Two'}]}
        self.first = {'catalog_id': 'ima-one', 'name_en': 'One', 'name_zh': '甲矿', 'status': 'reviewed',
                      'source_url': 'https://example.org/paper1', 'source_title': '中英文原文',
                      'source_doi': '10.1/one', 'evidence_locator': '关键词'}
        self.second = dict(self.first, catalog_id='ima-two', name_en='Two', name_zh='乙矿', source_url='https://example.org/paper2')

    def reviewed(self, records):
        return {'schema_version': 1, 'source_review': {'reviewer': 'root', 'actual_source_pages_read': True}, 'records': records}

    def test_addition_preserves_all_old_names_and_official_rows(self):
        first = prepare(self.catalog, self.reviewed([self.first]))
        result = prepare(first, self.reviewed([self.first, self.second]))
        self.assertEqual(result['minerals'], self.catalog['minerals'])
        self.assertEqual(result['reviewed_names_zh']['records'], [self.first, self.second])
        self.assertEqual(first['reviewed_names_zh']['records'], [self.first])

    def test_removal_and_provenance_change_remain_blocked(self):
        previous = prepare(self.catalog, self.reviewed([self.first]))
        for records in ([self.second], [dict(self.first, source_url='https://example.org/changed'), self.second]):
            with self.subTest(records=records), self.assertRaises(ValueError):
                prepare(previous, self.reviewed(records))

    def test_unreviewed_and_identity_mismatch_remain_blocked(self):
        for record in (dict(self.first, status='needs_review'), dict(self.first, name_en='Wrong')):
            with self.subTest(record=record), self.assertRaises(ValueError):
                prepare(self.catalog, self.reviewed([record]))


if __name__ == '__main__':
    unittest.main()
