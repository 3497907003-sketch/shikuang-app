#!/usr/bin/env python3
"""Audit published reference data against private original sources, read-only.

Only writes the requested summary report. PDF pages, archive text, photographs,
cookies and full source documents are never copied into the report.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import re
import subprocess
import unicodedata
from urllib.parse import urlsplit
import zipfile
from PIL import Image
from annotate_crystal_systems import compile_annotations
from bind_physical_sources import bound_properties
from import_reviewed_extension import prepare as prepare_extension
from copy import deepcopy
from import_reviewed_literature import (prepare_catalog as prepare_literature_catalog, load_validated_batch,
                                       load_additional_batches, literature_bundle_identity)
from literature_contract import require, read_json as strict_read_json
from import_reviewed_names import reviewed_records as reviewed_name_records


SUB = str.maketrans('0123456789+-=()aeiorux', '₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑᵢₒᵣᵤₓ')
SUP = str.maketrans('0123456789+-=()n', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ')
ORIGINAL_FIELDS = ('name_en', 'formula', 'formula_html', 'ima_status', 'ima_number',
                   'discovery_country', 'first_reference', 'second_reference',
                   'source_url', 'source_page', 'source_id')
EXCLUDED = r'synthetic|synthesi|calculated|simulat|theoretical|hypothetical|idealized|ab initio|first.princip|density functional|\bDFT\b|quantum|mathematical model|optimized|predicted'
EXTENSION_CONFIG_SCHEMA = 'shikuang.private.extension-source-config.v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def normal(value):
    return unicodedata.normalize('NFKC', value).strip().casefold().replace('\u2011', '-')


def formula_plain(value):
    for tag, conversion in [('sub', SUB), ('sup', SUP)]:
        value = re.sub(r'<' + tag + r'>(.*?)</' + tag + r'>',
                       lambda m: html.unescape(m[1]).translate(conversion), value)
    # Spaces assigned to a small script font by the original PDF may be wrapped
    # in separate HTML tags. Compare the same normalized whitespace as the
    # source extractor; retain every chemical character and its script position.
    return re.sub(r'\s+', ' ', html.unescape(value)).strip()


def audit_literature_batches(catalog, catalog_path, primary_spec, additional_config=None, trusted_config_sha256=None):
    """Revalidate the originals and Root decisions for every published batch."""
    inputs, staged, ledger = load_validated_batch(primary_spec, catalog_path)
    additional = load_additional_batches(additional_config, trusted_config_sha256, catalog_path)
    expected, bundle = prepare_literature_catalog(catalog, inputs, staged, ledger, additional)
    stats = expected['literature_stats']
    counts = stats['field_status_counts']
    review = {'source_species': bundle['count'], 'source_batches': stats.get('source_batches', []),
              'approved_fields': counts.get('verified', 0),
              'withheld_fields': sum(counts.values()) - counts.get('verified', 0),
              'root_ledger_sha256': stats['root_ledger_sha256'],
              'root_ledger_sha256s': [batch['root_ledger_sha256'] for batch in stats.get('source_batches', [])] or [stats['root_ledger_sha256']],
              'all_declared_batches_revalidated': True,
              'scope': 'Chinese source correspondence, not experimental or model accuracy verification.'}
    return expected, bundle, review


def extension_source_specs(batch_hashes, config_path=None, trusted_config_sha256=None,
                           pdf_dir=None, evidence_root=None, translations=None):
    """Resolve complete, independently SHA-bound per-batch source locations."""
    require(bool(config_path) == bool(trusted_config_sha256), 'Extension config and independently trusted config SHA are both required')
    if config_path is None:
        require(not batch_hashes or all(path is not None for path in (pdf_dir, evidence_root, translations)),
                'Private extension PDF, actual viewed evidence and translations paths required')
        return {digest: {'pdf_dir': Path(pdf_dir), 'evidence_root': Path(evidence_root), 'translations': Path(translations)}
                for digest in batch_hashes}
    config_path = Path(config_path)
    require(type(trusted_config_sha256) is str and re.fullmatch('[a-f0-9]{64}', trusted_config_sha256) and
            sha(config_path) == trusted_config_sha256, 'Extension source config checksum differs')
    config = strict_read_json(config_path)
    require(set(config) == {'schema', 'batches'} and config['schema'] == EXTENSION_CONFIG_SCHEMA and
            type(config['batches']) is dict, 'Unknown extension source config schema')
    require(set(config['batches']) == set(batch_hashes), 'Extension config must name exactly all published source batches; missing or unknown batch')
    resolved = {}
    for digest, raw in config['batches'].items():
        require(type(raw) is dict and set(raw) == {'pdf_dir', 'evidence_root', 'translations'}, 'Unknown/missing per-batch extension source fields')
        spec = {}
        for key, value in raw.items():
            require(type(value) is str and value, 'Invalid per-batch extension source path')
            path = Path(value)
            spec[key] = (config_path.parent / path).resolve() if not path.is_absolute() else path
        resolved[digest] = spec
    return resolved


def audit_extension_sources(catalog, reviewed_paths, default_translations, pdf_dir=None, evidence_root=None,
                            config_path=None, trusted_config_sha256=None):
    """Actually prepare and compare each declared extension from its own roots.

    This remains read-only. A catalog entry and its self-reported counters are
    not evidence that its original PDF, viewed render or translation was read.
    """
    declared = catalog.get('physical_stats', {}).get('extension_batches', [])
    batch_hashes = [row['source_json_sha256'] for row in declared]
    require(all(type(digest) is str and re.fullmatch('[a-f0-9]{64}', digest) for digest in batch_hashes) and
            len(set(batch_hashes)) == len(batch_hashes), 'Invalid/duplicate published extension source batches')
    paths = [Path(path) for path in reviewed_paths or []]
    actual_hashes = [sha(path) for path in paths]
    require(len(set(actual_hashes)) == len(actual_hashes) and sorted(batch_hashes) == sorted(actual_hashes),
            'Every published extension requires its exact reviewed source JSON; missing, duplicate or unknown source is not audited')
    specs = extension_source_specs(batch_hashes, config_path, trusted_config_sha256, pdf_dir, evidence_root, default_translations)
    declared_by_hash = {row['source_json_sha256']: row for row in declared}
    species = {row['id']: row for row in catalog['minerals']}
    require(len(species) == len(catalog['minerals']), 'Duplicate catalog IMA IDs')
    proofs, all_keys = [], set()
    for path, digest in zip(paths, actual_hashes):
        extension = strict_read_json(path)
        keys = [row['key'] for row in extension['records']]
        require(len(set(keys)) == len(keys) and not all_keys.intersection(keys), 'Duplicate extension species within/across batches')
        require(set(keys) <= set(species), 'Unknown extension species')
        spec = specs[digest]
        translation_sha = sha(spec['translations'])
        require(declared_by_hash[digest].get('translations_sha256') == translation_sha, 'Published extension translations checksum differs')
        temporary = deepcopy(catalog)
        for row in temporary['minerals']:
            if row['id'] in keys:
                row.pop('physical_properties', None)
                row.pop('physical_review', None)
        expected, proof = prepare_extension(temporary, extension, strict_read_json(spec['translations']),
                                            spec['pdf_dir'], spec['evidence_root'])
        expected_rows = {row['id']: row for row in expected['minerals']}
        require(all(species[key].get(field) == expected_rows[key].get(field)
                    for key in keys for field in ('physical_properties', 'physical_review')),
                'Published extension source facts/translation/review differ')
        require(all(declared_by_hash[digest].get(field) == proof[field]
                    for field in ('species', 'field_status_counts', 'records')),
                'Published extension batch species/count/source proof differs')
        require(sha(path) == digest and sha(spec['translations']) == translation_sha, 'Extension source/translation changed during audit')
        proofs.append({'source_json_sha256': digest, **proof})
        all_keys.update(keys)
    if config_path is not None:
        require(sha(Path(config_path)) == trusted_config_sha256, 'Extension source config changed during audit')
    return proofs, all_keys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True, help='Private source folder; only read, never copied')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--re-extracted-ima', type=Path, help='Fresh portable extract_ima.py output for all-row reproducibility comparison')
    parser.add_argument('--re-extracted-physical', type=Path, help='Fresh collector + finalizer output for reproducibility comparison')
    parser.add_argument('--reviewed-extension', type=Path, nargs='+', help='Each actual finalized extension source file; required when the catalog has extension batches')
    parser.add_argument('--extension-pdf-dir', type=Path)
    parser.add_argument('--extension-evidence-root', type=Path)
    parser.add_argument('--extension-source-config', type=Path, help='SHA-bound complete per-reviewed-JSON source-root/translation map')
    parser.add_argument('--trusted-extension-source-config-sha256')
    parser.add_argument('--literature-proposal', type=Path)
    parser.add_argument('--literature-render-index', type=Path)
    parser.add_argument('--literature-physical-registry', type=Path)
    parser.add_argument('--literature-pdf-dir', type=Path)
    parser.add_argument('--literature-evidence-root', type=Path)
    parser.add_argument('--literature-ledger', type=Path)
    parser.add_argument('--trusted-literature-ledger-sha256')
    parser.add_argument('--additional-literature-batch-config', type=Path)
    parser.add_argument('--trusted-additional-literature-batch-config-sha256')
    parser.add_argument('--node', default='node')
    args = parser.parse_args()
    repo, source = args.repo, args.sources
    report = {'schema_version': 1, 'validated_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'All published reference records compared to acquired official-source files and reviewed imports. This audit does not establish ML accuracy, photograph quality or photo reuse permission.',
              'checks': {}, 'anomalies': {}, 'files': {}, 'original_sources': {}}

    def check(name, failed):
        failed = list(failed)
        report['checks'][name] = not failed
        if failed:
            report['anomalies'][name] = {'count': len(failed), 'examples': failed[:5]}

    catalog = read(repo / 'data/catalog.json')
    crystals = read(repo / 'data/crystals.json')
    images = read(repo / 'data/image-sources.json')
    original = read(source / 'ima-catalog-2026-09.json')
    physical = read(source / 'physical-properties.json')
    original_images = read(source / 'image-sources.json')
    originals = {row['id']: row for row in original['minerals']}
    species = {row['id']: row for row in catalog['minerals']}
    by_name = {normal(row['name_en']): row for row in species.values()}
    expression = "const fs=require('node:fs'),vm=require('node:vm');const c={window:{}};vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),c);process.stdout.write(JSON.stringify({knowledge:c.window.MINERAL_KB,crystal_systems:c.window.MINERAL_CRYSTAL_SYSTEM_ANNOTATIONS,literature:c.window.MINERAL_LITERATURE_PROPERTIES}));"
    extracted = json.loads(subprocess.run([args.node, '-e', expression, str(repo / 'data/minerals.js')], check=True, capture_output=True, text=True).stdout)
    kb = extracted['knowledge']
    check('official_catalog_count_and_unique_ids', [] if catalog['count'] == len(catalog['minerals']) == len(species) == len(originals) == 6239 else ['count or unique ID mismatch'])
    check('official_names_unique', [] if len({r['name_en'] for r in species.values()}) == 6239 else ['duplicate name'])
    try:
        expected_names = reviewed_name_records(read(Path(__file__).with_name('reviewed-names-zh.json')), catalog)
        check('source_reviewed_chinese_names', [] if catalog.get('reviewed_names_zh') == {'schema_version': 1, 'records': expected_names} else ['Reviewed name overlay differs'])
    except (ValueError, KeyError, TypeError) as error:
        check('source_reviewed_chinese_names', ['Invalid source-reviewed names: ' + str(error)])
    check('official_fields_preserved', [row['id'] + ':' + field for row in species.values() for field in ORIGINAL_FIELDS if row.get(field) != originals.get(row['id'], {}).get(field)])
    check('formula_unicode_html_equivalent', [r['id'] for r in species.values() if formula_plain(r['formula_html']) != r['formula'] or re.search(r'</?(?:sub|sup)\b|�|[\ue000-\uf8ff]', r['formula'])])
    check('symbol_formula_glyphs_match_reviewed_pdf_pages', [name for name, formula in {
        'Gachingite': 'Au(Te₁₋ₓSeₓ) (0.2 ≈ x ≤ 0.5)',
        'Orcelite': 'Ni₅₋ₓAs₂ (x ≈ 0.25)',
        'Sluzhenikinite': 'Pd₁₅(Sb₇₋ₓSnₓ) (3 ≤ x ≤ 4)',
    }.items() if by_name.get(normal(name), {}).get('formula') != formula])
    check('source_page_valid', [r['id'] for r in species.values() if not isinstance(r['source_page'], int) or not 3 <= r['source_page'] <= 244])
    legacy_formulas = [key for key, row in kb.items() if row.get('formula_source')]
    check('legacy_official_formula_and_source', [key for key in legacy_formulas if normal(kb[key]['name_en']) not in by_name or kb[key]['formula'] != by_name[normal(kb[key]['name_en'])]['formula'] or kb[key]['formula_source'] != {'source_id': 'ima-cnmnc', 'url': by_name[normal(kb[key]['name_en'])]['source_url'], 'page': by_name[normal(kb[key]['name_en'])]['source_page'], 'version': catalog['version']}])
    check('legacy_kb_count', [] if len(kb) == 105 else ['expected 105 original labels'])
    literature_rows = [row for row in catalog['minerals'] if row.get('literature_properties')]
    if literature_rows or catalog.get('literature_stats') or extracted.get('literature'):
        required_literature = [args.literature_proposal, args.literature_render_index, args.literature_physical_registry,
                               args.literature_pdf_dir, args.literature_evidence_root, args.literature_ledger,
                               args.trusted_literature_ledger_sha256]
        check('literature_private_evidence_supplied', [] if all(required_literature) else ['All private source/index/Root-ledger inputs and independently trusted ledger SHA required'])
        if all(required_literature):
            try:
                expected, bundle, review = audit_literature_batches(catalog, repo / 'data/catalog.json', {'proposal': args.literature_proposal,
                    'index': args.literature_render_index, 'physical': args.literature_physical_registry,
                    'pdf_dir': args.literature_pdf_dir, 'evidence_root': args.literature_evidence_root,
                    'ledger': args.literature_ledger, 'trusted_ledger_sha256': args.trusted_literature_ledger_sha256},
                    args.additional_literature_batch_config, args.trusted_additional_literature_batch_config_sha256)
                check('literature_actual_source_and_root_field_decisions', [] if expected == catalog else ['Root-approved catalog facts differ'])
                check('literature_js_exact_ima_binding', [] if extracted.get('literature') == bundle else ['Independent IMA literature bundle differs'])
                report['literature_review'] = review
            except (ValueError, KeyError, OSError, TypeError) as error:
                check('literature_actual_source_and_root_field_decisions', [str(error)])
    pdf = source / 'IMA_Master_List_2026-09.pdf'
    archive = source / 'amc.zip'
    check('original_pdf_hash', [] if sha(pdf) == catalog['source']['sha256'] else ['IMA PDF SHA-256 mismatch'])
    check('original_zip_hash', [] if sha(archive) == crystals['source']['sha256'] else ['AMCSD ZIP SHA-256 mismatch'])
    check('ima_license_and_credits_preserved', [] if (repo / 'data/licenses/ima-cnmnc-2026-09.txt').read_bytes() == (source / 'IMA-CNMNC-CREDITS-LICENSE.txt').read_bytes() and catalog['source']['license'] == 'CC BY-SA 3.0 Unported' and 'creative commons' in (repo / 'data/licenses/ima-cnmnc-2026-09.txt').read_text(encoding='utf-8').lower() else ['license or credits mismatch'])
    if args.re_extracted_ima:
        fresh = {r['id']: r for r in read(args.re_extracted_ima)['minerals']}
        check('all_ima_rows_reproduced_from_original_pdf', [r['id'] + ':' + key for r in species.values() for key in ORIGINAL_FIELDS if r.get(key) != fresh.get(r['id'], {}).get(key)])
    if args.re_extracted_physical:
        check('reviewed_physical_import_reproduced', [] if read(args.re_extracted_physical) == physical else ['reviewed collector output differs from reviewed original'])

    physical_fields = Counter()
    physical_sources = {}
    for row in physical['records']:
        for prop in row['properties'].values():
            physical_fields[prop['status']] += 1
        physical_sources.setdefault(row['source_url'], {'url': row['source_url'], 'sha256': row['source_pdf_sha256'], 'legacy_keys': []})['legacy_keys'].append(row['key'])
    check('physical_review_complete', [] if physical.get('verification_complete') is True and physical.get('complete') is True and len(physical['records']) == 89 and physical_fields['verified'] == 477 else ['physical review incomplete or counts differ'])
    check('physical_legacy_import_exact', [r['key'] for r in physical['records'] if kb.get(r['key'], {}).get('verified_properties') != bound_properties(r)])
    check('physical_catalog_import_exact', [r['key'] for r in physical['records'] if normal(r['name_en']) in by_name and by_name[normal(r['name_en'])].get('physical_properties') != bound_properties(r)])
    check('physical_status_and_null_semantics', [r['key'] + ':' + key for r in physical['records'] for key, prop in r['properties'].items() if prop['status'] not in {'verified', 'needs_review', 'source_inferred', 'unavailable'} or (prop['status'] != 'verified' and prop['value'] is not None) or (prop['status'] == 'verified' and (not prop['value'] or not prop.get('verification'))) or prop['source_url'] != r['source_url'] or prop['source_page'] != 1])
    check('physical_original_pdf_hashes', [r['key'] for r in physical['records'] if sha(source / 'physical-source-pdfs' / (r['key'] + '.pdf')) != r['source_pdf_sha256']])
    check('physical_no_calculated_density_substitution', [r['key'] for r in physical['records'] if r['properties']['density_measured'].get('unit') != 'g/cm³' or re.search(r'calc|calculated', r['properties']['density_measured']['raw'] or '', re.I)])
    extension_proofs, extension_keys = [], set()
    try:
        extension_proofs, extension_keys = audit_extension_sources(catalog, args.reviewed_extension,
            repo / 'tools/source-import/extension-translations-zh.json', args.extension_pdf_dir, args.extension_evidence_root,
            args.extension_source_config, args.trusted_extension_source_config_sha256)
        check('physical_extension_sources_required_and_bound', [])
        check('physical_extensions_source_render_translation_exact', [])
    except (ValueError, KeyError, OSError, TypeError) as error:
        check('physical_extension_sources_required_and_bound', [str(error)])
        check('physical_extensions_source_render_translation_exact', [str(error)])
    original_physical_ids = {by_name[normal(r['name_en'])]['id'] for r in physical['records'] if normal(r['name_en']) in by_name}
    check('all_catalog_physical_facts_accounted_for', [r['id'] for r in species.values() if r.get('physical_properties') and r['id'] not in original_physical_ids | extension_keys])
    report['physical_extensions'] = extension_proofs
    try:
        annotations = compile_annotations(read(repo / 'tools/source-import/crystal-system-reviewed.json'), kb, source / 'physical-source-pdfs')
        check('crystal_system_separate_annotation_exact_and_pdf_bound', [] if extracted.get('crystal_systems') == annotations else ['published annotation differs from reviewed source-bound inference'])
    except (ValueError, KeyError, OSError) as error:
        annotations = {}
        check('crystal_system_separate_annotation_exact_and_pdf_bound', [str(error)])
    report['crystal_system_annotations'] = annotations.get('counts', {})

    crystal_rows = [r for rows in crystals['by_species'].values() for r in rows]
    check('crystal_counts_unique_ids', [] if len(crystal_rows) == crystals['stats']['matched_records'] == len({r['id'] for r in crystal_rows}) == 9895 and len(crystals['by_species']) == crystals['stats']['species_with_records'] == 3430 else ['crystal counts or IDs differ'])
    check('crystal_ima_species_and_cell_values', [r['id'] for key, rows in crystals['by_species'].items() for r in rows if key not in species or normal(r['mineral_name']) != normal(species[key]['name_en']) or set(r['cell']) != {'a', 'b', 'c', 'alpha', 'beta', 'gamma'} or not all(math.isfinite(v) and v > 0 for v in r['cell'].values()) or not all(r['cell'][v] < 180 for v in ['alpha', 'beta', 'gamma'])])
    unmatched_archive, excluded_headers = [], []
    with zipfile.ZipFile(archive) as files:
        archive_count = sum(name.endswith('.amc') for name in files.namelist())
        for row in crystal_rows:
            lines = files.read(row['source_file']).decode('utf-8').splitlines()
            index = next((i for i, line in enumerate(lines) if line.startswith('_database_code_amcsd ')), None)
            header = '\n'.join(lines[:index])
            if re.search(EXCLUDED, header, re.I):
                excluded_headers.append(row['id'])
            fields = lines[index + 1].split() if index is not None else []
            expected = [row['cell'][key] for key in ['a', 'b', 'c', 'alpha', 'beta', 'gamma']]
            if len(fields) != 7 or [float(v) for v in fields[:6]] != expected or fields[6] != row['space_group'] or lines[index].split()[-1] != row['id'] or lines[0].strip() != row['mineral_name'] or row['citation'] not in lines:
                unmatched_archive.append(row['id'])
    check('crystal_archive_count', [] if archive_count == crystals['stats']['archive_records'] == 21503 else ['archive count mismatch'])
    check('all_crystal_measurements_match_original_zip', unmatched_archive)
    check('explicit_synthetic_or_computational_headers_excluded', excluded_headers)
    check('catalog_crystal_counts_match', [r['id'] for r in species.values() if r['crystal_record_count'] != len(crystals['by_species'].get(r['id'], []))])

    rows = images['records']
    old_rows = {r['id']: r for r in original_images['records']}
    current_rows = {r['id']: r for r in rows}
    local_rows = [r for r in rows if r.get('local_image_url')]
    local_ids = {r['id'] for r in local_rows}
    original_mismatch = []
    for key, old in old_rows.items():
        current = current_rows.get(key)
        if current is None:
            original_mismatch.append(key + ':missing')
        elif key not in local_ids and current != old:
            original_mismatch.append(key + ':unreviewed_metadata_changed')
        elif key in local_ids and current.get('previous_source_record_sha256') != hashlib.sha256(json.dumps(old, ensure_ascii=False, sort_keys=True).encode()).hexdigest():
            original_mismatch.append(key + ':reviewed_previous_source_snapshot_changed')
    check('original_image_metadata_preserved_or_reviewed_incremental_snapshot', original_mismatch)
    check('image_counts_unique_ids_urls', [] if len(rows) == images['stats']['image_references'] == len(current_rows) == len({r['original_image_url'] for r in rows}) and len({r['mineral_name'] for r in rows}) == images['stats']['distinct_source_names'] else ['image counts or unique IDs/URLs differ'])
    check('image_species_use_official_names_or_explicit_unresolved_group', [r['id'] for r in rows if normal(r['mineral_name']) not in by_name and not (r.get('label_unit') == 'mineral_group' and r.get('catalog_id') is None)])
    check('unreviewed_images_keep_pending_training_status', [r['id'] for r in rows if r['id'] not in local_ids and (r['training_ready'] is not False or r['quality_review'] != 'not_performed_pixels_not_downloaded' or not r['training_blockers'])])
    assets = read(repo / 'data/reviewed-photo-assets.json')['assets']
    assets_by_path = {r['path']: r for r in assets}
    attribution = {r['id']: r for r in read(repo / 'data/licenses/reviewed-photo-attributions.json')['records']}
    photo_failures = []
    for row in local_rows:
        path = row['local_image_url']
        asset = assets_by_path.get(path)
        local = repo / path
        if not re.fullmatch(r'images/reviewed-v25/commons-\d+\.jpg', path) or not asset or not local.is_file():
            photo_failures.append(row['id'] + ':missing_or_invalid_asset');continue
        evidence = row.get('review_evidence', {})
        required = ('pixel_review_performed', 'source_and_license_review_performed', 'download_provenance_verified', 'source_raw_sha256_verified', 'published_derivative_sha256_verified')
        if row.get('training_ready') is not True or row.get('quality_review_status') != 'pixel_quality_pass' or row.get('source_review_status') != 'per_file_source_label_license_sha_verified' or not all(evidence.get(key) is True for key in required) or evidence.get('source_label_independently_analysed') is not False:
            photo_failures.append(row['id'] + ':incomplete_review_or_false_analytical_claim')
        if row.get('sha256') != row.get('crop_sha256') or row.get('sha256') != sha(local) or asset != {'path': path, 'bytes': local.stat().st_size, 'sha256': sha(local), 'source_asset_id': row['source_asset_id']} or row['bytes'] != local.stat().st_size:
            photo_failures.append(row['id'] + ':published_hash_or_size_mismatch')
        with Image.open(local) as photo:
            if photo.format != 'JPEG' or min(photo.size) < 224 or list(photo.size) != [row['width'], row['height']]:
                photo_failures.append(row['id'] + ':image_dimensions_or_format')
        credit = attribution.get(row['id'], {})
        if any(credit.get(key) != row.get(key) for key in ('author', 'license', 'license_url', 'image_page_url', 'sha256', 'modifications')):
            photo_failures.append(row['id'] + ':license_attribution_mismatch')
        if not all(re.fullmatch(r'[0-9a-f]{64}', row.get(key, '')) for key in ('source_file_sha256', 'crop_sha256')) or not re.fullmatch(r'[0-9a-f]{40}', row.get('source_original_sha1', '')):
            photo_failures.append(row['id'] + ':source_hash_missing')
    check('reviewed_local_photos_source_license_pixels_and_hashes', photo_failures)
    check('reviewed_photo_counts_and_unique_groups_per_label', [] if len(local_rows) == images['stats']['local_images'] == images['stats']['training_ready'] == len(assets) == len(attribution) and len({r['sha256'] for r in local_rows}) == len(local_rows) else ['local photo count or exact-byte duplicate mismatch'])
    check('image_urls_are_official_https', [r['id'] for r in rows if urlsplit(r['original_image_url']).scheme != 'https' or urlsplit(r['original_image_url']).hostname not in {'www.rruff.net', 'upload.wikimedia.org'}])
    check('commons_individual_author_license_metadata', [r['id'] for r in rows if r['source'] == 'Wikimedia Commons' and (not r['author'] or not r['license'] or not r['permission_evidence_url'])])
    check('rruff_permissions_not_invented', [r['id'] for r in rows if r['source'] == 'RRUFF' and (r['license'] is not None or r['author'] is not None or r['permission_status'] != 'unverified_photo_reuse_permission' or not r['sample_id'])])
    check('handbook_and_rruff_no_blanket_open_license_claim', [] if 'no open' in catalog['external_indexes'][0]['source']['license'].lower() and 'No open license' in physical['source']['license'] and 'no explicit per-photo reuse license confirmed' in images['source_policies']['RRUFF']['photo_permission_conclusion'] else ['rights scope wording differs'])
    manifest = read(repo / 'data/reference-manifest.json')
    for item in manifest['files']:
        path = repo / item['path']
        report['files'][item['path']] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
    report['files']['data/minerals.js'] = {'bytes': (repo / 'data/minerals.js').stat().st_size, 'sha256': sha(repo / 'data/minerals.js')}
    check('published_manifest_hashes', [item['path'] for item in manifest['files'] if report['files'][item['path']] != {'bytes': item['bytes'], 'sha256': item['sha256']}])
    if literature_rows:
        bundle_hash = manifest.get('literature_bundle', {})
        try:
            expected_bundle = literature_bundle_identity((repo / 'data/minerals.js').read_bytes(), catalog.get('literature_stats', {}))
            check('published_literature_bundle_hash', [] if bundle_hash == expected_bundle else ['Literature JS bytes/hash/ledger differ from manifest'])
        except (KeyError, TypeError, ValueError) as error:
            check('published_literature_bundle_hash', ['Invalid literature source registry: ' + str(error)])
        check('published_literature_counts', [] if all(manifest['counts'].get(key) == catalog['literature_stats'].get(key) for key in
                                                       ('catalog_species_with_literature_facts', 'verified_literature_fields')) else ['Literature manifest counts differ'])
    catalog_physical = [r for r in species.values() if 'physical_properties' in r]
    catalog_physical_counts = Counter(p['status'] for r in catalog_physical for p in r['physical_properties'].values())
    report['counts'] = {'ima_species': len(species), 'official_formulas_in_legacy_kb': len(legacy_formulas), 'original_kb_labels': len(kb), 'handbook_links': sum(bool(r.get('handbook_url')) for r in species.values()), 'physical_legacy_labels': len(physical['records']), 'physical_unique_pdf_sources': len(physical_sources), 'verified_label_fields': physical_fields['verified'], 'physical_label_field_status_counts': dict(physical_fields), 'catalog_physical_unique_ima_species': len(catalog_physical), 'catalog_unique_species_verified_fields': catalog_physical_counts['verified'], 'catalog_unique_species_field_status_counts': dict(catalog_physical_counts), 'crystal_records': len(crystal_rows), 'crystal_species': len(crystals['by_species']), 'image_references': len(rows), 'image_species': len({r['mineral_name'] for r in rows}), 'training_ready_images': sum(r['training_ready'] for r in rows)}
    report['original_sources'] = {'ima_pdf': {'file': pdf.name, 'sha256': sha(pdf), 'url': catalog['source']['url']}, 'amcsd_zip': {'file': archive.name, 'sha256': sha(archive), 'url': crystals['source']['download_url']}, 'handbook_pdfs': sorted(physical_sources.values(), key=lambda r: r['url'])}
    report['license_review'] = {'ima': {'license': catalog['source']['license'], 'attribution_file': 'data/licenses/ima-cnmnc-2026-09.txt', 'credits_sha256': sha(repo / 'data/licenses/ima-cnmnc-2026-09.txt')}, 'handbook': {'citation': physical['source']['citation'], 'permissions_url': physical['source']['permissions_url'], 'scope': 'Selected scientific facts and source links only; no open PDF/body-text redistribution license identified.'}, 'amcsd': {'scope': crystals['source']['scope'], 'terms': crystals['source']['terms']}, 'images': {'scope': 'Original pending references plus individually licensed, source/pixel/hash-reviewed local Commons photographs. RRUFF photo reuse permission remains unverified. Gallery inclusion does not assert model training or independent analytical identity.'}, 'primary_policy_pages_for_reference': ['https://handbookofmineralogy.org/', 'https://msaweb.org/copyright-permission-request-form/', 'https://www.rruff.net/about/download-data/']}
    report['license_review']['fresh_live_policy_page_verification_performed'] = False
    report['license_review']['audit_uses_saved_sources_without_network_requests'] = True
    report['limitations'] = ['Original legacy formation, uses and unreplaced attributes are not newly verified.', 'Historical Handbook ranges, mixed crystal systems and directional hardness remain as reported.', 'Uncertain cleavage fields and all unverified facts remain null.', 'Acquired files are date-specific; updating an original PDF hash requires another visual review.', 'Recorded source/pixel review and public photo bytes are checked; training splits, released weights, independent analytical identity and accuracy are not certified by this data audit.', 'License wording and attribution are checked; this report does not grant rights to reproduce complete source works.']
    report['anomaly_count'] = sum(v['count'] for v in report['anomalies'].values())
    report['passed'] = report['anomaly_count'] == 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'anomaly_count': report['anomaly_count'], 'counts': report['counts']}, ensure_ascii=False))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
