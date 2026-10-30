"""Chinese56 pure metadata tests; no PDF, render, model or network I/O."""
import copy,json,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import book43_increment as importer
import book43_profile as profile
import book_evidence_import as core
REPO=HERE.parents[1];ROOT=REPO.parents[1]
REVIEW=ROOT/'work/user-book-next-Chinese-facts-resume42-001'
BASE=ROOT/'work/Chinese56-local-App-import-resume43-001/baseline001'

class Chinese56Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate=(REVIEW/'short-candidates.Root-review-pending.json').read_bytes()
        cls.ledger=(REVIEW/'Root-approved-source-statements56-resume43.json').read_bytes()
        cls.held=(REVIEW/'withheld-or-excluded-fields.json').read_bytes()
        cls.catalog_raw=(BASE/'data/catalog.json').read_bytes();cls.manifest_raw=(BASE/'data/reference-manifest.json').read_bytes()
        cls.catalog=json.loads(cls.catalog_raw);cls.manifest=json.loads(cls.manifest_raw)
        cls.incoming=importer.public_increment(cls.catalog,cls.candidate,cls.ledger,cls.held)

    def test_exact56_final_authority_and57_original_semantic_hashes(self):
        candidate,ledger,holds=importer.approved_inputs(self.candidate,self.ledger,self.held)
        self.assertEqual(len(ledger['records']),56);self.assertEqual(len(holds['records']),14)
        self.assertTrue(all(importer.source_field_hash(r)==r['proposal_field_sha256'] for r in candidate['records']))
        self.assertNotIn('Chinese42-023',{r['review']['approved_candidate_id'] for r in self.incoming['records']})
        self.assertEqual(ledger['additional_HOLD'][0]['candidate_id'],'Chinese42-023')
        for args in [(self.candidate+b' ',self.ledger,self.held),(self.candidate,self.ledger+b' ',self.held),(self.candidate,self.ledger,self.held+b' ')]:
            with self.assertRaises(ValueError):importer.approved_inputs(*args)

    def test_quantities_are_literal_secondary_and_pending_flags_do_not_ship(self):
        for row in self.incoming['records']:
            self.assertIsNone(row['unit']);self.assertIsNone(row['hardness_scale']);self.assertNotIn('Root_approval_pending',row['limits'])
            self.assertNotIn('no_App_import',row['limits']);profile.validate_row(row)
        for field in ('crystal_habit','cleavage','formula','occurrence'):
            original=next(r for r in self.incoming['records'] if r['field']==field)
            for key,value in [('unit','Mohs'),('hardness_scale','Mohs'),('quantity_kind','literal_source_statement'),('limits',[]),('conditions',[]),('value','本标本已确认产地')]:
                row=copy.deepcopy(original);row[key]=value
                with self.subTest(field=field,key=key),self.assertRaises(ValueError):profile.validate_row(row)

    def test_formula_is_separate_from_unchanged_narrative_and_exact_approved_literal(self):
        rows=[r for r in self.incoming['records'] if r['field']=='formula'];self.assertEqual(len(rows),23)
        original=next(r for r in rows if r['review']['approved_candidate_id']=='Chinese42-007')
        self.assertEqual(original['formula_display'],'Zr[SiO4]');self.assertIn('本书锆石条目',original['value'])
        for value in [None,original['value'],'ZrSiO5','<svg>']:
            row=copy.deepcopy(original);row['formula_display']=value
            with self.assertRaises(ValueError):profile.validate_row(row)
        row=copy.deepcopy(next(r for r in self.incoming['records'] if r['field']=='occurrence'));row['formula_display']='WC'
        with self.assertRaises(ValueError):profile.validate_row(row)

    def test_locality_HOLD_cannot_reenter_and_limits_remain_explicit(self):
        row=copy.deepcopy(next(r for r in self.incoming['records'] if r['review']['approved_candidate_id']=='Chinese42-022'))
        row.update(field='occurrence',quantity_kind='historical_book_locality_occurrence_not_specimen_origin')
        row['review']['approved_candidate_id']='Chinese42-023'
        with self.assertRaises(ValueError):profile.validate_row(row)
        for field in ('occurrence','cleavage'):
            row=copy.deepcopy(next(r for r in self.incoming['records'] if r['field']==field));row['conditions']=[]
            with self.assertRaises(ValueError):profile.validate_row(row)

    def test_wrong_source_Root_or_selected_page_is_rejected(self):
        original=self.incoming['records'][0]
        for key in ('root_record_sha256','source_book_sha256','proposal_field_sha256'):
            row=copy.deepcopy(original);row['review'][key]='0'*64
            with self.assertRaises(ValueError):profile.validate_row(row)
        for value in [[],[None],[{'pdf_page_1based':True,'printed_page':'325','render_sha256':'0'*64}]]:
            row=copy.deepcopy(original);row['source_pages']=value
            with self.assertRaises(ValueError):profile.validate_row(row)
        row=copy.deepcopy(original);row['source_pages'][0]['render_sha256']='0'*64
        with self.assertRaises(ValueError):profile.validate_row(row)

    def test_editor_only_bibliography_and_no_invented_ISBN_or_publisher(self):
        book=self.incoming['books'][0];self.assertEqual(book['authors'],['赵珊茸']);self.assertEqual(book['credit_role'],'editor')
        self.assertTrue(profile.valid_book(book))
        for key,value in [('credit_role','author'),('authors',['DK']),('book_sha256','0'*64),('ISBN','unknown'),('publisher','某出版社')]:
            incoming=copy.deepcopy(self.incoming);incoming['books'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):core.validate_overlay(incoming,self.catalog)

    def test_new_typed_fields_do_not_open_other_sources(self):
        row=copy.deepcopy(self.incoming['records'][0]);row['source_id']='user-book-99'
        changed=copy.deepcopy(self.incoming);changed['books'][0]['source_id']='user-book-99'
        for r in changed['records']:r['source_id']='user-book-99'
        with self.assertRaises(ValueError):core.validate_overlay(changed,self.catalog)

    def test_python_and_UI_finite_profile_match(self):
        app=(REPO/'app.js').read_text();public=json.loads(app.split('const book43Profile=',1)[1].split(';\n',1)[0])
        self.assertEqual(public,profile.PROFILE)

    def test_174_append_retains_primary_old118_old9_and_HOLD_raw_bytes(self):
        catraw,manraw,overlay,_=importer.prepare(self.catalog_raw,self.manifest_raw,self.candidate,self.ledger,self.held)
        self.assertEqual(len(overlay['records']),174);self.assertEqual(len(overlay['books']),10)
        self.assertEqual(overlay['counts']['selected_source_pages'],20)
        self.assertEqual(len({r['catalog_id'] for r in overlay['records']}),61)
        self.assertEqual(overlay['records'][:118],self.catalog['reviewed_book_evidence']['records'])
        self.assertEqual(overlay['books'][:9],self.catalog['reviewed_book_evidence']['books'])
        self.assertEqual(importer.value_bytes(catraw,'minerals'),importer.value_bytes(self.catalog_raw,'minerals'))
        before=importer.value_bytes(self.catalog_raw,'reviewed_book_evidence');after=importer.value_bytes(catraw,'reviewed_book_evidence')
        self.assertEqual(importer.value_bytes(before,'withheld'),importer.value_bytes(after,'withheld'))
        entry=next(r for r in json.loads(manraw)['files'] if r['path']=='data/catalog.json');self.assertEqual(entry['sha256'],core.digest(catraw))
        with self.assertRaises(ValueError):importer.prepare(self.catalog_raw+b' ',self.manifest_raw,self.candidate,self.ledger,self.held)

if __name__=='__main__':unittest.main()
