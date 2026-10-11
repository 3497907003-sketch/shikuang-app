"""Admission/translation failure tests; fixture bytes are not mineral evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from import_reviewed_extension import prepare


class ExtensionImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        key = 'ima-fixture'
        url = 'https://handbookofmineralogy.org/pdfs/Fixture.pdf'
        pdf, image = b'unit-test-only-source', b'unit-test-only-render'
        (self.root / (key + '.pdf')).write_bytes(pdf)
        (self.root / 'view.png').write_bytes(image)
        self.catalog = {'minerals': [{'id': key, 'name_en': 'Fixture', 'formula': 'CaCO3', 'handbook_url': url}], 'physical_stats': {}}
        props = {field: {'value': value, 'raw': value, 'status': 'verified', 'verification': 'Unit fixture', 'source_url': url, 'source_page': 1} for field, value in {'hardness': '3', 'density_measured': '2.7', 'crystal_system': 'Cubic', 'cleavage': 'None', 'luster': 'Vitreous', 'streak': 'White'}.items()}
        props['density_measured']['unit'] = 'g/cm³'
        self.reviewed = {'schema_version': 1, 'reviewed_species_count': 1, 'field_status_counts': {'verified': 6}, 'records': [{'key': key, 'name_en': 'Fixture', 'ima_species': True, 'source_url': url, 'source_pdf_sha256': hashlib.sha256(pdf).hexdigest(), 'properties': props, 'verification': {'reviewed_at': '2026-10-11', 'evidence': {'path': 'view.png', 'sha256': hashlib.sha256(image).hexdigest(), 'actual_image_viewed': True}}}]}
        row = self.reviewed['records'][0]
        row['source_page'] = 1
        row['verification']['evidence']['position'] = 1
        index = {'sheets': [{'path': 'view.png', 'sha256': hashlib.sha256(image).hexdigest(), 'sources': [{field: row[field] for field in ('key', 'source_url', 'source_pdf_sha256', 'source_page')} | {'position': 1, 'crop_points': [0, 0, 100, 100]}]}]}
        index_bytes = json.dumps(index).encode()
        (self.root / 'index.json').write_bytes(index_bytes)
        row['verification']['evidence']['index_sha256'] = hashlib.sha256(index_bytes).hexdigest()
        self.translations = {'schema_version': 1, 'crystal_system': {'Cubic': '等轴晶系'}, 'cleavage': {'None': '无解理'}, 'luster': {'Vitreous': '玻璃光泽'}, 'streak': {'White': '白色'}}

    def call(self):
        return prepare(self.catalog, self.reviewed, self.translations, self.root, self.root)

    def test_exact_identity_and_existing_catalog_preserved(self):
        before = deepcopy(self.catalog)
        out, report = self.call()
        self.assertEqual(before, self.catalog)
        self.assertEqual(out['minerals'][0]['formula'], 'CaCO3')
        self.assertEqual(report['field_status_counts'], {'verified': 6})
        prop = out['minerals'][0]['physical_properties']['luster']
        self.assertEqual(prop['value'], 'Vitreous')
        self.assertEqual(prop['translation'], {'status': 'reviewed', 'source_value': 'Vitreous', 'text_zh': '玻璃光泽'})

    def test_missing_english_translation_blocks_import(self):
        self.reviewed['records'][0]['properties']['luster']['value'] = 'Unreviewed wording'
        with self.assertRaisesRegex(ValueError, 'translation missing'):
            self.call()

    def test_changed_source_and_viewed_bytes_require_new_review(self):
        (self.root / 'ima-fixture.pdf').write_bytes(b'changed-source')
        with self.assertRaisesRegex(ValueError, 'Source PDF changed'):
            self.call()

    def test_exact_ima_identity_not_fuzzy_name_matching(self):
        self.catalog['minerals'][0]['name_en'] = 'Fixture-(Fe)'
        with self.assertRaisesRegex(ValueError, 'exact IMA identity'):
            self.call()

    def test_existing_properties_cannot_be_overwritten(self):
        self.catalog['minerals'][0]['physical_properties'] = {'hardness': {'value': '9'}}
        with self.assertRaisesRegex(ValueError, 'overwritten'):
            self.call()

    def test_unverified_and_calculated_values_are_rejected(self):
        row = self.reviewed['records'][0]
        row['properties']['cleavage']['status'] = 'source_inferred'
        with self.assertRaisesRegex(ValueError, 'must remain null'):
            self.call()
        row['properties']['cleavage']['status'] = 'verified'
        row['properties']['density_measured']['raw'] = 'D(calc.)=2.7'
        with self.assertRaisesRegex(ValueError, 'Calculated density'):
            self.call()

    def test_changed_render_or_outside_evidence_path_is_rejected(self):
        (self.root / 'view.png').write_bytes(b'changed-render')
        with self.assertRaisesRegex(ValueError, 'viewed source evidence'):
            self.call()

    def test_changed_slot_position_and_hash_bound_index_are_rejected(self):
        proof = self.reviewed['records'][0]['verification']['evidence']
        proof['position'] = 999
        with self.assertRaisesRegex(ValueError, 'slot does not match'):
            self.call()
        proof['position'] = 1
        (self.root / 'index.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'index changed'):
            self.call()

    def test_a_valid_viewed_sheet_for_a_different_source_cannot_be_reused(self):
        index = json.loads((self.root / 'index.json').read_text())
        index['sheets'][0]['sources'][0]['key'] = 'ima-different-mineral'
        raw = json.dumps(index).encode(); (self.root / 'index.json').write_bytes(raw)
        self.reviewed['records'][0]['verification']['evidence']['index_sha256'] = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(ValueError, 'exact PDF identity'):
            self.call()
        self.reviewed['records'][0]['verification']['evidence']['path'] = '../outside.png'
        with self.assertRaisesRegex(ValueError, 'viewed source evidence'):
            self.call()


if __name__ == '__main__':
    unittest.main()
