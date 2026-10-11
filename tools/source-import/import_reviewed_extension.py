#!/usr/bin/env python3
"""Add reviewed selected facts to exact IMA IDs, preserving all existing data.

Source PDFs and viewed renders stay private. A proposal is the default; the
explicit publish option updates the local catalog and its checksum manifest.
This does not change model labels, weights, photos or inference knowledge.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

FIELDS = {'hardness', 'density_measured', 'crystal_system', 'cleavage', 'luster', 'streak'}
STATES = {'verified', 'unavailable', 'source_inferred', 'needs_review'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_viewed_source(source, evidence_root, require_index_hash=True):
    """Bind a viewed contact-sheet slot to the exact PDF and mineral identity."""
    proof = source['verification']['evidence']
    path = (evidence_root / proof['path']).resolve()
    if not path.is_relative_to(evidence_root.resolve()) or proof.get('actual_image_viewed') is not True or digest(path) != proof['sha256']:
        raise ValueError('Actual viewed source evidence changed/missing: ' + source['key'])
    index_path = path.parent / 'index.json'
    index_hash = digest(index_path)
    if require_index_hash and proof.get('index_sha256') != index_hash:
        raise ValueError('Viewed source index changed/missing: ' + source['key'])
    index = json.loads(index_path.read_text(encoding='utf-8'))
    sheets = [sheet for sheet in index['sheets'] if sheet['path'] == path.name and sheet['sha256'] == proof['sha256']]
    position = proof.get('position')
    if len(sheets) != 1 or type(position) is not int or position < 1:
        raise ValueError('Viewed source sheet/position invalid: ' + source['key'])
    slots = [slot for slot in sheets[0]['sources'] if slot.get('position') == position]
    pages = {prop.get('source_page') for prop in source['properties'].values()}
    if len(pages) != 1 or pages != {1} or source.get('source_page', 1) != 1:
        raise ValueError('Viewed source field pages inconsistent: ' + source['key'])
    if len(slots) != 1 or any(slots[0].get(field) != source.get(field) for field in ('key', 'source_url', 'source_pdf_sha256')) or slots[0].get('source_page') != 1:
        raise ValueError('Viewed source slot does not match exact PDF identity: ' + source['key'])
    crop = slots[0].get('crop_points')
    if not isinstance(crop, list) or len(crop) != 4 or any(type(x) not in (int, float) or not math.isfinite(x) for x in crop) or crop[0] < 0 or crop[1] < 0 or crop[2] <= crop[0] or crop[3] <= crop[1]:
        raise ValueError('Viewed source crop invalid: ' + source['key'])
    return index_hash


def translated(prop, field, translations):
    value = prop['value']
    if prop['status'] != 'verified':
        return None
    text = translations.get(field, {}).get(value)
    if text is None and not re.search(r'[A-Za-z]{2}', value):
        # Numeric scientific notation is preserved, not machine translated.
        text = value
    if not isinstance(text, str) or not text or re.search(r'[A-Za-z]{2}', text):
        raise ValueError('Exact Chinese translation missing: ' + field + ':' + value)
    return {'status': 'reviewed', 'source_value': value, 'text_zh': text}


def prepare(catalog, reviewed, translations, pdf_dir, evidence_root):
    if reviewed.get('schema_version') != 1 or translations.get('schema_version') != 1:
        raise ValueError('Unsupported source/translation schema')
    if reviewed.get('reviewed_species_count') != len(reviewed['records']):
        raise ValueError('Reviewed source count differs')
    result = deepcopy(catalog)
    rows = {r['id']: r for r in result['minerals']}
    if len(rows) != len(result['minerals']):
        raise ValueError('Catalog contains duplicate IDs')
    seen = set()
    stats = Counter()
    records = []
    for source in reviewed['records']:
        key = source['key']
        if key in seen or key not in rows or rows[key]['name_en'] != source['name_en'] or source.get('ima_species') is not True:
            raise ValueError('Not a unique exact IMA identity: ' + key)
        seen.add(key)
        row = rows[key]
        url = source['source_url']
        if row.get('physical_properties'):
            raise ValueError('Existing physical facts would be overwritten: ' + key)
        if row.get('handbook_url') != url or not re.fullmatch(r'https://(?:www\.)?handbookofmineralogy\.org/pdfs/[A-Za-z0-9_-]+\.pdf', url):
            raise ValueError('Changed/unsupported matched Handbook link: ' + key)
        pdf_hash = source['source_pdf_sha256']
        if not re.fullmatch(r'[a-f0-9]{64}', pdf_hash) or digest(pdf_dir / (key + '.pdf')) != pdf_hash:
            raise ValueError('Source PDF changed: ' + key)
        proof = source['verification']['evidence']
        verify_viewed_source(source, evidence_root)
        if set(source['properties']) != FIELDS:
            raise ValueError('Six-field source decisions incomplete: ' + key)
        props = deepcopy(source['properties'])
        for field, prop in props.items():
            if prop.get('status') not in STATES or prop.get('source_url') != url or prop.get('source_page') != 1:
                raise ValueError('Invalid field status/source/page: ' + key + ':' + field)
            if prop['status'] == 'verified':
                if not isinstance(prop['value'], str) or not prop['value'].strip() or not prop.get('verification'):
                    raise ValueError('Verified field lacks explicit source value/review: ' + key + ':' + field)
            elif prop['value'] is not None:
                raise ValueError('Unverified field must remain null: ' + key + ':' + field)
            if field == 'density_measured' and (prop.get('unit') != 'g/cm³' or re.search(r'calc', prop.get('raw') or '', re.I)):
                raise ValueError('Calculated density must not substitute measured density: ' + key)
            prop['source_pdf_sha256'] = pdf_hash
            translation = translated(prop, field, translations)
            if translation:
                prop['translation'] = translation
            stats[prop['status']] += 1
        row['physical_properties'] = props
        row['physical_review'] = {'reviewed_at': source['verification']['reviewed_at'],
                                  'source_pdf_sha256': pdf_hash, 'viewed_render_sha256': proof['sha256'],
                                  'scope': 'Six selected source facts; no photograph or current specimen measurements inferred.'}
        records.append({'catalog_id': key, 'source_url': url, 'source_pdf_sha256': pdf_hash,
                        'viewed_render_sha256': proof['sha256']})
    if dict(stats) != reviewed['field_status_counts']:
        raise ValueError('Reviewed field totals differ')
    return result, {'species': len(seen), 'field_status_counts': dict(stats), 'records': records}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--reviewed', type=Path, required=True)
    p.add_argument('--translations', type=Path, default=Path(__file__).with_name('extension-translations-zh.json'))
    p.add_argument('--pdf-dir', type=Path, required=True)
    p.add_argument('--evidence-root', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--publish-to-app', action='store_true')
    a = p.parse_args()
    read = lambda path: json.loads(path.read_text(encoding='utf-8'))
    catalog_path = a.repo / 'data/catalog.json'
    previous = digest(catalog_path)
    result, summary = prepare(read(catalog_path), read(a.reviewed), read(a.translations), a.pdf_dir, a.evidence_root)
    summary.update({'source_json_sha256': digest(a.reviewed), 'translations_sha256': digest(a.translations),
                    'previous_catalog_sha256': previous, 'generated_at': datetime.now(timezone.utc).isoformat(),
                    'training_or_accuracy_claim': False})
    stats = result.setdefault('physical_stats', {})
    stats.setdefault('extension_batches', []).append(deepcopy(summary))
    facts = [r for r in result['minerals'] if r.get('physical_properties')]
    stats['catalog_species_with_physical_facts'] = len(facts)
    counts = Counter(prop['status'] for row in facts for prop in row['physical_properties'].values())
    stats['catalog_field_status_counts'] = dict(counts)
    stats['verified_catalog_fields'] = counts['verified']
    catalog_bytes = (json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
    summary['catalog_sha256'] = hashlib.sha256(catalog_bytes).hexdigest()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    (a.output_dir / 'catalog.json').write_bytes(catalog_bytes)
    (a.output_dir / 'extension-import-report.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    if a.publish_to_app:
        if digest(catalog_path) != previous:
            raise ValueError('Catalog changed during review/import')
        manifest_path = a.repo / 'data/reference-manifest.json'
        manifest = read(manifest_path)
        files = [r for r in manifest['files'] if r['path'] == 'data/catalog.json']
        if len(files) != 1:
            raise ValueError('Exactly one catalog checksum required')
        files[0].update(bytes=len(catalog_bytes), sha256=summary['catalog_sha256'])
        manifest['counts']['catalog_species_with_physical_facts'] = len(facts)
        manifest['counts']['verified_catalog_fields'] = counts['verified']
        manifest['version'] = '2026-10-11'
        catalog_tmp = catalog_path.with_suffix('.json.tmp')
        manifest_tmp = manifest_path.with_suffix('.json.tmp')
        catalog_tmp.write_bytes(catalog_bytes)
        manifest_tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        # A partial interruption leaves a checksum failure, never silently accepted bytes.
        catalog_tmp.replace(catalog_path)
        manifest_tmp.replace(manifest_path)
    print(json.dumps({k: summary[k] for k in ('species', 'field_status_counts', 'catalog_sha256')}))


if __name__ == '__main__':
    main()
