"""Exact public metadata and rejection boundaries; no PDF/render/model reads."""
import copy,json,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import book42_increment as importer
import book42_profile as profile
import book_evidence_import as core
REPO=HERE.parents[1];ROOT=REPO.parents[1]
REVIEW=ROOT/'work/user-book-expanded-facts-resume42-001'
BASE=ROOT/'work/book42-local-secondary-import-resume42-001/baseline001'

class Exact40Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate=(REVIEW/'short-candidates.json').read_bytes()
        cls.ledger=(REVIEW/'Root-approved-source-statements40.json').read_bytes()
        cls.metadata=(REVIEW/'source-pins-and-selection.json').read_bytes()
        cls.catalog=json.loads((BASE/'data/catalog.json').read_bytes())
        cls.manifest=json.loads((BASE/'data/reference-manifest.json').read_bytes())
        cls.incoming=importer.public_increment(cls.catalog,cls.candidate,cls.ledger,cls.metadata)
    def test_exact40_with_all_contributing_pages(self):
        self.assertEqual(len(self.incoming['records']),40);self.assertEqual(len(self.incoming['books']),2)
        self.assertEqual(len({(r['source_id'],p['pdf_page_1based']) for r in self.incoming['records'] for p in r['source_pages']}),6)
    def test_only_exact_unknown_author_bibliography_is_accepted(self):
        book=next(b for b in self.incoming['books'] if b['source_id']=='new-book-07')
        self.assertEqual(book['authors'],[]);self.assertTrue(profile.valid_bibliography(book))
        for key,value in [('authors',['DK']),('authors',['Bharti Bedi']),('credit_role','editor'),('book_sha256','0'*64),('bibliographic_pdf_pages',[True,6])]:
            changed=copy.deepcopy(self.incoming);target=next(b for b in changed['books'] if b['source_id']=='new-book-07');target[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):core.validate_overlay(changed,self.catalog)
        changed=copy.deepcopy(self.incoming);changed['books'][1]['bibliography_review']['root_record_sha256']='0'*64
        with self.assertRaises(ValueError):core.validate_overlay(changed,self.catalog)
        changed=copy.deepcopy(self.catalog['reviewed_book_evidence']);changed['books'][0]['authors']=[]
        with self.assertRaises(ValueError):core.validate_overlay(changed,self.catalog)
    def test_python_UI_and_Root_bibliography_are_the_same_metadata(self):
        approval_path=ROOT/'work/book42-bibliography-review-resume42-001/Root-approved-bibliography.json'
        raw=approval_path.read_bytes();self.assertEqual((len(raw),core.digest(raw)),(profile.BIBLIOGRAPHY_REVIEW_BYTES,profile.BIBLIOGRAPHY_REVIEW_SHA))
        reviewed=json.loads(raw)['approved_books']
        app=(ROOT/'outputs/shikuang-web-2.0/app.js').read_text()
        UI=json.loads(app.split('const book42Bibliography=',1)[1].split(';\n',1)[0])
        for book in self.incoming['books']:
            sid=book['source_id'];expected=profile.public_bibliography(sid)
            self.assertEqual({k:book[k] for k in expected},expected);self.assertEqual(UI[sid],expected)
            for key in ('title','authors','publisher','edition','isbn','bibliographic_pdf_pages','bibliography_note'):self.assertEqual(expected[key],reviewed[sid][key])
    def test_bibliography_appendix_changes_no_statements_old7_or_primary_bytes(self):
        unit=ROOT/'work/book42-bibliography-review-resume42-001/appendix001'
        before=(unit/'baseline/data/catalog.json').read_bytes();manifest=(unit/'baseline/data/reference-manifest.json').read_bytes()
        approval=(unit.parent/'Root-approved-bibliography.json').read_bytes()
        catraw,manraw,report=importer.prepare_bibliography_appendix(before,manifest,approval)
        old=json.loads(before);after=json.loads(catraw);o=old['reviewed_book_evidence'];n=after['reviewed_book_evidence']
        self.assertEqual(n['records'],o['records']);self.assertEqual(n['books'][:7],o['books'][:7]);self.assertEqual(n['withheld'],o['withheld']);self.assertEqual(n['counts'],o['counts'])
        self.assertTrue(report['all6239_primary_array_bytes_exact']);self.assertEqual(after['minerals'],old['minerals'])
        row=next(r for r in json.loads(manraw)['files'] if r['path']=='data/catalog.json');self.assertEqual((row['bytes'],row['sha256']),(len(catraw),core.digest(catraw)))
        with self.assertRaises(ValueError):importer.prepare_bibliography_appendix(before,manifest,approval+b' ')
    def test_candidate_pending_status_cannot_replace_final_Root_authority(self):
        self.assertFalse(json.loads(self.candidate)['App_import_approved'])
        for position in ('Root_approved','Root_actual_review'):
            d=json.loads(self.ledger);d['records'][0][position]=False
            with self.assertRaises(ValueError):importer.approved_inputs(self.candidate,core.encoded(d),self.metadata)
    def test_candidate_field_or_locator_mutation_rejected(self):
        for k,v in [('value_zh','伪造陈述'),('source_pages',[])]:
            d=json.loads(self.candidate);d['records'][0][k]=v
            with self.assertRaises(ValueError):importer.approved_inputs(core.encoded(d),self.ledger,self.metadata)
    def test_ledger_extra_or_missing_record_rejected(self):
        d=json.loads(self.ledger);d['records'].append(copy.deepcopy(d['records'][0]))
        with self.assertRaises(ValueError):importer.approved_inputs(self.candidate,core.encoded(d),self.metadata)
    def test_Mohs_retained_and_ratio_or_unknown_scale_rejected(self):
        rows=[r for r in self.incoming['records'] if r['field']=='hardness'];self.assertEqual(len(rows),10)
        for original in rows:
            profile.validate_row(original)
            for field,value in [('quantity_kind','hardness_scale_unspecified'),('unit','ratio'),('hardness_scale',None)]:
                row=copy.deepcopy(original);row[field]=value
                with self.assertRaises(ValueError):profile.validate_row(row)
    def test_qualitative_comparisons_never_numeric_density_or_hardness(self):
        for original in [r for r in self.incoming['records'] if r['field'].endswith('_comparison')]:
            for field,value in [('unit','g/cm³'),('hardness_scale','Mohs'),('quantity_kind','relative_density')]:
                row=copy.deepcopy(original);row[field]=value
                with self.assertRaises(ValueError):profile.validate_row(row)
    def test_missing_duplicate_or_changed_page_render_rejected(self):
        original=next(r for r in self.incoming['records'] if len(r['source_pages'])==2)
        for pages in [[],[None],[original['source_pages'][0]]*2,[dict(original['source_pages'][0],render_sha256='0'*64)]]:
            row=copy.deepcopy(original);row['source_pages']=pages
            with self.assertRaises(ValueError):profile.validate_row(row)
    def test_new_fields_require_exact_review_and_source(self):
        for field,value in [('root_record_sha256','0'*64),('source_book_sha256','0'*64)]:
            row=copy.deepcopy(next(r for r in self.incoming['records'] if r['field']=='processing'));row['review'][field]=value
            with self.assertRaises(ValueError):profile.validate_row(row)
    def test_conditions_and_source_limits_cannot_be_removed(self):
        row=copy.deepcopy(self.incoming['records'][0]);row['limits']=[]
        with self.assertRaises(ValueError):profile.validate_row(row)
    def test_preserve_all6239_old78_old7_and_HOLD(self):
        catraw,manraw,overlay=core.prepare_increment(self.catalog,self.manifest,self.incoming)
        self.assertEqual(json.loads(catraw)['minerals'],self.catalog['minerals'])
        self.assertEqual(overlay['records'][:78],self.catalog['reviewed_book_evidence']['records'])
        self.assertEqual(overlay['books'][:7],self.catalog['reviewed_book_evidence']['books'])
        self.assertEqual(overlay['withheld'],self.catalog['reviewed_book_evidence']['withheld'])
        self.assertEqual(overlay['counts']['reviewed_source_statements'],118)
        self.assertEqual(overlay['counts']['selected_source_pages'],16)
        m=json.loads(manraw);entry=next(r for r in m['files'] if r['path']=='data/catalog.json')
        self.assertEqual(entry['sha256'],core.digest(catraw))
    def test_legacy_same_source_statement_cannot_be_replaced(self):
        changed=copy.deepcopy(self.catalog['reviewed_book_evidence']);changed['records'][0]['value']='changed'
        with self.assertRaises(ValueError):core.merge_overlay(self.catalog['reviewed_book_evidence'],changed,self.catalog)
    def test_private_source_locators_or_fulltext_cannot_ship(self):
        self.assertNotIn('source_excerpt_or_table_transcription',core.encoded(self.incoming).decode())
        for value in ('/Users/UNIT/private.pdf','file:///private/book.pdf','private-sources/book.pdf'):
            changed=copy.deepcopy(self.incoming);changed['records'][0]['value']=value
            with self.assertRaises(ValueError):core.validate_overlay(changed,self.catalog)

if __name__=='__main__':unittest.main()
