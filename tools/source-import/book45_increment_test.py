"""Meaningful source/scope mutations and exact174 preservation; metadata only."""
import copy,json,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import book45_increment as importer
import book45_profile as profile
import book_evidence_import as core
REPO=HERE.parents[1];ROOT=REPO.parents[1]
BASE=ROOT/'work/resume45-book16-local-App-import-001/baseline001/data'
REVIEW=ROOT/'work/resume44-next-book-facts-001'

class China16Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate=(REVIEW/'short-candidates.Root-review-pending.json').read_bytes()
        cls.approval=(ROOT/'work/resume45-book16-approval-001/Root-approved16-source-statements.json').read_bytes()
        cls.held=(REVIEW/'withheld-or-excluded-fields.json').read_bytes()
        cls.catalog_raw=(BASE/'catalog.json').read_bytes();cls.manifest_raw=(BASE/'reference-manifest.json').read_bytes()
        cls.catalog=json.loads(cls.catalog_raw)
        cls.incoming=importer.public_increment(cls.catalog,cls.candidate,cls.approval,cls.held)

    def test_exact_original_candidates_and_separate_Root_authority(self):
        candidate,approval,held=importer.approved_inputs(self.candidate,self.approval,self.held)
        self.assertEqual(len(approval['records']),16);self.assertEqual(len(held),5)
        self.assertTrue(all(importer.source_field_hash(r)==r['proposal_field_sha256'] for r in candidate['records']))
        self.assertFalse(candidate['Root_approved'])
        for args in [(self.candidate+b' ',self.approval,self.held),(self.candidate,self.approval+b' ',self.held),(self.candidate,self.approval,self.held+b' ')]:
            with self.assertRaises(ValueError):importer.approved_inputs(*args)

    def test16_append_preserves_all174_primary_bytes_and_HOLD(self):
        values=importer.prepare(self.catalog_raw,self.manifest_raw,self.candidate,self.approval,self.held)
        again=importer.prepare(self.catalog_raw,self.manifest_raw,self.candidate,self.approval,self.held)
        self.assertEqual(values,again)
        catraw,manraw,o,_=values;before=self.catalog['reviewed_book_evidence']
        self.assertEqual(o['records'][:174],before['records']);self.assertEqual(o['books'][:10],before['books'])
        self.assertEqual(o['withheld'],before['withheld'])
        self.assertEqual(o['counts']['reviewed_source_statements'],190)
        self.assertEqual(o['counts']['selected_source_pages'],23)
        self.assertEqual(len({r['catalog_id'] for r in o['records']}),63)
        self.assertEqual(importer.value_bytes(catraw,'minerals'),importer.value_bytes(self.catalog_raw,'minerals'))
        for kind in ('records','books'):
            old=importer.value_bytes(importer.value_bytes(self.catalog_raw,'reviewed_book_evidence'),kind)
            current=importer.value_bytes(importer.value_bytes(catraw,'reviewed_book_evidence'),kind)
            self.assertTrue(current.startswith(old[:-1]+b','))
        entry=next(r for r in json.loads(manraw)['files'] if r['path']=='data/catalog.json')
        self.assertEqual(entry['sha256'],core.digest(catraw))
        with self.assertRaises(ValueError):importer.prepare(catraw,manraw,self.candidate,self.approval,self.held)

    def test_compiler1980_bibliography_does_not_invent_ISBN(self):
        b=self.incoming['books'][0];self.assertEqual(b['credit_role'],'compiler')
        self.assertEqual(b['publication_year'],1980);self.assertNotIn('isbn',b);self.assertTrue(profile.valid_book(b))
        for key,value in [('credit_role','editor'),('authors',['某个人']),('edition','2026年'),('publisher','未知出版社'),('isbn','unknown'),('ISBN',None)]:
            changed=copy.deepcopy(self.incoming);changed['books'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):core.validate_overlay(changed,self.catalog)

    def test_historical_and_caption_conditions_cannot_be_removed(self):
        rows=self.incoming['records']
        for cid in ['Chinese44-006','Chinese44-007','Chinese44-010','Chinese44-014','Chinese44-015','Chinese44-016']:
            row=copy.deepcopy(next(r for r in rows if r['review']['approved_candidate_id']==cid));row['conditions']=[]
            with self.subTest(cid=cid),self.assertRaises(ValueError):profile.validate_row(row)
        row=copy.deepcopy(rows[0]);row['limits'].remove('book_publication_year1980_and_historical_scope_retained')
        with self.assertRaises(ValueError):profile.validate_row(row)

    def test_wrong_field_value_Root_formula_or_render_is_rejected(self):
        row=next(r for r in self.incoming['records'] if r['review']['approved_candidate_id']=='Chinese44-008')
        for key,value in [('formula_display',row['value']),('formula_display','CuFeS3'),('unit','Mohs'),('value','当前标本已确认'),('field','hardness')]:
            changed=copy.deepcopy(row);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):profile.validate_row(changed)
        for key in ('root_record_sha256','source_book_sha256','proposal_field_sha256'):
            changed=copy.deepcopy(row);changed['review'][key]='0'*64
            with self.assertRaises(ValueError):profile.validate_row(changed)
        changed=copy.deepcopy(row);changed['source_pages'][0]['render_sha256']='0'*64
        with self.assertRaises(ValueError):profile.validate_row(changed)

    def test_unlabelled_page12_and_printed_folios_cannot_enter(self):
        self.assertEqual({r['pdf_page_1based'] for r in self.incoming['records']},{10,11,13})
        self.assertTrue(all(r['printed_page'] is None for r in self.incoming['records']))
        for page in [12,True]:
            row=copy.deepcopy(self.incoming['records'][0]);row['pdf_page_1based']=page;row['source_pages'][0]['pdf_page_1based']=page
            with self.assertRaises(ValueError):profile.validate_row(row)

    def test_new_fields_and_compiler_do_not_open_unapproved_sources(self):
        changed=copy.deepcopy(self.incoming);changed['books'][0]['source_id']='user-book-99'
        for row in changed['records']:row['source_id']='user-book-99'
        with self.assertRaises(ValueError):core.validate_overlay(changed,self.catalog)

    def test_generic_legacy_source_rejects_both_new_fields_even_with_subject_ownership(self):
        old=self.catalog['reviewed_book_evidence'];core.validate_overlay(old,self.catalog)
        for field in profile.EXTRA_FIELDS:
            overlay=copy.deepcopy(old);book=next(b for b in overlay['books'] if b['source_id']=='user-book-17')
            row=next(r for r in overlay['records'] if r['source_id']=='user-book-17' and r['catalog_id']=='ima-quartz' and r['field']=='uses')
            subject=next(s for s in book['subjects'] if s['catalog_id']==row['catalog_id'] and s['pdf_page_1based']==row['pdf_page_1based'])
            subject['approved_fields']=[field if x=='uses' else x for x in subject['approved_fields']];row['field']=field
            with self.subTest(field=field),self.assertRaises(ValueError):core.validate_overlay(overlay,self.catalog)
        changed=copy.deepcopy(self.incoming);changed['books'][0]['credit_role']='author'
        for row in changed['records']:row['source_id']='user-book-99'
        with self.assertRaises(ValueError):core.validate_overlay(changed,self.catalog)

    def test_python_and_UI_finite_profile_identical_and_public(self):
        app=(REPO/'app.js').read_text();profile_js=json.loads(app.split('const book45Profile=',1)[1].split(';\n',1)[0])
        self.assertEqual(profile_js,profile.PROFILE);core.public_text_only(self.incoming)
        self.assertNotIn('source_short_evidence',core.encoded(self.incoming).decode())

if __name__=='__main__':unittest.main()
