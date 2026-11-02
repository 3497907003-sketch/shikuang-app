#!/usr/bin/env python3
"""Count support in explicitly pinned, already exposed development metadata.

No image, weight, prediction, source-manifest or independent-test file is opened.
Source-proxy components and claimed review flags are not physical-specimen proof.
This audit neither repartitions data nor makes samples eligible for evaluation.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read_pinned(path, expected_sha256, limit):
    require(isinstance(expected_sha256, str) and len(expected_sha256) == 64
            and all(c in '0123456789abcdef' for c in expected_sha256), 'Invalid input SHA256')
    with Path(path).open('rb') as handle:
        data = handle.read(limit + 1)
    require(len(data) <= limit, 'Metadata exceeds the explicit byte budget')
    require(hashlib.sha256(data).hexdigest() == expected_sha256, 'Pinned metadata changed')
    return data


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON object key')
        result[key] = value
    return result


def decode_json(data):
    return json.loads(data, object_pairs_hook=unique_object)


def audit_support(rows, views, minimum_groups=10):
    require(type(minimum_groups) is int and minimum_groups >= 10,
            'Planning minimum must be at least ten; it is not an accuracy guarantee')
    require(isinstance(rows, list) and rows, 'No development rows')
    ids, components, target_labels, labels = set(), defaultdict(list), {}, {}
    counts = defaultdict(list)
    for index, row in enumerate(rows):
        require(isinstance(row, dict) and row.get('index') == index
                and type(row.get('index')) is int, 'Manifest indices must match their row order')
        for field in ('id', 'component_id', 'species_target_id'):
            require(isinstance(row.get(field), str) and row[field].strip(), 'Missing development identity')
        require(row['id'] not in ids, 'Repeated development row ID')
        ids.add(row['id'])
        target, label = row['species_target_id'], row.get('label')
        require(type(label) is int and label >= 0, 'Invalid class index')
        require(target_labels.setdefault(target, label) == label
                and labels.setdefault(label, target) == target, 'Class identity/order conflict')
        require(row.get('role') == 'train' and row.get('blind_eligible') is False,
                'This tool accepts exposed development metadata only, never a blind-test manifest')
        require(row.get('train_only') is None or type(row['train_only']) is bool,
                'Fit-only flag must be Boolean, null or absent')
        valid_fold = (type(row.get('fold')) is int and row['fold'] in (0, 1)
                      or row.get('fold') is None and row.get('train_only') is True)
        require('fold' in row and valid_fold, 'Unknown development fold/fit-only role')
        require(not row.get('train_only') or row.get('fold') is None, 'Fit-only row has an outer fold')
        for field in ('phase_assay_confirmed', 'physical_specimen_independence_proven'):
            require(type(row.get(field)) is bool, 'Missing explicit evidence flag')
        components[row['component_id']].append(row)
        counts[target].append(row)
    require(set(labels) == set(range(len(labels))), 'Class indices must be contiguous')
    for members in components.values():
        require(len({r['species_target_id'] for r in members}) == 1, 'Conflicting component labels')
    require(isinstance(views, dict) and set(views) == {'0', '1'}, 'Expected both fixed development folds')
    per_fold = {}
    for fold, view in views.items():
        require(isinstance(view, dict) and set(view) == {
            'fit_indices', 'inner_indices', 'outer_indices', 'append_fit_indices'}, 'Unknown view schema')
        selections = {}
        for key, values in view.items():
            require(isinstance(values, list) and all(type(i) is int and 0 <= i < len(rows) for i in values)
                    and len(set(values)) == len(values), 'Invalid or duplicate view index')
            selections[key] = set(values)
        roles = ('fit', 'inner', 'outer')
        role_sets = [selections[role + '_indices'] for role in roles]
        require(set.union(*role_sets) == set(range(len(rows)))
                and sum(map(len, role_sets)) == len(rows), 'View omission or overlap')
        fit_only = {i for i, row in enumerate(rows) if row.get('train_only') is True}
        require(selections['append_fit_indices'] == fit_only
                and fit_only <= selections['fit_indices'], 'Fit-only append escaped the fit partition')
        require(selections['outer_indices'] == {i for i, row in enumerate(rows) if row['fold'] == int(fold)},
                'Fixed outer-fold membership changed')
        owner = {}
        per_fold[fold] = {}
        for role in roles:
            selected = [rows[i] for i in selections[role + '_indices']]
            by_class = defaultdict(set)
            for row in selected:
                component = row['component_id']
                require(owner.setdefault(component, role) == role, 'Source-proxy component crosses view roles')
                by_class[row['species_target_id']].add(component)
            per_fold[fold][role] = {target: len(by_class[target]) for target in counts}
    report_rows = []
    for target, selected in sorted(counts.items()):
        groups = {r['component_id'] for r in selected}
        fit = {fold: per_fold[fold]['fit'][target] for fold in ('0', '1')}
        report_rows.append({
            'species_target_id': target, 'class_index': target_labels[target], 'photos': len(selected),
            'source_proxy_groups': len(groups),
            'fit_only_append_photos': sum(r.get('train_only') is True for r in selected),
            'claimed_phase_assay_confirmed_photos': sum(r['phase_assay_confirmed'] for r in selected),
            'claimed_physical_independence_photos': sum(r['physical_specimen_independence_proven'] for r in selected),
            'fixed_fold_fit_proxy_groups': fit,
            'fixed_fold_inner_proxy_groups': {fold: per_fold[fold]['inner'][target] for fold in ('0', '1')},
            'fixed_fold_outer_proxy_groups': {fold: per_fold[fold]['outer'][target] for fold in ('0', '1')},
            'fewest_fit_proxy_groups': min(fit.values()),
            'additional_proxy_groups_to_planning_minimum': max(0, minimum_groups - len(groups)),
        })
    priority = sorted(report_rows, key=lambda r: (
        r['fewest_fit_proxy_groups'], r['source_proxy_groups'], r['species_target_id']))
    return {
        'schema': 'shikuang-development-support-audit-v1',
        'scope': 'Exposed development metadata counts; not physical specimen or accuracy validation.',
        'photos': len(rows), 'classes': len(counts), 'source_proxy_groups': len(components),
        'fit_only_append_photos': sum(r.get('train_only') is True for r in rows),
        'planning_minimum_proxy_groups_per_class': minimum_groups,
        'planning_minimum_is_accuracy_guarantee': False,
        'classes_below_planning_minimum_total_proxy_groups': sum(len({r['component_id'] for r in v}) < minimum_groups for v in counts.values()),
        'classes_with_at_most_two_fit_proxy_groups_in_either_fold': sum(r['fewest_fit_proxy_groups'] <= 2 for r in report_rows),
        'classes_with_at_most_five_fit_proxy_groups_in_either_fold': sum(r['fewest_fit_proxy_groups'] <= 5 for r in report_rows),
        'classes_with_zero_inner_support_in_either_fold': sum(any(per_fold[f]['inner'][t] == 0 for f in ('0', '1')) for t in counts),
        'claimed_phase_assay_confirmed_photos': sum(r['phase_assay_confirmed'] for r in rows),
        'claimed_physical_independence_photos': sum(r['physical_specimen_independence_proven'] for r in rows),
        'independent_evaluation_eligible': False, 'independent_Kappa': None,
        'physical_specimen_80_10_10_partition_proven': False,
        'roles_or_data_changed': False,
        'priority_basis': 'Fewest fixed-fold fit source-proxy groups, then total proxy groups. No outcomes or predictions used.',
        'per_class': priority,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('manifest', 'views', 'output'):
        parser.add_argument('--' + field, required=True, type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--views-sha256', required=True)
    parser.add_argument('--minimum-groups', type=int, default=10)
    args = parser.parse_args()
    require(not args.output.exists(), 'Refuse to overwrite an audit')
    require(args.output.resolve() not in {args.manifest.resolve(), args.views.resolve()}, 'Output aliases an input')
    manifest = read_pinned(args.manifest, args.manifest_sha256, 4 * 1024 * 1024)
    views = read_pinned(args.views, args.views_sha256, 512 * 1024)
    rows = [decode_json(line) for line in manifest.splitlines()]
    result = audit_support(rows, decode_json(views), args.minimum_groups)
    result['inputs'] = {'manifest_sha256': args.manifest_sha256, 'manifest_bytes': len(manifest),
                        'views_sha256': args.views_sha256, 'views_bytes': len(views)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2); handle.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'per_class'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
