"""Unit-only publication guards; fictional fixture text is not mineral evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from import_reviewed_literature import (BEGIN, END, approved_properties, bundle_script,
                                       manifest_for, prepare_catalog, canonical_sha, load_additional_batches,
                                       load_validated_batch, BATCH_CONFIG_SCHEMA)


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


def fictional_batch(number, key=None):
    """In-memory fixture only; no actual mineral/source approval is implied."""
    key = key or 'ima-unit-fictional-' + str(number)
    pin = lambda field: hashlib.sha256((str(number) + ':' + field).encode()).hexdigest()
    entity = {'id': key, 'name_en': 'Fictional fixture ' + key, 'ima_number': 'unit-only'}
    inputs = {'fields': {(key, field): {'entity': entity} for field in ('occurrence', 'distribution')},
              'proposal_sha256': pin('proposal'), 'render_index_sha256': pin('index'),
              'physical_decision_sha256': pin('physical')}
    props = {field: {'status': 'verified', 'value_zh': '仅用于软件测试的虚构字段' + field,
                     'root_ledger_sha256': pin('ledger'), 'render_index_sha256': pin('index')}
             for field in ('occurrence', 'distribution')}
    staged = {'unit_fixture': False, 'automatically_approved': False,
              'records': [{'id': key, 'literature_properties': props}], 'withheld': [],
              'root_ledger_sha256': pin('ledger'), 'counts': {'approved_fields': 2, 'withheld_fields': 0}}
    return inputs, staged, {'decisions': []}


def fixture_catalog(*batches):
    return {'count': len(batches), 'minerals': [copy.deepcopy(next(iter(batch[0]['fields'].values()))['entity'])
                                              for batch in batches], 'unrelated': {'must': 'remain'}}


class LiteratureBatchOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.old, self.new = fictional_batch(1), fictional_batch(2)
        self.empty = fixture_catalog(self.old, self.new)
        self.legacy, self.legacy_bundle = prepare_catalog(self.empty, *self.old)

    def test_append_preserves_legacy_values_and_source_pins(self):
        before = copy.deepcopy(self.legacy)
        merged, bundle = prepare_catalog(self.legacy, *self.old, additional_batches=[self.new])
        self.assertEqual(self.legacy, before)
        self.assertEqual(merged['minerals'][0], before['minerals'][0])
        self.assertEqual(merged['unrelated'], before['unrelated'])
        stats = merged['literature_stats']
        self.assertEqual(stats['catalog_species_with_literature_facts'], 2)
        self.assertEqual(stats['verified_literature_fields'], 4)
        self.assertEqual(stats['root_ledger_sha256'], before['literature_stats']['root_ledger_sha256'])
        self.assertEqual(stats['source_json_sha256'], before['literature_stats']['source_json_sha256'])
        self.assertEqual(stats['source_batch_registry_sha256'], canonical_sha(stats['source_batches']))
        self.assertEqual(len(stats['source_batches']), 2)
        self.assertEqual(set(bundle['by_species']), {row['id'] for row in merged['minerals']})
        self.assertEqual(bundle['counts'], stats)

    def test_same_batch_is_idempotent_without_double_counting(self):
        one, bundle = prepare_catalog(self.legacy, *self.old, additional_batches=[self.old])
        self.assertEqual(one, self.legacy)
        self.assertEqual(bundle, self.legacy_bundle)
        merged, first_bundle = prepare_catalog(self.legacy, *self.old, additional_batches=[self.new])
        again, again_bundle = prepare_catalog(merged, *self.old, additional_batches=[self.new, self.old, self.new])
        self.assertEqual(again, merged)
        self.assertEqual(again_bundle, first_bundle)

    def test_input_order_cannot_replace_legacy_anchor_pins(self):
        expected, expected_bundle = prepare_catalog(self.legacy, *self.old, additional_batches=[self.new])
        reversed_input, reversed_bundle = prepare_catalog(self.legacy, *self.new, additional_batches=[self.old])
        self.assertEqual(reversed_input, expected)
        self.assertEqual(bundle_script('window.MINERAL_KB={};', reversed_bundle),
                         bundle_script('window.MINERAL_KB={};', expected_bundle))

    def test_missing_historical_batch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unaccounted'):
            prepare_catalog(self.legacy, *self.new)
        merged, _ = prepare_catalog(self.legacy, *self.old, additional_batches=[self.new])
        with self.assertRaisesRegex(ValueError, 'Unaccounted'):
            prepare_catalog(merged, *self.old)

    def test_existing_field_and_counter_tampering_rejected(self):
        for mutate in ('value', 'count', 'owner', 'remove_stats'):
            changed = copy.deepcopy(self.legacy)
            if mutate == 'value':
                changed['minerals'][0]['literature_properties']['occurrence']['value_zh'] = '篡改'
            elif mutate == 'count':
                changed['literature_stats']['verified_literature_fields'] = 123
            elif mutate == 'owner':
                changed['literature_stats']['root_ledger_sha256'] = 'f' * 64
            else:
                del changed['literature_stats']
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                prepare_catalog(changed, *self.old, additional_batches=[self.new])

    def test_same_ledger_different_material_is_rejected(self):
        other = copy.deepcopy(self.new)
        other[1]['root_ledger_sha256'] = self.old[1]['root_ledger_sha256']
        for prop in other[1]['records'][0]['literature_properties'].values():
            prop['root_ledger_sha256'] = self.old[1]['root_ledger_sha256']
        with self.assertRaisesRegex(ValueError, 'Same Root ledger'):
            prepare_catalog(self.legacy, *self.old, additional_batches=[other])

    def test_different_batches_cannot_claim_the_same_species(self):
        shared_key = self.legacy['minerals'][0]['id']
        other = fictional_batch(3, key=shared_key)
        with self.assertRaisesRegex(ValueError, 'Overlapping species'):
            prepare_catalog(self.legacy, *self.old, additional_batches=[other])

    def test_registered_batch_species_or_statistics_tampering_rejected(self):
        merged, _ = prepare_catalog(self.legacy, *self.old, additional_batches=[self.new])
        for mutate in ('count', 'species', 'hash', 'missing_declaration'):
            changed = copy.deepcopy(merged)
            registry = changed['literature_stats']['source_batches']
            if mutate == 'count':
                registry[1]['verified_literature_fields'] = 999
            elif mutate == 'species':
                registry[1]['species_ids'] = ['ima-unowned-fictional']
            elif mutate == 'missing_declaration':
                registry.pop()
            if mutate != 'hash':
                changed['literature_stats']['source_batch_registry_sha256'] = canonical_sha(registry)
            else:
                changed['literature_stats']['source_batch_registry_sha256'] = 'f' * 64
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                prepare_catalog(changed, *self.old, additional_batches=[self.new])

    def test_empty_unowned_statistics_rejected(self):
        changed = copy.deepcopy(self.empty)
        changed['literature_stats'] = copy.deepcopy(self.legacy['literature_stats'])
        with self.assertRaisesRegex(ValueError, 'without owned'):
            prepare_catalog(changed, *self.old)

    def test_multibatch_manifest_binds_every_ledger_and_aggregate_registry(self):
        merged, _ = prepare_catalog(self.legacy, *self.old, additional_batches=[self.new])
        manifest = {'counts': {'untouched': 7}, 'files': [{'path': 'data/catalog.json'}, {'path': 'data/crystals.json'}, {'path': 'data/image-sources.json'}]}
        published = manifest_for(manifest, b'fictional catalog', b'fictional js', merged['literature_stats'])
        self.assertEqual(published['literature_bundle']['root_ledger_sha256s'], [self.old[1]['root_ledger_sha256'], self.new[1]['root_ledger_sha256']])
        self.assertEqual(published['literature_bundle']['source_batch_registry_sha256'], merged['literature_stats']['source_batch_registry_sha256'])
        self.assertEqual(published['counts']['verified_literature_fields'], 4)
        self.assertEqual(published['files'][1:], manifest['files'][1:])


class LiteratureAdditionalSourceLoadingTests(unittest.TestCase):
    def config(self, root):
        spec = {name: name + '-unit-only.json' for name in ('proposal', 'index', 'physical', 'pdf_dir', 'evidence_root', 'ledger')}
        spec['trusted_ledger_sha256'] = 'a' * 64
        data = {'schema': BATCH_CONFIG_SCHEMA, 'batches': [spec, dict(spec, proposal='second-proposal-unit-only.json')]}
        path = root / 'additional.json'
        path.write_text(json.dumps(data))
        return path, hashlib.sha256(path.read_bytes()).hexdigest(), data

    def test_every_additional_source_spec_is_revalidated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, digest, _ = self.config(root)
            with patch('import_reviewed_literature.load_validated_batch', side_effect=[fictional_batch(1), fictional_batch(2)]) as load:
                batches = load_additional_batches(config, digest, root / 'catalog.json')
            self.assertEqual(len(batches), 2)
            self.assertEqual(load.call_count, 2)
            self.assertEqual(load.call_args_list[0].args[0]['proposal'], (root / 'proposal-unit-only.json').resolve())
            self.assertEqual(load.call_args_list[1].args[0]['proposal'], (root / 'second-proposal-unit-only.json').resolve())
            self.assertEqual(load.call_args_list[1].args[0]['trusted_ledger_sha256'], 'a' * 64)

    def test_untrusted_changed_missing_or_unknown_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, digest, data = self.config(root)
            for path, token in ((config, None), (None, digest), (config, 'f' * 64)):
                with self.subTest(path=path, token=token), self.assertRaises(ValueError):
                    load_additional_batches(path, token, root / 'catalog.json')
            data['batches'][1]['ignore_old_batch'] = True
            config.write_text(json.dumps(data))
            digest = hashlib.sha256(config.read_bytes()).hexdigest()
            with patch('import_reviewed_literature.load_validated_batch', return_value=fictional_batch(1)):
                with self.assertRaisesRegex(ValueError, 'Unknown/missing'):
                    load_additional_batches(config, digest, root / 'catalog.json')

    def test_batch_loader_calls_actual_source_validator_and_root_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / 'ledger.json'; ledger.write_text('{"decisions": []}')
            spec = {name: root / name for name in ('proposal', 'index', 'physical', 'pdf_dir', 'evidence_root')}
            digest = hashlib.sha256(ledger.read_bytes()).hexdigest()
            spec.update(ledger=ledger, trusted_ledger_sha256=digest)
            with patch('import_reviewed_literature.validate_inputs', return_value={'unit': 'fictional'}) as validate, patch('import_reviewed_literature.stage_import', return_value={'unit': 'staged'}) as stage:
                inputs, staged, parsed = load_validated_batch(spec, root / 'catalog.json')
            validate.assert_called_once_with(spec['proposal'], spec['index'], spec['physical'], root / 'catalog.json', spec['pdf_dir'], spec['evidence_root'])
            stage.assert_called_once_with(inputs, ledger, digest)
            self.assertEqual(parsed, {'decisions': []})

    def test_readonly_audit_requires_every_declared_batch(self):
        from validate_sources import audit_literature_batches
        old, new = fictional_batch(1), fictional_batch(2)
        catalog, _ = prepare_catalog(fixture_catalog(old, new), *old, additional_batches=[new])
        with patch('validate_sources.load_validated_batch', return_value=old), patch('validate_sources.load_additional_batches', return_value=[new, new]):
            expected, bundle, review = audit_literature_batches(catalog, Path('unit-only.json'), {})
        self.assertEqual(expected, catalog)
        self.assertEqual(bundle['count'], 2)
        self.assertEqual(review['approved_fields'], 4)
        self.assertTrue(review['all_declared_batches_revalidated'])
        with patch('validate_sources.load_validated_batch', return_value=old), patch('validate_sources.load_additional_batches', return_value=[]):
            with self.assertRaisesRegex(ValueError, 'Unaccounted'):
                audit_literature_batches(catalog, Path('unit-only.json'), {})


if __name__ == '__main__':
    unittest.main()
