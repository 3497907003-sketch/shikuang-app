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


def prepare_catalog(catalog, inputs, staged, ledger):
    result = deepcopy(catalog)
    by_id = {r['id']: r for r in result['minerals']}
    require(len(by_id) == len(result['minerals']), 'Duplicate catalog IMA ID')
    facts = approved_properties(inputs, staged, ledger)
    require(not [r['id'] for r in result['minerals'] if r.get('literature_properties') and r['id'] not in facts], 'Unaccounted literature source batch')
    for key, props in facts.items():
        entity = inputs['fields'][(key, FIELDS[0])]['entity']
        require(key in by_id and by_id[key]['name_en'] == entity['name_en'] and by_id[key].get('ima_number') == entity.get('ima_number'), 'Catalog IMA identity changed')
        previous = by_id[key].get('literature_properties')
        require(previous is None or previous == props, 'Existing literature facts would be overwritten: ' + key)
        by_id[key]['literature_properties'] = props
    counts = Counter(p['status'] for props in facts.values() for p in props.values())
    stats = {'catalog_species_with_literature_facts': len(facts), 'field_status_counts': dict(sorted(counts.items())),
             'verified_literature_fields': counts['verified'], 'complete_all_minerals': False,
             'source_scope': 'Selected source-reviewed occurrence and nonexhaustive distribution paraphrases only.',
             'source_json_sha256': inputs['proposal_sha256'], 'render_index_sha256': inputs['render_index_sha256'],
             'physical_decision_sha256': inputs['physical_decision_sha256'], 'root_ledger_sha256': staged['root_ledger_sha256'],
             'scientific_experiment_or_model_accuracy_claim': False}
    require(not result.get('literature_stats') or result['literature_stats'] == stats, 'Existing literature statistics/source batch differ')
    result['literature_stats'] = stats
    bundle = {'schema_version': 1, 'count': len(facts), 'by_species': facts, 'counts': stats}
    return result, bundle


def bundle_script(minerals_text, bundle):
    block = BEGIN + '\nwindow.MINERAL_LITERATURE_PROPERTIES=' + json.dumps(bundle, ensure_ascii=False, separators=(',', ':')) + ';\n' + END
    require(minerals_text.count(BEGIN) == minerals_text.count(END) and minerals_text.count(BEGIN) <= 1, 'Ambiguous literature JS block')
    if BEGIN in minerals_text:
        return re.sub(re.escape(BEGIN) + r'[\s\S]*?' + re.escape(END), lambda _: block, minerals_text)
    return minerals_text.rstrip('\n') + '\n' + block + '\n'


def manifest_for(manifest, catalog_bytes, minerals_bytes, stats):
    result = deepcopy(manifest)
    rows = [r for r in result['files'] if r['path'] == 'data/catalog.json']
    require(len(rows) == 1 and len(result['files']) == 3, 'Exactly one catalog entry in the unchanged three-file manifest required')
    rows[0].update(bytes=len(catalog_bytes), sha256=hashlib.sha256(catalog_bytes).hexdigest())
    result['counts'].update(catalog_species_with_literature_facts=stats['catalog_species_with_literature_facts'],
                            verified_literature_fields=stats['verified_literature_fields'])
    result['literature_bundle'] = {'path': 'data/minerals.js', 'bytes': len(minerals_bytes),
                                  'sha256': hashlib.sha256(minerals_bytes).hexdigest(),
                                  'root_ledger_sha256': stats['root_ledger_sha256']}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'proposal', 'index', 'physical', 'pdf-dir', 'evidence-root', 'ledger', 'output-dir'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--trusted-ledger-sha256', required=True)
    parser.add_argument('--publish-to-app', action='store_true', help='Explicit local file application, not website deployment')
    args = parser.parse_args()
    catalog_path, minerals_path, manifest_path = [args.repo / ('data/' + name) for name in ('catalog.json', 'minerals.js', 'reference-manifest.json')]
    previous = {path: sha(path) for path in (catalog_path, minerals_path, manifest_path)}
    inputs = validate_inputs(args.proposal, args.index, args.physical, catalog_path, args.pdf_dir, args.evidence_root)
    staged = stage_import(inputs, args.ledger, args.trusted_ledger_sha256)
    ledger = read_json(args.ledger)
    require(sha(args.ledger) == args.trusted_ledger_sha256, 'Ledger changed during staging')
    result, bundle = prepare_catalog(read_json(catalog_path), inputs, staged, ledger)
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
