#!/usr/bin/env python3
"""Attach reviewed name translations without changing official catalog records."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def reviewed_records(reviewed, catalog):
    review = reviewed.get('source_review', {})
    if reviewed.get('schema_version') != 1 or review.get('reviewer') != 'root' or review.get('actual_source_pages_read') is not True:
        raise ValueError('Explicit source-page review required')
    minerals = {row['id']: row for row in catalog['minerals']}
    records = reviewed.get('records')
    if not isinstance(records, list) or not records:
        raise ValueError('Reviewed names are missing')
    seen = set()
    for row in records:
        key, name = row.get('catalog_id'), row.get('name_zh')
        url = urlsplit(row.get('source_url', ''))
        if key in seen or key not in minerals or row.get('name_en') != minerals[key]['name_en']:
            raise ValueError('Duplicate or mismatched official mineral identity')
        if row.get('status') != 'reviewed' or not isinstance(name, str) or not re.fullmatch(r'[\u3400-\u9fff·（）()\- ]{1,60}', name):
            raise ValueError('Reviewed Chinese name required')
        if url.scheme != 'https' or not url.hostname or url.username or url.password or not row.get('source_title') or not row.get('source_doi') or not row.get('evidence_locator'):
            raise ValueError('Exact primary-source provenance required')
        seen.add(key)
    return deepcopy(records)


def prepare(catalog, reviewed):
    records = reviewed_records(reviewed, catalog)
    result = deepcopy(catalog)
    previous = result.get('reviewed_names_zh')
    overlay = {'schema_version': 1, 'records': records}
    if previous is not None:
        old = previous.get('records') if isinstance(previous, dict) and previous.get('schema_version') == 1 else None
        if not isinstance(old, list) or any(not isinstance(row, dict) or not isinstance(row.get('catalog_id'), str) for row in old):
            raise ValueError('Existing translation registry is malformed')
        current = {row['catalog_id']: row for row in records}
        if len({row['catalog_id'] for row in old}) != len(old) or any(current.get(row['catalog_id']) != row for row in old):
            raise ValueError('Preserve every existing translation and its provenance unchanged')
    result['reviewed_names_zh'] = overlay
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--reviewed', type=Path, default=Path(__file__).with_name('reviewed-names-zh.json'))
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--publish-to-app', action='store_true')
    a = p.parse_args()
    path = a.repo / 'data/catalog.json'
    before = path.read_bytes()
    catalog, names = json.loads(before), json.loads(a.reviewed.read_bytes())
    result = prepare(catalog, names)
    raw = (json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
    assert result['minerals'] == catalog['minerals']
    a.output_dir.mkdir(parents=True, exist_ok=False)
    (a.output_dir / 'catalog.json').write_bytes(raw)
    report = {'reviewed_names': len(names['records']), 'all_official_rows_unchanged': True,
              'reviewed_source_sha256': hashlib.sha256(a.reviewed.read_bytes()).hexdigest(),
              'previous_catalog_sha256': hashlib.sha256(before).hexdigest(),
              'catalog_sha256': hashlib.sha256(raw).hexdigest(), 'model_or_training_change': False}
    if a.publish_to_app:
        if path.read_bytes() != before:
            raise ValueError('Catalog changed during import')
        mp = a.repo / 'data/reference-manifest.json'
        manifest = json.loads(mp.read_bytes())
        items = [row for row in manifest['files'] if row['path'] == 'data/catalog.json']
        if len(items) != 1:
            raise ValueError('Exactly one catalog checksum required')
        items[0].update(bytes=len(raw), sha256=report['catalog_sha256'])
        path.write_bytes(raw)
        mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (a.output_dir / 'name-import-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
