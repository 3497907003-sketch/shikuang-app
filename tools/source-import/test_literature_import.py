"""Unit-only publication guards; fictional fixture text is not mineral evidence."""
import copy
import unittest

from import_reviewed_literature import (BEGIN, END, approved_properties, bundle_script,
                                       manifest_for, prepare_catalog)


class LiteraturePublicationTests(unittest.TestCase):
    def test_independent_variable_preserves_inference_knowledge_and_annotations(self):
        prefix = 'window.MINERAL_KB={"unit_test_only":{}};\nwindow.MINERAL_CRYSTAL_SYSTEM_ANNOTATIONS={};\n'
        bundle = {'schema_version': 1, 'count': 0, 'by_species': {}}
        result = bundle_script(prefix, bundle)
        self.assertTrue(result.startswith(prefix))
        self.assertEqual(result.count('MINERAL_KB='), 1)
        self.assertEqual(result.count(BEGIN), 1)
        self.assertEqual(bundle_script(result, bundle), result)

    def test_ambiguous_block_rejected(self):
        for source in (BEGIN, END, BEGIN + END + BEGIN + END):
            with self.assertRaises(ValueError):
                bundle_script(source, {})

    def test_manifest_preserves_three_file_lazy_loading_contract(self):
        manifest = {'counts': {'existing': 123}, 'files': [{'path': 'data/catalog.json'}, {'path': 'data/crystals.json'}, {'path': 'data/image-sources.json'}]}
        original = copy.deepcopy(manifest)
        result = manifest_for(manifest, b'unit fixture catalog', b'unit fixture js',
                              {'catalog_species_with_literature_facts': 0, 'verified_literature_fields': 0, 'root_ledger_sha256': 'f' * 64})
        self.assertEqual(len(result['files']), 3)
        self.assertEqual(result['files'][1:], original['files'][1:])
        self.assertEqual(result['counts']['existing'], 123)
        self.assertEqual(result['literature_bundle']['path'], 'data/minerals.js')
        self.assertEqual(manifest, original)

    def test_duplicate_catalog_manifest_row_rejected(self):
        manifest = {'counts': {}, 'files': [{'path': 'data/catalog.json'}, {'path': 'data/catalog.json'}, {'path': 'data/image-sources.json'}]}
        with self.assertRaises(ValueError):
            manifest_for(manifest, b'x', b'y', {})

    def test_test_fixture_and_autoapproval_cannot_be_published(self):
        for staged in ({'unit_fixture': True, 'automatically_approved': False}, {'unit_fixture': False, 'automatically_approved': True}):
            with self.assertRaises(ValueError):
                approved_properties({}, staged, {})

    def test_unaccounted_existing_literature_is_not_silently_overwritten(self):
        # Empty fixture batch may not overwrite an unrelated already stored row.
        catalog = {'minerals': [{'id': 'ima-unit-fixture-only', 'literature_properties': {'occurrence': {'status': 'needs_review', 'value_zh': None}}}]}
        inputs = {'fields': {}, 'proposal_sha256': 'a' * 64, 'render_index_sha256': 'b' * 64, 'physical_decision_sha256': 'c' * 64}
        staged = {'unit_fixture': False, 'automatically_approved': False, 'records': [], 'withheld': [], 'root_ledger_sha256': 'd' * 64}
        with self.assertRaisesRegex(ValueError, 'Unaccounted'):
            prepare_catalog(catalog, inputs, staged, {'decisions': []})


if __name__ == '__main__':
    unittest.main()
