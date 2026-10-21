"""Two-root source audits with fictional bytes; not mineral evidence/approval."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from import_reviewed_extension import prepare
from validate_sources import audit_extension_sources, EXTENSION_CONFIG_SCHEMA


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ExtensionSourceRootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.catalog = {'minerals': [], 'physical_stats': {'extension_batches': []}}
        self.paths, self.specs, self.reviewed, self.translations = [], {}, [], []
        for number, crystal, chinese in ((1, 'Cubic', '等轴晶系'), (2, 'Monoclinic', '单斜晶系')):
            directory = self.root / str(number)
            pdf_dir, view_dir = directory / 'pdf', directory / 'evidence'
            pdf_dir.mkdir(parents=True); view_dir.mkdir()
            key = 'ima-fictional-unit-' + str(number)
            url = 'https://handbookofmineralogy.org/pdfs/FictionalUnit' + str(number) + '.pdf'
            pdf, view = pdf_dir / (key + '.pdf'), view_dir / 'view.png'
            pdf.write_bytes(('Fictional unit source ' + str(number)).encode())
            view.write_bytes(('Fictional unit render ' + str(number)).encode())
            values = {'hardness': str(number + 1), 'density_measured': str(number + 2) + '.1',
                      'crystal_system': crystal, 'cleavage': 'None', 'luster': 'Vitreous', 'streak': 'White'}
            props = {field: {'value': value, 'raw': value, 'status': 'verified', 'verification': 'Fictional software fixture only',
                             'source_url': url, 'source_page': 1} for field, value in values.items()}
            props['density_measured']['unit'] = 'g/cm³'
            row = {'key': key, 'name_en': 'Fictional Unit ' + str(number), 'ima_species': True,
                   'source_url': url, 'source_pdf_sha256': sha(pdf), 'source_page': 1, 'properties': props,
                   'verification': {'reviewed_at': 'unit-only', 'evidence': {'path': 'view.png', 'sha256': sha(view),
                       'actual_image_viewed': True, 'position': 1}}}
            index = {'sheets': [{'path': view.name, 'sha256': sha(view), 'sources': [{field: row[field] for field in
                ('key', 'source_url', 'source_pdf_sha256', 'source_page')} | {'position': 1, 'crop_points': [0, 0, 100, 100]}]}]}
            (view_dir / 'index.json').write_text(json.dumps(index))
            row['verification']['evidence']['index_sha256'] = sha(view_dir / 'index.json')
            reviewed = {'schema_version': 1, 'reviewed_species_count': 1, 'field_status_counts': {'verified': 6}, 'records': [row]}
            translations = {'schema_version': 1, 'crystal_system': {crystal: chinese}, 'cleavage': {'None': '无解理'},
                            'luster': {'Vitreous': '玻璃光泽'}, 'streak': {'White': '白色'}}
            reviewed_path, translation_path = directory / 'reviewed.json', directory / 'translations.json'
            reviewed_path.write_text(json.dumps(reviewed)); translation_path.write_text(json.dumps(translations))
            self.paths.append(reviewed_path); self.reviewed.append(reviewed); self.translations.append(translations)
            self.specs[sha(reviewed_path)] = {'pdf_dir': str(pdf_dir.relative_to(self.root)),
                'evidence_root': str(view_dir.relative_to(self.root)), 'translations': str(translation_path.relative_to(self.root))}
            self.catalog['minerals'].append({'id': key, 'name_en': row['name_en'], 'handbook_url': url, 'formula': 'unit-only'})
        for path, reviewed, translations in zip(self.paths, self.reviewed, self.translations):
            spec = self.specs[sha(path)]
            self.catalog, proof = prepare(self.catalog, reviewed, translations,
                                          self.root / spec['pdf_dir'], self.root / spec['evidence_root'])
            self.catalog['physical_stats']['extension_batches'].append({**proof, 'source_json_sha256': sha(path),
                'translations_sha256': sha(self.root / spec['translations']), 'training_or_accuracy_claim': False})
        self.config = self.root / 'source-map.json'
        self.data = {'schema': EXTENSION_CONFIG_SCHEMA, 'batches': self.specs}
        self.write_config()

    def write_config(self):
        self.config.write_text(json.dumps(self.data))
        self.config_sha = sha(self.config)

    def call(self, catalog=None, paths=None, **kwargs):
        return audit_extension_sources(catalog or self.catalog, self.paths if paths is None else paths,
            self.root / 'unused-global-translations.json', config_path=self.config,
            trusted_config_sha256=self.config_sha, **kwargs)

    def test_two_distinct_roots_and_translation_files_are_actually_prepared(self):
        before = deepcopy(self.catalog)
        with patch('validate_sources.prepare_extension', wraps=prepare) as execute:
            proofs, keys = self.call()
        self.assertEqual(execute.call_count, 2)
        self.assertNotEqual(execute.call_args_list[0].args[3], execute.call_args_list[1].args[3])
        self.assertNotEqual(execute.call_args_list[0].args[4], execute.call_args_list[1].args[4])
        self.assertEqual(execute.call_args_list[0].args[2]['crystal_system'], {'Cubic': '等轴晶系'})
        self.assertEqual(execute.call_args_list[1].args[2]['crystal_system'], {'Monoclinic': '单斜晶系'})
        self.assertEqual(len(proofs), 2); self.assertEqual(len(keys), 2)
        self.assertEqual(self.catalog, before)

    def test_legacy_single_global_root_remains_supported(self):
        catalog = deepcopy(self.catalog)
        catalog['physical_stats']['extension_batches'] = catalog['physical_stats']['extension_batches'][:1]
        catalog['minerals'] = catalog['minerals'][:1]
        spec = self.specs[sha(self.paths[0])]
        proofs, keys = audit_extension_sources(catalog, self.paths[:1], self.root / spec['translations'],
                                               self.root / spec['pdf_dir'], self.root / spec['evidence_root'])
        self.assertEqual(len(proofs), 1); self.assertEqual(len(keys), 1)

    def test_config_is_complete_and_unknown_or_missing_batch_is_rejected(self):
        for kind in ('missing', 'unknown'):
            data = deepcopy(self.data)
            if kind == 'missing':
                data['batches'].pop(next(iter(data['batches'])))
            else:
                data['batches']['f' * 64] = next(iter(data['batches'].values()))
            self.config.write_text(json.dumps(data)); self.config_sha = sha(self.config)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'exactly all published'):
                self.call()

    def test_reviewed_inventory_missing_duplicate_or_unknown_is_rejected(self):
        other = self.root / 'not-declared.json'; other.write_text('{"unit_only":true}')
        for paths in (self.paths[:1], [self.paths[0], self.paths[0]], [*self.paths, other]):
            with self.subTest(paths=paths), self.assertRaisesRegex(ValueError, 'Every published extension'):
                self.call(paths=paths)

    def test_wrong_config_sha_and_unpaired_flags_reject_before_source_preparation(self):
        with patch('validate_sources.prepare_extension', wraps=prepare) as execute:
            self.config_sha = 'f' * 64
            with self.assertRaisesRegex(ValueError, 'checksum'):
                self.call()
            execute.assert_not_called()
        for config, token in ((self.config, None), (None, sha(self.config))):
            with self.subTest(config=config), self.assertRaisesRegex(ValueError, 'both required'):
                audit_extension_sources(self.catalog, self.paths, None, config_path=config, trusted_config_sha256=token)

    def test_duplicate_config_json_keys_and_conflicting_fields_are_rejected(self):
        digest = next(iter(self.specs)); spec = json.dumps(self.specs[digest])
        self.config.write_text('{"schema":' + json.dumps(EXTENSION_CONFIG_SCHEMA) + ',"batches":{"' + digest + '":' + spec + ',"' + digest + '":' + spec + '}}')
        self.config_sha = sha(self.config)
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            self.call()
        self.data['batches'][digest]['source_json_sha256'] = 'f' * 64
        self.write_config()
        with self.assertRaisesRegex(ValueError, 'Unknown/missing'):
            self.call()

    def test_source_translation_or_render_tampering_is_detected(self):
        for kind in ('pdf', 'translation', 'render'):
            with self.subTest(kind=kind):
                spec = self.specs[sha(self.paths[1])]
                path = self.root / (spec['pdf_dir'] + '/ima-fictional-unit-2.pdf' if kind == 'pdf' else
                                    spec['translations'] if kind == 'translation' else spec['evidence_root'] + '/view.png')
                old = path.read_bytes(); path.write_bytes(b'tampered fictional unit bytes')
                try:
                    with self.assertRaises((ValueError, OSError)):
                        self.call()
                finally:
                    path.write_bytes(old)

    def test_published_field_and_batch_statistics_must_match_recomputed_sources(self):
        for kind in ('field', 'count', 'record'):
            catalog = deepcopy(self.catalog)
            if kind == 'field':
                catalog['minerals'][1]['physical_properties']['hardness']['value'] = '99'
            elif kind == 'count':
                catalog['physical_stats']['extension_batches'][1]['field_status_counts']['verified'] = 999
            else:
                catalog['physical_stats']['extension_batches'][1]['records'][0]['catalog_id'] = 'ima-not-the-source'
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'differ'):
                self.call(catalog=catalog)

    def test_duplicate_declared_source_batch_cannot_double_count(self):
        catalog = deepcopy(self.catalog)
        catalog['physical_stats']['extension_batches'].append(deepcopy(catalog['physical_stats']['extension_batches'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate published'):
            self.call(catalog=catalog)


if __name__ == '__main__':
    unittest.main()
