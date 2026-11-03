"""Source authority, cumulative preservation and rejected field mutations only."""
import copy,json,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import book56_increment as importer
import book56_profile as profile
import book_evidence_import as core
REPO=HERE.parents[1];ROOT=REPO.parents[1];REVIEW=ROOT/'work/resume56-book-evidence-audit-001';BASE=REVIEW/'baseline001/data'
class Book56Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate=(REVIEW/'book56-candidates.Root-review-pending.json').read_bytes();cls.approval=(REVIEW/'ROOT-SECONDARY-SOURCE-REVIEW.json').read_bytes()
        cls.catalog_raw=(BASE/'catalog.json').read_bytes();cls.manifest_raw=(BASE/'reference-manifest.json').read_bytes();cls.catalog=json.loads(cls.catalog_raw)
        cls.incoming=importer.public_increment(cls.catalog,cls.candidate,cls.approval)
    def test_original_pending_candidate_requires_exact_separate_Root_authority(self):
        proposal,approval=importer.approved_inputs(self.candidate,self.approval);self.assertFalse(proposal['approved_by_Root']);self.assertEqual(set(approval['approved_secondary_statement_ids']),set(profile.ROWS))
        for inputs in [(self.candidate+b' ',self.approval),(self.candidate,self.approval+b' ')]:
            with self.assertRaises(ValueError):importer.approved_inputs(*inputs)
    def test_cumulative_append_preserves190_records_primary_bytes_and_all_owner_metadata(self):
        a=importer.prepare(self.catalog_raw,self.manifest_raw,self.candidate,self.approval);b=importer.prepare(self.catalog_raw,self.manifest_raw,self.candidate,self.approval);self.assertEqual(a,b)
        raw,manifest,o,_=a;old=self.catalog['reviewed_book_evidence'];self.assertEqual(o['records'][:190],old['records']);self.assertEqual(o['withheld'],old['withheld'])
        self.assertEqual(importer.value_bytes(raw,'minerals'),importer.value_bytes(self.catalog_raw,'minerals'))
        for before,after in zip(old['books'],o['books']):
            self.assertEqual({k:v for k,v in before.items()if k!='subjects'},{k:v for k,v in after.items()if k!='subjects'});self.assertEqual(after['subjects'][:len(before['subjects'])],before['subjects'])
        self.assertEqual(len(o['books']),11);self.assertEqual(o['counts']['reviewed_source_statements'],200)
        self.assertEqual(len({r['catalog_id']for r in o['records']}),71);self.assertEqual(o['counts']['selected_source_pages'],25)
        item=next(x for x in json.loads(manifest)['files']if x['path']=='data/catalog.json');self.assertEqual(item['sha256'],core.digest(raw))
        with self.assertRaises(ValueError):importer.prepare(raw,manifest,self.candidate,self.approval)
    def test_exact_Mohs_not_density_or_ratio_and_qualitative_units_cannot_change(self):
        for cid in profile.ROWS:
            row=profile.ROWS[cid]
            if row['field']=='hardness':self.assertEqual((row['unit'],row['hardness_scale']),('Mohs','Mohs'));self.assertIn('ordinal_scale_not_a_ratio_scale',row['limits'])
            else:self.assertIsNone(row['unit']);self.assertIsNone(row['hardness_scale'])
            for key,value in [('unit','g/cm³'),('hardness_scale',None if row['field']=='hardness'else'Mohs'),('quantity_kind','mass_density_measured'),('value','当前上传标本已确认')]:
                changed=copy.deepcopy(row);changed[key]=value
                with self.subTest(cid=cid,key=key),self.assertRaises(ValueError):profile.validate_row(changed)
    def test_wrong_source_page_review_conditions_and_unreviewed_names_fail_closed(self):
        row=next(iter(profile.ROWS.values()))
        for change in ['source','root','proposal','render','printed','HOLD_page','conditions','extra_name']:
            r=copy.deepcopy(row)
            if change=='source':r['source_id']='user-book-99'
            if change=='root':r['review']['root_record_sha256']='0'*64
            if change=='proposal':r['review']['proposal_field_sha256']='0'*64
            if change=='render':r['source_pages'][0]['render_sha256']='0'*64
            if change=='printed':r['printed_page']='312'
            if change=='HOLD_page':r['pdf_page_1based']=332;r['source_pages'][0]['pdf_page_1based']=332
            if change=='conditions':r['conditions']=[]
            if change=='extra_name':r['name_zh']='未经审核名称'
            self.assertTrue(profile.claims(r))
            with self.subTest(change=change),self.assertRaises(ValueError):profile.validate_row(r)
    def test_merge_is_idempotent_and_never_duplicates_existing_book17_owner(self):
        merged=core.merge_overlay(self.catalog['reviewed_book_evidence'],self.incoming,self.catalog);again=core.merge_overlay(merged,self.incoming,self.catalog)
        self.assertEqual(merged,again);self.assertEqual(sum(b['source_id']=='user-book-17'for b in again['books']),1)
        self.assertEqual(sum(r['catalog_id']=='ima-quartz'and r['source_id']=='user-book-17'for r in again['records']),1)
    def test_unapproved_editor_identity_and_missing_Mohs_review_are_rejected(self):
        bad=copy.deepcopy(self.incoming);bad['books'][0]['credit_role']='author'
        with self.assertRaises(ValueError):core.validate_overlay(bad,self.catalog)
        bad=copy.deepcopy(self.incoming);bad['records'][0]['review']['root_record_sha256']='0'*64
        with self.assertRaises(ValueError):core.validate_overlay(bad,self.catalog)
        bad=copy.deepcopy(self.incoming);bad['records'][0]['review']['approved_candidate_id']='unknown';bad['records'][0]['review']['root_record_sha256']='0'*64;bad['books'][0]['subjects'][0]['root_review_sha256']='0'*64
        with self.assertRaises(ValueError):core.validate_overlay(bad,self.catalog)
if __name__=='__main__':unittest.main()
