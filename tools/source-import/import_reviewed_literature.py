#!/usr/bin/env python3
"""Stage or explicitly apply Root-reviewed literature facts to exact IMA IDs.

No source PDFs, render pixels or long transcription are distributed. Does not
change the 105 inference/confirmation labels, physical facts, formulae or models.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from literature_contract import (FIELDS, GEO_SCOPE, GEO_NOTICE, canonical_sha, read_json, require,
                                 sha, stage_import, validate_inputs)

BEGIN = '// BEGIN SOURCE-BOUND LITERATURE PROPERTIES'
END = '// END SOURCE-BOUND LITERATURE PROPERTIES'
PINS = ('source_json_sha256', 'render_index_sha256', 'physical_decision_sha256', 'root_ledger_sha256')
BATCH_CONFIG_SCHEMA = 'shikuang.private.additional-literature-batches.v1'
BATCH_SPEC_KEYS = {'proposal', 'index', 'physical', 'pdf_dir', 'evidence_root', 'ledger', 'trusted_ledger_sha256'}


def approved_properties(inputs, staged, ledger):
    require(staged.get('unit_fixture') is False and staged.get('automatically_approved') is False, 'Cannot publish unit fixtures or auto-approvals')
    by_id = {r['id']: deepcopy(r['literature_properties']) for r in staged['records']}
    decisions = {(d['key'], d['field']): d for d in ledger['decisions']}
    for row in staged['withheld']:
        identity = row['key'], row['field']
        item = inputs['fields'][identity]
        prop, source = item['prop'], item['record']
        state = 'unavailable' if prop['decision'] == 'unavailable' else 'needs_review'
        fact = {'status': state, 'value_zh': None, 'display_as_verified': False,
                'source_url': source['source_url'], 'source_pdf_sha256': source['source_pdf_sha256'],
                'source_page': prop['source_page'], 'source_pages': prop['source_pages'], 'original_excerpt': prop['original_excerpt'],
                'proposal_decision': prop['decision'], 'root_decision': row['root_decision'],
                'proposal_field_sha256': item['field_sha256'], 'evidence_sha256': item['evidence_sha256'],
                'render_index_sha256': inputs['render_index_sha256'], 'root_ledger_sha256': staged['root_ledger_sha256'],
                'review_note': decisions.get(identity, {}).get('review_note') or prop.get('review_note', ''),
                'truth_scope': 'Not admitted as a verified literature fact.', 'source_permission_scope': source['source_permission_scope']}
        if prop.get('terminology_to_review'):
            fact['terminology_to_review'] = prop['terminology_to_review']
        if identity[1] == 'distribution':
            fact.update(geography_scope=GEO_SCOPE, specimen_origin_inference_allowed=False, display_notice_zh=GEO_NOTICE)
        by_id.setdefault(identity[0], {})[identity[1]] = fact
    require(set(by_id) == {key for key, field in inputs['fields']}, 'Not all reviewed species accounted for')
    require(all(set(props) == set(FIELDS) for props in by_id.values()), 'Two-field decisions incomplete')
    return by_id


def batch_record(inputs, staged, facts):
    pins = {'source_json_sha256': inputs['proposal_sha256'], 'render_index_sha256': inputs['render_index_sha256'],
            'physical_decision_sha256': inputs['physical_decision_sha256'], 'root_ledger_sha256': staged['root_ledger_sha256']}
    require(all(type(value) is str and re.fullmatch('[a-f0-9]{64}', value) for value in pins.values()), 'Invalid literature source pins')
    for props in facts.values():
        require(set(props) == set(FIELDS), 'Incomplete literature batch fields')
        for prop in props.values():
            require(prop.get('root_ledger_sha256') == pins['root_ledger_sha256'] and
                    prop.get('render_index_sha256') == pins['render_index_sha256'], 'Literature field source owner differs')
    counts = Counter(prop['status'] for props in facts.values() for prop in props.values())
    return {'batch_id': canonical_sha(pins), **pins, 'species_ids': sorted(facts), 'species_count': len(facts),
            'field_status_counts': dict(sorted(counts.items())), 'verified_literature_fields': counts['verified']}


def literature_statistics(facts, batches, include_registry=False):
    require(bool(batches), 'Literature source registry is empty')
    counts = Counter(prop['status'] for props in facts.values() for prop in props.values())
    stats = {'catalog_species_with_literature_facts': len(facts), 'field_status_counts': dict(sorted(counts.items())),
             'verified_literature_fields': counts['verified'], 'complete_all_minerals': False,
             'source_scope': 'Selected source-reviewed occurrence and nonexhaustive distribution paraphrases only.',
             **{key: batches[0][key] for key in PINS}, 'scientific_experiment_or_model_accuracy_claim': False}
    if include_registry:
        stats.update(batch_schema_version=1, source_batches=deepcopy(batches), source_batch_registry_sha256=canonical_sha(batches))
    return stats


def prepare_catalog(catalog, inputs, staged, ledger, additional_batches=None):
    """Reconstruct every supplied batch, then account for all pre-existing facts.

    Existing JSON is never treated as approval evidence. The caller must validate
    and stage every batch's source and trusted Root ledger before calling here.
    A legacy single batch retains its exact statistics until another is added.
    """
    result = deepcopy(catalog)
    by_id = {r['id']: r for r in result['minerals']}
    require(len(by_id) == len(result['minerals']), 'Duplicate catalog IMA ID')
    facts, records, facts_by_batch, ledger_owners = {}, {}, {}, {}
    for batch_inputs, batch_staged, batch_ledger in [(inputs, staged, ledger), *(additional_batches or [])]:
        batch_facts = approved_properties(batch_inputs, batch_staged, batch_ledger)
        record = batch_record(batch_inputs, batch_staged, batch_facts)
        identity, owner = record['batch_id'], record['root_ledger_sha256']
        require(owner not in ledger_owners or ledger_owners[owner] == identity, 'Same Root ledger reused for different source material')
        ledger_owners[owner] = identity
        if identity in records:
            require(records[identity] == record and facts_by_batch[identity] == batch_facts, 'Same literature batch changed contents')
            continue
        require(not set(facts).intersection(batch_facts), 'Overlapping species ownership across literature batches')
        for key in batch_facts:
            entity = batch_inputs['fields'][(key, FIELDS[0])]['entity']
            require(key in by_id and by_id[key]['name_en'] == entity['name_en'] and
                    by_id[key].get('ima_number') == entity.get('ima_number'), 'Catalog IMA identity changed')
        records[identity], facts_by_batch[identity] = record, batch_facts
        facts.update(batch_facts)
    previous_facts = {r['id']: r['literature_properties'] for r in result['minerals'] if r.get('literature_properties')}
    require(set(previous_facts) <= set(facts), 'Unaccounted literature source batch; all historical source evidence is required')
    for key, previous in previous_facts.items():
        require(previous == facts[key], 'Existing literature facts would be overwritten: ' + key)
    old_stats = catalog.get('literature_stats')
    old_ids = []
    if previous_facts:
        require(type(old_stats) is dict, 'Existing literature facts lack source statistics')
        if 'source_batches' in old_stats:
            declared = old_stats['source_batches']
            require(type(declared) is list and declared and old_stats.get('batch_schema_version') == 1 and
                    old_stats.get('source_batch_registry_sha256') == canonical_sha(declared), 'Literature batch registry checksum/schema differs')
            for record in declared:
                identity = record.get('batch_id')
                require(identity in records and identity not in old_ids and record == records[identity], 'Declared literature batch not supplied or source/count/species differ')
                old_ids.append(identity)
        else:
            matches = [identity for identity, record in records.items() if
                       all(old_stats.get(key) == record[key] for key in PINS) and set(record['species_ids']) == set(previous_facts)]
            require(len(matches) == 1, 'Legacy literature batch has unknown source ownership')
            old_ids = matches
        accounted = {key: props for identity in old_ids for key, props in facts_by_batch[identity].items()}
        require(accounted == previous_facts, 'Existing literature species do not match declared source batches')
        expected_old = literature_statistics(accounted, [records[key] for key in old_ids], 'source_batches' in old_stats)
        require(old_stats == expected_old, 'Existing literature statistics/source batch differ')
    else:
        require(not old_stats, 'Literature statistics exist without owned catalog facts')
    order = old_ids + [identity for identity in records if identity not in old_ids]
    batches = [records[identity] for identity in order]
    # A caller may supply the new primary first; publication order still follows
    # the preserved registry, so idempotent imports also reproduce JS bytes.
    facts = {key: props for identity in order for key, props in facts_by_batch[identity].items()}
    stats = literature_statistics(facts, batches, len(batches) > 1 or bool(old_stats and 'source_batches' in old_stats))
    for key, props in facts.items():
        by_id[key]['literature_properties'] = deepcopy(props)
    result['literature_stats'] = stats
    return result, {'schema_version': 1, 'count': len(facts), 'by_species': facts, 'counts': stats}


def load_validated_batch(spec, catalog_path):
    require(set(spec) == BATCH_SPEC_KEYS, 'Unknown/missing literature batch configuration fields')
    inputs = validate_inputs(spec['proposal'], spec['index'], spec['physical'], catalog_path, spec['pdf_dir'], spec['evidence_root'])
    staged = stage_import(inputs, spec['ledger'], spec['trusted_ledger_sha256'])
    ledger = read_json(spec['ledger'])
    require(sha(spec['ledger']) == spec['trusted_ledger_sha256'], 'Ledger changed during staging')
    return inputs, staged, ledger


def load_additional_batches(config_path, trusted_config_sha256, catalog_path):
    require(bool(config_path) == bool(trusted_config_sha256), 'Additional batch config and independently trusted config SHA are both required')
    if not config_path:
        return []
    config_path = Path(config_path)
    require(type(trusted_config_sha256) is str and re.fullmatch('[a-f0-9]{64}', trusted_config_sha256) and
            sha(config_path) == trusted_config_sha256, 'Additional literature batch config checksum differs')
    config = read_json(config_path)
    require(set(config) == {'schema', 'batches'} and config['schema'] == BATCH_CONFIG_SCHEMA and
            type(config['batches']) is list and config['batches'], 'Unknown/empty additional literature batch config')
    batches = []
    for raw in config['batches']:
        require(type(raw) is dict and set(raw) == BATCH_SPEC_KEYS, 'Unknown/missing additional literature batch fields')
        spec = {'trusted_ledger_sha256': raw['trusted_ledger_sha256']}
        for key in BATCH_SPEC_KEYS - {'trusted_ledger_sha256'}:
            require(type(raw[key]) is str and raw[key], 'Invalid additional literature source path')
            path = Path(raw[key])
            spec[key] = (config_path.parent / path).resolve() if not path.is_absolute() else path
        batches.append(load_validated_batch(spec, catalog_path))
    require(sha(config_path) == trusted_config_sha256, 'Additional batch config changed during validation')
    return batches


def bundle_script(minerals_text, bundle):
    block = BEGIN + '\nwindow.MINERAL_LITERATURE_PROPERTIES=' + json.dumps(bundle, ensure_ascii=False, separators=(',', ':')) + ';\n' + END
    require(minerals_text.count(BEGIN) == minerals_text.count(END) and minerals_text.count(BEGIN) <= 1, 'Ambiguous literature JS block')
    if BEGIN in minerals_text:
        return re.sub(re.escape(BEGIN) + r'[\s\S]*?' + re.escape(END), lambda _: block, minerals_text)
    return minerals_text.rstrip('\n') + '\n' + block + '\n'


def literature_bundle_identity(minerals_bytes, stats):
    identity = {'path': 'data/minerals.js', 'bytes': len(minerals_bytes),
                'sha256': hashlib.sha256(minerals_bytes).hexdigest(), 'root_ledger_sha256': stats['root_ledger_sha256']}
    if 'source_batches' in stats:
        identity.update(source_batch_registry_sha256=stats['source_batch_registry_sha256'],
                        root_ledger_sha256s=[batch['root_ledger_sha256'] for batch in stats['source_batches']])
    return identity


def manifest_for(manifest, catalog_bytes, minerals_bytes, stats):
    result = deepcopy(manifest)
    rows = [r for r in result['files'] if r['path'] == 'data/catalog.json']
    require(len(rows) == 1 and len(result['files']) == 3, 'Exactly one catalog entry in the unchanged three-file manifest required')
    rows[0].update(bytes=len(catalog_bytes), sha256=hashlib.sha256(catalog_bytes).hexdigest())
    result['counts'].update(catalog_species_with_literature_facts=stats['catalog_species_with_literature_facts'],
                            verified_literature_fields=stats['verified_literature_fields'])
    result['literature_bundle'] = literature_bundle_identity(minerals_bytes, stats)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'proposal', 'index', 'physical', 'pdf-dir', 'evidence-root', 'ledger', 'output-dir'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--trusted-ledger-sha256', required=True)
    parser.add_argument('--additional-literature-batch-config', type=Path, help='Private additional source/ledger specs; each batch is fully validated')
    parser.add_argument('--trusted-additional-literature-batch-config-sha256', help='Independently checked SHA of the entire additional config')
    parser.add_argument('--publish-to-app', action='store_true', help='Explicit local file application, not website deployment')
    args = parser.parse_args()
    catalog_path, minerals_path, manifest_path = [args.repo / ('data/' + name) for name in ('catalog.json', 'minerals.js', 'reference-manifest.json')]
    previous = {path: sha(path) for path in (catalog_path, minerals_path, manifest_path)}
    inputs, staged, ledger = load_validated_batch({'proposal': args.proposal, 'index': args.index, 'physical': args.physical,
                                                  'pdf_dir': args.pdf_dir, 'evidence_root': args.evidence_root,
                                                  'ledger': args.ledger, 'trusted_ledger_sha256': args.trusted_ledger_sha256}, catalog_path)
    additional = load_additional_batches(args.additional_literature_batch_config,
                                         args.trusted_additional_literature_batch_config_sha256, catalog_path)
    result, bundle = prepare_catalog(read_json(catalog_path), inputs, staged, ledger, additional)
    catalog_bytes = (json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    minerals_bytes = bundle_script(minerals_path.read_text(encoding='utf-8'), bundle).encode('utf-8')
    manifest = manifest_for(read_json(manifest_path), catalog_bytes, minerals_bytes, result['literature_stats'])
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {'schema_version': 1, 'scope': 'Explicit root-reviewed source paraphrases only; no training or experimental accuracy claim.',
              'counts': result['literature_stats'], 'files': {}, 'applied_to_local_app': args.publish_to_app,
              'source_PDF_or_pixels_redistributed': False}
    for name, contents in [('catalog.json', catalog_bytes), ('minerals.js', minerals_bytes), ('reference-manifest.json', manifest_bytes)]:
        output = args.output_dir / name
        require(not output.exists(), 'New output directory required: ' + str(output))
        output.write_bytes(contents)
        report['files']['data/' + name] = {'bytes': len(contents), 'sha256': hashlib.sha256(contents).hexdigest()}
    if args.publish_to_app:
        require(all(sha(path) == digest for path, digest in previous.items()), 'App data changed during staging; refusing overwrite')
        for path, contents in [(catalog_path, catalog_bytes), (minerals_path, minerals_bytes), (manifest_path, manifest_bytes)]:
            temporary = path.with_suffix(path.suffix + '.literature.tmp')
            temporary.write_bytes(contents)
            temporary.replace(path)
    (args.output_dir / 'literature-import-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'local_app_applied': args.publish_to_app, 'counts': result['literature_stats'], 'files': report['files']}))


if __name__ == '__main__':
    main()
