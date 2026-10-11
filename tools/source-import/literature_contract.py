#!/usr/bin/env python3
"""Fail-closed source and explicit Root-approval contract for literature paraphrases.

Verification is correspondence to an explicitly approved literature source, not a
new experiment, exhaustive locality inventory, specimen origin, or ML accuracy.
The trusted caller must independently confirm the root ledger SHA. A JSON role
string is not authentication. Unit fixtures are never publishable.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import pdfplumber

FIELDS = ('occurrence', 'distribution')
DECISIONS = {'source_checked_paraphrase_proposal', 'unavailable', 'needs_terminology_review'}
LEDGER_SCHEMA = 'shikuang.root.field-review-ledger.v1'
GEO_SCOPE = 'nonexhaustive examples reported in this particular source version, not a current complete inventory'
GEO_NOTICE = '仅列举该版文献中的典型分布，非完整或实时地点清单；不代表上传图片中标本的产地。'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha(value):
    """UTF-8, sorted keys, no whitespace, non-ASCII literal, disallow NaN."""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def value_sha(value):
    require(type(value) is str, 'Override value must be a string')
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON member: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda token: (_ for _ in ()).throw(ValueError('Nonfinite JSON: ' + token)))


def inside_file(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    require(path.is_relative_to(root) and path.is_file(), 'Missing/outside private evidence root: ' + str(path))
    return path


def checked_file(path, expected, root):
    path = inside_file(path, root)
    require(type(expected) is str and re.fullmatch('[a-f0-9]{64}', expected), 'Invalid SHA-256')
    require(sha(path) == expected, 'Private file checksum mismatch: ' + str(path))
    return path


def rectangle(value):
    require(type(value) is list and len(value) == 4 and all(type(x) in (float, int) and math.isfinite(x) for x in value), 'Invalid crop rectangle')
    require(value[0] >= 0 and value[1] >= 0 and value[2] > value[0] and value[3] > value[1], 'Invalid crop bounds')
    return value


def verify_evidence(record, prop, index, evidence_root, page_bounds=None):
    require(type(prop.get('source_page')) is int and prop['source_page'] > 0, 'Invalid source page')
    pages = prop.get('source_pages')
    require(type(pages) is list and pages and len(pages) == len(set(pages)) and
            all(type(p) is int and 1 <= p <= record['pdf_page_count'] for p in pages) and prop['source_page'] in pages, 'Invalid source page population')
    proofs = prop.get('evidence')
    require(type(proofs) is list and proofs, 'Missing actually viewed evidence')
    normalized, seen = [], set()
    # Supplemental slots inherit exact PDF identity from the hash-bound physical
    # decision registry; their original schema does not repeat URL/PDF SHA.
    for proof in proofs:
        require(proof.get('actual_image_viewed') is True, 'Evidence not actually viewed')
        require('key' not in proof or proof['key'] == record['key'], 'Evidence explicit source key mismatch')
        page = proof.get('source_page')
        require(type(page) is int and page in pages, 'Evidence page outside declared pages')
        crop_path = checked_file(proof.get('path', ''), proof.get('sha256'), evidence_root)
        sheet_proof = proof.get('displayed_in_sheet')
        if sheet_proof:
            require(sheet_proof.get('actual_image_viewed') is True, 'Sheet not actually viewed')
            sheet_path = checked_file(sheet_proof.get('path', ''), sheet_proof.get('sha256'), evidence_root)
            sheets = list(index['sheets']) + [index['supplemental_second_pages']]
            matches = [s for s in sheets if Path(s['path']).resolve() == sheet_path and s['sha256'] == sheet_proof['sha256']]
            require(len(matches) == 1 and matches[0].get('actual_image_viewed') is True, 'Missing/ambiguous viewed sheet')
            position = sheet_proof.get('position')
            require(type(position) is int and position > 0, 'Invalid sheet slot position')
            require('position' not in proof or proof['position'] == position, 'Evidence/sheet slot position mismatch')
            slots = [s for s in matches[0]['sources'] if s.get('position') == position]
            require(len(slots) == 1, 'Missing/ambiguous exact sheet slot')
            slot = slots[0]
            require(slot.get('key') == record['key'] and slot.get('source_page') == page, 'Sheet slot source/page mismatch')
            crop = rectangle(proof.get('crop_points'))
            if page_bounds is not None:
                bounds = page_bounds[page - 1]
                require(crop[2] <= bounds[2] and crop[3] <= bounds[3], 'Crop outside exact PDF page')
            require(slot.get('crop_points') == crop and slot.get('crop_sha256', slot.get('sha256')) == proof['sha256'], 'Crop checksum/coordinates mismatch')
            if 'crop_sha256' in slot:
                require(slot.get('source_url') == record['source_url'] and slot.get('source_pdf_sha256') == record['source_pdf_sha256'], 'Sheet PDF identity mismatch')
            else:
                require(slot.get('actual_image_viewed') is True and Path(slot['path']).resolve() == crop_path, 'Supplemental source path/view mismatch')
            field_crop = proof.get('field_crop_points')
            if field_crop is not None:
                rectangle(field_crop)
                require(crop[0] <= field_crop[0] < field_crop[2] <= crop[2] and crop[1] <= field_crop[1] < field_crop[3] <= crop[3], 'Field crop outside actually viewed crop')
            normalized.append({'key': record['key'], 'source_url': record['source_url'], 'source_pdf_sha256': record['source_pdf_sha256'],
                               'source_page': page, 'crop_points': crop, 'field_crop_points': field_crop,
                               'crop_sha256': proof['sha256'], 'sheet_sha256': sheet_proof['sha256'], 'position': position,
                               'actual_image_viewed': True})
        else:
            matches = [p for p in index['additional_full_page_views'] if p.get('key') == record['key'] and
                       p.get('source_page') == page and Path(p['path']).resolve() == crop_path and p['sha256'] == proof['sha256']]
            require(len(matches) == 1 and matches[0].get('actual_image_viewed') is True, 'Full-page view identity mismatch')
            normalized.append({'key': record['key'], 'source_url': record['source_url'], 'source_pdf_sha256': record['source_pdf_sha256'],
                               'source_page': page, 'render_scope': 'complete_pdf_page', 'render_sha256': proof['sha256'], 'actual_image_viewed': True})
        seen.add(page)
    require(seen == set(pages), 'Not all declared source pages actually viewed')
    return normalized


def validate_inputs(proposal_path, index_path, physical_path, catalog_path, pdf_dir, evidence_root):
    proposal, index, physical, catalog = map(read_json, [proposal_path, index_path, physical_path, catalog_path])
    require(proposal.get('schema') == 'shikuang.private.detailed-occurrence-proposal.v1' and index.get('schema') == 'shikuang.private.actual-source-render-index.v1', 'Unknown proposal/render schema')
    require(proposal.get('source_only') is True and index.get('source_only') is True, 'Expected private source-only proposals')
    require(proposal['render_index_sha256'] == sha(index_path), 'Render index changed')
    require(proposal['current_physical_decision_sha256'] == index['current_physical_decision_sha256'] == sha(physical_path), 'Physical source registry changed')
    physical_by_key = {r['key']: r for r in physical['records']}
    catalog_by_key = {r['id']: r for r in catalog['minerals']}
    require(len(physical_by_key) == len(physical['records']) and len(catalog_by_key) == len(catalog['minerals']), 'Duplicate source/catalog identity')
    fields = {}
    for record in proposal['records']:
        key = record.get('key')
        require(type(key) is str and re.fullmatch('ima-[a-z0-9-]+', key), 'Invalid IMA key')
        require(key in physical_by_key and key in catalog_by_key, 'Unknown exact IMA/catalog identity')
        source, entity = physical_by_key[key], catalog_by_key[key]
        require(source.get('ima_species') is True and entity['name_en'] == record['name_en'] == source['name_en'], 'IMA species/name mismatch')
        require(entity.get('handbook_url') == source['source_url'] == record['source_url'], 'Exact catalog/source URL mismatch')
        require(record['source_pdf_sha256'] == source['source_pdf_sha256'], 'Physical source PDF checksum mismatch')
        checked_file(Path(pdf_dir) / (key + '.pdf'), record['source_pdf_sha256'], pdf_dir)
        require(type(record.get('pdf_page_count')) is int and record['pdf_page_count'] >= 1, 'Invalid PDF page count')
        with pdfplumber.open(Path(pdf_dir) / (key + '.pdf')) as pdf:
            require(len(pdf.pages) == record['pdf_page_count'], 'Declared PDF page count differs from exact source bytes')
            page_bounds = [list(page.bbox) for page in pdf.pages]
        require(set(record['properties']) == set(FIELDS), 'Unexpected/missing source field')
        total_words = 0
        for field in FIELDS:
            prop = record['properties'][field]
            require((key, field) not in fields, 'Duplicate mineral field')
            require(prop.get('decision') in DECISIONS and prop.get('automatic_import_allowed') is False and prop.get('app_imported') is False, 'Unknown/already-imported proposal state')
            require(prop.get('source_url') == record['source_url'] and prop.get('source_pdf_sha256') == record['source_pdf_sha256'], 'Field PDF identity mismatch')
            require(Path(prop.get('render_index_path', '')).resolve() == Path(index_path).resolve() and prop.get('render_index_sha256') == sha(index_path), 'Field index path/checksum mismatch')
            excerpt = prop.get('original_excerpt')
            require(type(excerpt) is str and len(excerpt) <= 400 and len(excerpt.split()) <= 12, 'Source excerpt exceeds short-anchor limit')
            total_words += len(excerpt.split())
            if prop['decision'] == 'unavailable':
                require(prop.get('value_zh') is None and not excerpt and prop.get('source_statement_status') == 'not_provided_on_source_page', 'Unavailable field contains invented facts')
            else:
                require(prop.get('source_statement_status') == 'actual_source_pixels_checked', 'Source pixels not checked')
                require(type(prop.get('value_zh')) is str and prop['value_zh'].strip() and 1 <= len(prop['value_zh']) <= 700, 'Missing/overlong Chinese proposal')
            if field == 'distribution':
                require(prop.get('specimen_origin_inference_allowed') is False and prop.get('geography_scope') == GEO_SCOPE, 'Distribution scope/origin inference changed')
            evidence = verify_evidence(record, prop, index, evidence_root, page_bounds)
            fields[(key, field)] = {'record': record, 'prop': prop, 'entity': entity, 'field_sha256': canonical_sha(prop),
                                    'evidence': evidence, 'evidence_sha256': canonical_sha(evidence)}
        require(total_words <= 24, 'Combined source excerpt limit exceeded')
    viewed_documents = {}
    documents = list(index['sheets']) + [index['supplemental_second_pages']] + index['additional_full_page_views']
    for document in documents:
        require(document.get('actual_image_viewed') is True, 'Index document not actually viewed')
        path = checked_file(document['path'], document['sha256'], evidence_root)
        require(str(path) not in viewed_documents, 'Duplicate viewed document path')
        viewed_documents[str(path)] = document['sha256']
    return {'unit_fixture': False, 'proposal_sha256': sha(proposal_path), 'render_index_sha256': sha(index_path),
            'physical_decision_sha256': sha(physical_path), 'fields': fields, 'viewed_documents': viewed_documents}


def draft_ledger(inputs):
    return {'schema': LEDGER_SCHEMA, 'reviewer': 'root', 'unit_fixture': inputs.get('unit_fixture', False),
            'approval_policy': 'explicit manual field decisions; trusted caller must independently confirm ledger SHA',
            **{k: inputs[k] for k in ('proposal_sha256', 'render_index_sha256', 'physical_decision_sha256')},
            'decisions': [{'key': key, 'field': field, 'decision': 'hold',
                           'source_url': item['record']['source_url'], 'source_pdf_sha256': item['record']['source_pdf_sha256'],
                           'original_field_sha256': item['field_sha256'], 'evidence_sha256': item['evidence_sha256'],
                           'manual_actual_source_review': False, 'review_note': ''}
                          for (key, field), item in inputs['fields'].items()]}


def stage_import(inputs, ledger_path, trusted_ledger_sha256, unit_fixture=False):
    require(inputs.get('unit_fixture', False) is unit_fixture, 'Fixture inputs cannot enter real source import, or vice versa')
    require(sha(ledger_path) == trusted_ledger_sha256, 'Root ledger checksum differs from independently trusted approval')
    ledger = read_json(ledger_path)
    require(ledger.get('schema') == LEDGER_SCHEMA and ledger.get('reviewer') == 'root', 'Unexpected ledger authority/schema')
    require(ledger.get('unit_fixture') is unit_fixture, 'Unit fixture ledger cannot enter real source import')
    for key in ('proposal_sha256', 'render_index_sha256', 'physical_decision_sha256'):
        require(ledger.get(key) == inputs[key], 'Ledger input changed: ' + key)
    root_viewed_hashes = set()
    has_approvals = any(d.get('decision') in {'approve', 'approve_override'} for d in ledger.get('decisions', []))
    if has_approvals and not unit_fixture:
        require(ledger.get('automatic_factual_approval') is False, 'Automatic factual approval is forbidden')
        views = ledger.get('root_viewed_evidence')
        require(type(views) is list and views, 'Missing root actual source view record')
        paths = set()
        for view in views:
            path = str(Path(view.get('path', '')).resolve())
            require(path in inputs['viewed_documents'] and path not in paths and
                    view.get('sha256') == inputs['viewed_documents'][path] and
                    view.get('root_actual_view_completed') is True, 'Root actual view path/hash/decision mismatch')
            paths.add(path)
            root_viewed_hashes.add(view['sha256'])
    decisions = {}
    for decision in ledger.get('decisions', []):
        identity = (decision.get('key'), decision.get('field'))
        require(identity in inputs['fields'] and identity not in decisions, 'Unknown/duplicate ledger field')
        item = inputs['fields'][identity]
        for ledger_key, expected in [('source_url', item['record']['source_url']), ('source_pdf_sha256', item['record']['source_pdf_sha256']),
                                     ('original_field_sha256', item['field_sha256']), ('evidence_sha256', item['evidence_sha256'])]:
            require(decision.get(ledger_key) == expected, 'Ledger field binding mismatch: ' + ledger_key)
        require(decision.get('decision') in {'approve', 'approve_override', 'hold', 'unavailable', 'reject'}, 'Unknown root decision')
        decisions[identity] = decision
    records, withheld = {}, []
    for identity, item in inputs['fields'].items():
        key, field = identity
        prop, source, entity = item['prop'], item['record'], item['entity']
        decision = decisions.get(identity)
        if decision is None or decision['decision'] in {'hold', 'unavailable', 'reject'}:
            withheld.append({'key': key, 'field': field, 'source_decision': prop['decision'],
                             'root_decision': decision['decision'] if decision else 'not_reviewed', 'display_as_verified': False})
            continue
        require(prop['decision'] == 'source_checked_paraphrase_proposal', 'Unverified/terminology/unavailable proposal cannot be approved')
        require(decision.get('manual_actual_source_review') is True and type(decision.get('review_note')) is str and decision['review_note'].strip(), 'Missing explicit manual root review')
        if not unit_fixture:
            require(all(proof.get('sheet_sha256', proof.get('render_sha256')) in root_viewed_hashes for proof in item['evidence']), 'Root did not actually view every approved field evidence document')
        value = prop['value_zh']
        override = None
        if decision['decision'] == 'approve_override':
            override = decision.get('override')
            require(type(override) is dict and override.get('reviewer') == 'root' and override.get('manual_actual_source_review') is True, 'Missing separate root override review')
            require(override.get('original_field_sha256') == item['field_sha256'] and override.get('evidence_sha256') == item['evidence_sha256'], 'Override original/evidence binding mismatch')
            require(override.get('source_url') == source['source_url'] and override.get('source_pdf_sha256') == source['source_pdf_sha256'], 'Override exact source identity mismatch')
            value = override.get('value_zh')
            require(type(value) is str and value.strip() and 1 <= len(value) <= 700 and override.get('value_sha256') == value_sha(value), 'Override value changed/missing')
            require(type(override.get('review_note')) is str and override['review_note'].strip(), 'Missing override source review note')
        else:
            require('override' not in decision, 'Unsigned override attached to ordinary approval')
        entry = records.setdefault(key, {'id': key, 'name_en': entity['name_en'], 'ima_number': entity.get('ima_number'), 'literature_properties': {}})
        fact = {'status': 'verified', 'truth_scope': 'root-reviewed Chinese paraphrase of this literature source; no experimental verification claim',
                'value_zh': value, 'source_url': source['source_url'], 'source_pdf_sha256': source['source_pdf_sha256'],
                'source_page': prop['source_page'], 'source_pages': prop['source_pages'], 'original_excerpt': prop['original_excerpt'],
                'proposal_field_sha256': item['field_sha256'], 'evidence_sha256': item['evidence_sha256'],
                'render_index_sha256': inputs['render_index_sha256'], 'root_ledger_sha256': trusted_ledger_sha256,
                'review_note': decision['review_note'], 'source_permission_scope': source['source_permission_scope']}
        if override:
            fact['root_override'] = {'original_proposal_value_sha256': value_sha(prop['value_zh']),
                                     'override_value_sha256': override['value_sha256'], 'review_note': override['review_note']}
        if field == 'distribution':
            fact.update(geography_scope=GEO_SCOPE, specimen_origin_inference_allowed=False, display_notice_zh=GEO_NOTICE)
        entry['literature_properties'][field] = fact
    return {'schema': 'shikuang.private.root-approved-literature-staging.v1', 'unit_fixture': unit_fixture,
            'production_imported': False, 'automatically_approved': False, 'public_release_allowed': False,
            'source_text_policy': 'Short English anchors and independently reviewed Chinese paraphrases only; no PDFs, rendered pixels or long transcription distributed.',
            'root_ledger_sha256': trusted_ledger_sha256, 'counts': {'approved_fields': sum(len(r['literature_properties']) for r in records.values()),
                                                               'withheld_fields': len(withheld)},
            'records': list(records.values()), 'withheld': withheld}



# Frozen from the independently tested private prototype; never auto-approves facts.
# Prototype SHA-256: 3b61e84704bb5aeda96b4c4f69f51f467966bbed1ecef9102f278911a2b603ea
