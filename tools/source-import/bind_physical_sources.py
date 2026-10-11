"""Enrich original facts with their already reviewed PDF hash; no fact edits."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path


def bound_properties(record):
    props = deepcopy(record['properties'])
    for prop in props.values():
        if prop['source_url'] != record['source_url']:
            raise ValueError('Physical field source identity differs')
        prop['source_pdf_sha256'] = record['source_pdf_sha256']
    return props


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--sources', type=Path, required=True)
    a = p.parse_args()
    physical = json.loads((a.sources / 'physical-properties.json').read_text())
    kb_path = a.repo / 'data/minerals.js'
    code = kb_path.read_text(); marker = 'window.MINERAL_KB='
    start = code.index(marker) + len(marker)
    kb, length = json.JSONDecoder().raw_decode(code[start:])
    catalog_path = a.repo / 'data/catalog.json'
    catalog = json.loads(catalog_path.read_text())
    by_name = {row['name_en'].casefold(): row for row in catalog['minerals']}
    for record in physical['records']:
        raw = (a.sources / 'physical-source-pdfs' / (record['key'] + '.pdf')).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record['source_pdf_sha256']:
            raise ValueError('Original PDF changed')
        props = bound_properties(record)
        old = kb[record['key']]['verified_properties']
        if old not in (record['properties'], props):
            raise ValueError('Original KB facts changed: ' + record['key'])
        kb[record['key']]['verified_properties'] = deepcopy(props)
        row = by_name.get(record['name_en'].casefold())
        if row:
            if row['physical_properties'] not in (record['properties'], props):
                raise ValueError('Original catalog facts changed: ' + record['key'])
            row['physical_properties'] = deepcopy(props)
    # Preserve all other assignments, annotations and model metadata byte-for-byte.
    kb_path.write_text(code[:start] + json.dumps(kb, ensure_ascii=False, separators=(',', ':')) + code[start + length:])
    catalog_bytes = (json.dumps(catalog, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
    manifest_path = a.repo / 'data/reference-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(x for x in manifest['files'] if x['path'] == 'data/catalog.json')
    entry.update(bytes=len(catalog_bytes), sha256=hashlib.sha256(catalog_bytes).hexdigest())
    catalog_path.write_bytes(catalog_bytes)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'original_label_sources_bound': len(physical['records']), 'facts_changed': False}))


if __name__ == '__main__':
    main()
