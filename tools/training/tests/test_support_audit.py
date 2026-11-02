"""Synthetic support-audit guards; never load a real dataset or ML framework."""
import copy
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('support_audit', Path(__file__).parents[1] / 'support_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fixture():
    rows = []
    for label in range(2):
        for fold in (0, 1):
            for _ in range(3):
                index = len(rows)
                rows.append({'id': f'row{index}', 'index': index, 'component_id': f'group{index}',
                             'species_target_id': f'class{label}', 'label': label, 'role': 'train',
                             'fold': fold, 'blind_eligible': False, 'phase_assay_confirmed': False,
                             'physical_specimen_independence_proven': False})
    views = {}
    for fold in (0, 1):
        outer = [i for i, r in enumerate(rows) if r['fold'] == fold]
        other = [i for i, r in enumerate(rows) if r['fold'] != fold]
        inner = other[::3]
        views[str(fold)] = {'outer_indices': outer, 'inner_indices': inner,
                            'fit_indices': [i for i in other if i not in inner], 'append_fit_indices': []}
    return rows, views


class SupportAuditTests(unittest.TestCase):
    def test_counts_and_truth_boundary(self):
        rows, views = fixture(); result = audit.audit_support(rows, views)
        self.assertEqual((result['photos'], result['classes'], result['source_proxy_groups']), (12, 2, 12))
        self.assertEqual(result['classes_with_at_most_two_fit_proxy_groups_in_either_fold'], 2)
        self.assertFalse(result['independent_evaluation_eligible'])
        self.assertFalse(result['physical_specimen_80_10_10_partition_proven'])
        self.assertIsNone(result['independent_Kappa'])

    def test_fit_only_does_not_enter_inner_or_outer(self):
        rows, views = fixture(); index = len(rows)
        row = dict(rows[0], id='append', index=index, component_id='append', fold=None, train_only=True)
        rows.append(row)
        for view in views.values():
            view['fit_indices'].append(index); view['append_fit_indices'].append(index)
        self.assertEqual(audit.audit_support(rows, views)['fit_only_append_photos'], 1)
        views['0']['fit_indices'].remove(index); views['0']['inner_indices'].append(index)
        with self.assertRaisesRegex(ValueError, 'Fit-only'): audit.audit_support(rows, views)

    def test_component_cannot_cross_roles(self):
        rows, views = fixture(); rows[3]['component_id'] = rows[0]['component_id']
        with self.assertRaisesRegex(ValueError, 'crosses view'): audit.audit_support(rows, views)

    def test_class_conflict_is_not_silently_counted(self):
        rows, views = fixture(); rows[6]['component_id'] = rows[0]['component_id']
        with self.assertRaisesRegex(ValueError, 'Conflicting component'): audit.audit_support(rows, views)

    def test_no_blind_manifest_or_boolean_indices(self):
        rows, views = fixture(); rows[0]['blind_eligible'] = True
        with self.assertRaisesRegex(ValueError, 'blind-test'): audit.audit_support(rows, views)
        rows, views = fixture(); views['0']['fit_indices'][0] = True
        with self.assertRaisesRegex(ValueError, 'view index'): audit.audit_support(rows, views)

    def test_string_evidence_flags_are_rejected(self):
        for field in ('train_only', 'phase_assay_confirmed', 'physical_specimen_independence_proven'):
            rows, views = fixture(); rows[0][field] = 'false'
            with self.assertRaises(ValueError): audit.audit_support(rows, views)

    def test_missing_or_invalid_fold_is_a_contract_error(self):
        for value in ('missing', None, True, 2, '0'):
            rows, views = fixture()
            if value == 'missing':
                rows[0]['train_only'] = True; del rows[0]['fold']
            else:
                rows[0]['fold'] = value
            with self.assertRaisesRegex(ValueError, 'development fold'): audit.audit_support(rows, views)

    def test_omission_and_outer_reassignment_rejected(self):
        rows, views = fixture(); views['0']['fit_indices'].pop()
        with self.assertRaisesRegex(ValueError, 'omission'): audit.audit_support(rows, views)
        rows, views = fixture(); rows[0]['fold'] = 1
        with self.assertRaisesRegex(ValueError, 'outer-fold'): audit.audit_support(rows, views)

    def test_counting_does_not_mutate_inputs_and_is_order_invariant_for_views(self):
        rows, views = fixture(); original = copy.deepcopy((rows, views))
        first = audit.audit_support(rows, views)
        self.assertEqual((rows, views), original)
        for view in views.values():
            for values in view.values(): values.reverse()
        self.assertEqual(audit.audit_support(rows, views), first)

    def test_pins_and_budget_checked_before_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'meta.json'; path.write_bytes(b'{}')
            digest = hashlib.sha256(b'{}').hexdigest()
            self.assertEqual(audit.read_pinned(path, digest, 2), b'{}')
            with self.assertRaisesRegex(ValueError, 'budget'): audit.read_pinned(path, digest, 1)
            with self.assertRaisesRegex(ValueError, 'changed'): audit.read_pinned(path, '0' * 64, 2)
        with self.assertRaisesRegex(ValueError, 'Duplicate'): audit.decode_json('{"a":1,"a":2}')


if __name__ == '__main__':
    unittest.main()
