"""Publication boundary tests using saved metadata only; no PDF/image/model I/O."""
from copy import deepcopy
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from book_evidence_import import encoded, merge_overlay, prepare_increment, validate_overlay
from book_pdf_increment import (BATCHES, DEFAULT_BATCH, approved_inputs, guide_markup,
    public_increment, verify_private_files)

ROOT=Path(__file__).resolve().parents[4]
REPO=Path(__file__).resolve().parents[2]
REVIEW=ROOT/'work/user-book-search-index-resume40-001/fact-candidates-resume41'


class ReviewedPDFIncrement(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.candidate_raw=(REVIEW/'selected-fact-candidates.Root-review-pending.json').read_bytes()
  cls.review_raw=(REVIEW/'Root-approved-source-statements27.json').read_bytes()
  cls.catalog=json.loads((REPO/'data/catalog.json').read_text())
  cls.manifest=json.loads((REPO/'data/reference-manifest.json').read_text())
  cls.increment=public_increment(cls.catalog,cls.candidate_raw,cls.review_raw)
  cls.ocr_root=REVIEW/'private-ocr-next3-resume41'
  cls.ocr_candidate_raw=(cls.ocr_root/'short-fact-candidates.Root-review-pending.json').read_bytes()
  cls.ocr_review_raw=(cls.ocr_root/'Root-approved-source-statements27.json').read_bytes()
  cls.ocr_increment=public_increment(cls.catalog,cls.ocr_candidate_raw,cls.ocr_review_raw,'ocr-selected3-v1')

 def test_only_exact_approved_files_can_generate_any_public_statement(self):
  for kind in ('value','new-field','approval','formatting'):
   candidate=json.loads(self.candidate_raw);review=json.loads(self.review_raw)
   if kind=='value':candidate['candidates'][0]['value_zh']='UNIT_ONLY unapproved value'
   if kind=='new-field':candidate['candidates'].append(deepcopy(candidate['candidates'][0]))
   if kind=='approval':review['records'][0]['Root_approved']=False
   candidate_raw=self.candidate_raw if kind=='approval' else json.dumps(candidate,ensure_ascii=False).encode()
   review_raw=json.dumps(review).encode() if kind=='approval' else self.review_raw
   with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'exact Root-approved'):
    public_increment(self.catalog,candidate_raw,review_raw)

 def test_actual24_and_three_methods_preserve_every_original_mineral_and_source(self):
  before=deepcopy(self.catalog);raw,_,overlay=prepare_increment(self.catalog,self.manifest,self.increment);after=json.loads(raw)
  self.assertEqual(after['minerals'],before['minerals']);self.assertEqual(len(after['minerals']),6239)
  self.assertEqual({k:v for k,v in after.items() if k!='reviewed_book_evidence'},
                   {k:v for k,v in before.items() if k!='reviewed_book_evidence'})
  old=before['reviewed_book_evidence']
  self.assertEqual(overlay['records'][:len(old['records'])],old['records'])
  self.assertEqual(overlay['withheld'],old['withheld']);self.assertEqual(self.catalog,before)
  self.assertEqual(len(self.increment['records']),24)
  self.assertEqual(overlay,merge_overlay(overlay,self.increment,self.catalog))

 def test_PDF_page_and_absent_printed_folio_remain_distinct(self):
  rows=self.increment['records'][:20]
  self.assertTrue(all(r['pdf_page_1based']==496 and r['printed_page'] is None for r in rows))
  validate_overlay(self.increment,self.catalog)
  for bad in (None,0,-1,True,'496'):
   value=deepcopy(self.increment)
   for r in value['records'][:20]:r['pdf_page_1based']=bad
   for s in value['books'][0]['subjects']:s['pdf_page_1based']=bad
   with self.subTest(bad=bad),self.assertRaises(ValueError):validate_overlay(value,self.catalog)
  value=deepcopy(self.increment);value['records'][0]['printed_page']='481'
  with self.assertRaises(ValueError):validate_overlay(value,self.catalog)

 def test_H_unknown_and_mass_density_cannot_be_promoted_or_renamed(self):
  for mutate in ('Mohs','density-unit','density-kind','density-condition','relative-density'):
   value=deepcopy(self.increment)
   if mutate=='Mohs':next(r for r in value['records'] if r['field']=='hardness')['hardness_scale']='Mohs'
   else:
    row=next(r for r in value['records'] if r['field']=='density')
    if mutate=='density-unit':row['unit']='dimensionless'
    if mutate=='density-kind':row['quantity_kind']='density_measured'
    if mutate=='density-condition':row['limits'].remove('do_not_label_measured_or_calculated')
    if mutate=='relative-density':
     row['field']='relative_density';value['books'][0]['subjects'][0]['approved_fields'][2]='relative_density'
   with self.subTest(mutate=mutate),self.assertRaises(ValueError):validate_overlay(value,self.catalog)

 def test_intake_alias_requires_exact_duplicate_identity_and_hash(self):
  book=self.increment['books'][-1]
  self.assertEqual(book['source_id'],'user-book-17');self.assertEqual(book['intake_aliases'],['new-book-02'])
  for mutate in ('alias','hash','arbitrary-new-id'):
   value=deepcopy(self.increment)
   if mutate=='alias':value['books'][-1]['intake_aliases']=['new-book-99']
   if mutate=='hash':value['books'][-1]['book_sha256']='f'*64
   if mutate=='arbitrary-new-id':value['books'][0]['source_id']='new-book-99'
   with self.subTest(mutate=mutate),self.assertRaises(ValueError):validate_overlay(value,self.catalog)

 def test_old_fields_and_credits_cannot_change_even_with_new_pdf_support(self):
  for mutate in ('value','credit','pdf-page'):
   incoming=deepcopy(self.increment)
   if mutate=='value':incoming['records'][0]['value']='UNIT_ONLY changed'
   if mutate=='credit':incoming['books'][0]['authors']=['UNIT_ONLY author']
   if mutate=='pdf-page':incoming['records'][0]['printed_page']='481';incoming['books'][0]['subjects'][0]['printed_page']='481'
   with self.subTest(mutate=mutate),self.assertRaises(ValueError):merge_overlay(self.increment,incoming,self.catalog)

 def test_public_overlay_and_guide_have_no_private_locator_or_held_value(self):
  text=encoded(self.increment).decode();guide=guide_markup(self.candidate_raw,self.review_raw)
  for private in ('/Users/','private-sources/','render_path','native_text','private-books.sqlite3'):
   self.assertNotIn(private,text);self.assertNotIn(private,guide)
  self.assertEqual(guide.count('<li>'),3);self.assertIn('印刷页 269 · PDF 第 292 页',guide)
  self.assertIn('印刷页 272 · PDF 第 295 页',guide);self.assertIn('Wenk、Andrei Bulakh',guide)
  self.assertEqual((REPO/'index.html').read_text().count(guide),1)
  self.assertFalse(any(r['catalog_id'] in ('ima-celsian','ima-cummingtonite','ima-grunerite') for r in self.increment['records']))
  value=deepcopy(self.increment);value['records'][0]['value']='file:///Users/UNIT_ONLY/private.pdf'
  with self.assertRaisesRegex(ValueError,'private book'):validate_overlay(value,self.catalog)

 def test_registry_has_only_two_exact_batches_and_legacy_entry_is_unchanged(self):
  self.assertEqual(set(BATCHES),{'selected27-v1','ocr-selected3-v1'});self.assertEqual(DEFAULT_BATCH,'selected27-v1')
  self.assertEqual(len(self.increment['records']),24)
  self.assertEqual(guide_markup(self.candidate_raw,self.review_raw).count('<li>'),3)
  self.assertEqual(len(self.ocr_increment['records']),27)
  for candidate,review,batch in ((self.candidate_raw,self.ocr_review_raw,DEFAULT_BATCH),
    (self.ocr_candidate_raw,self.review_raw,'ocr-selected3-v1'),
    (self.ocr_candidate_raw,self.ocr_review_raw,'arbitrary')):
   with self.assertRaises(ValueError):approved_inputs(candidate,review,batch)
  with self.assertRaisesRegex(ValueError,'no guide changes'):
   guide_markup(self.ocr_candidate_raw,self.ocr_review_raw,'ocr-selected3-v1')

 def test_new_batch_approval_and_candidate_cannot_be_forged_or_extended(self):
  for owner in ('candidate','review'):
   candidate=json.loads(self.ocr_candidate_raw);review=json.loads(self.ocr_review_raw)
   if owner=='candidate':candidate['candidates'][0]['value_zh']='UNIT_ONLY unapproved replacement'
   else:review['records'][0]['Root_approved']=False
   with self.subTest(owner=owner),self.assertRaisesRegex(ValueError,'exact Root-approved'):
    public_increment(self.catalog,json.dumps(candidate).encode(),json.dumps(review).encode(),'ocr-selected3-v1')

 def test_new_batch_file_limits_are_exact_and_do_not_expand_the_old_batch(self):
  calls=[]
  # Only stat and saved metadata are read; no PDF or image bytes enter this test.
  with patch('book_pdf_increment.file_pin',side_effect=lambda path,expected,maximum:calls.append((path.name,maximum))):
   proof=verify_private_files(self.ocr_root,self.ocr_candidate_raw,self.ocr_review_raw,'ocr-selected3-v1')
  self.assertIn(('new-book-11.pdf',120184046),calls);self.assertEqual(len(calls),6)
  self.assertIn(('new-book-13-p0085-highres.png',3386492),calls)
  self.assertEqual(BATCHES[DEFAULT_BATCH]['max_render_bytes'],2*1024*1024)
  self.assertEqual(proof['batch_render_limit_bytes'],4*1024*1024)
  self.assertEqual(max(BATCHES[DEFAULT_BATCH]['source_bytes'].values()),63581104)

 def test_exact_new_alias_and_same_filename_different_bytes_stay_distinct(self):
  book=self.ocr_increment['books'][-1]
  self.assertEqual((book['source_id'],book['intake_aliases']),('user-book-07',['new-book-12']))
  for mode in ('old-filename-bytes','wrong-existing-id','unregistered-intake-alias'):
   incoming=deepcopy(self.ocr_increment)
   if mode=='old-filename-bytes':incoming['books'][0]['book_sha256']='51256632b45d54a53231d1cb6f8e6338743da918984dcc7edcdd37b900f65c47'
   if mode=='wrong-existing-id':incoming['books'][-1]['source_id']='user-book-06'
   if mode=='unregistered-intake-alias':incoming['books'][-1]['intake_aliases']=['new-book-99']
   with self.subTest(mode=mode),self.assertRaises(ValueError):validate_overlay(incoming,self.catalog)

 def test_occurrence_and_habit_are_separate_source_statements_not_specimen_evidence(self):
  rows=[r for r in self.ocr_increment['records'] if r['field'] in ('occurrence','habit')]
  self.assertEqual(len(rows),3)
  for mode in ('kind','unit','limit'):
   incoming=deepcopy(self.ocr_increment);row=next(r for r in incoming['records'] if r['field']=='occurrence')
   if mode=='kind':row['quantity_kind']='current_specimen_phase'
   if mode=='unit':row['unit']='measured'
   if mode=='limit':row['limits'].remove('no_model_score_or_training_use')
   with self.subTest(mode=mode),self.assertRaises(ValueError):validate_overlay(incoming,self.catalog)
  self.assertTrue(all(b['full_book_reviewed'] is False and b['bibliography_note']=='书目版本尚待复核；所列条目已按标注原页核对。' for b in self.ocr_increment['books']))

 def test_new_batch_preserves_all_old51_sources_primary_objects_and_pending_original(self):
  old=deepcopy(self.catalog['reviewed_book_evidence'])
  raw,_,overlay=prepare_increment(self.catalog,self.manifest,self.ocr_increment)
  self.assertEqual(json.loads(raw)['minerals'],self.catalog['minerals'])
  self.assertEqual(overlay['records'][:len(old['records'])],old['records'])
  self.assertEqual(overlay['withheld'],old['withheld'])
  self.assertEqual(overlay,merge_overlay(overlay,self.ocr_increment,self.catalog))
  self.assertEqual((self.ocr_root/'short-fact-candidates.Root-review-pending.json').read_bytes(),self.ocr_candidate_raw)

 def test_mixture_formula_and_broken_OCR_are_not_public_fields(self):
  value=encoded(self.ocr_increment).decode()
  self.assertNotIn('Garnierite',value);self.assertNotIn('OCR_trace',value);self.assertNotIn('/Users/',value)
  self.assertFalse(any(r['field']=='formula' for r in self.ocr_increment['records']))
  row=next(r for r in self.ocr_increment['records'] if r['catalog_id']=='ima-millerite' and r['field']=='streak')
  self.assertIn('黑绿色',row['value']);self.assertIn('绿黑色',row['value'])
  self.assertEqual(row['comparison_status'],'source_internal_description_differs')


if __name__=='__main__':unittest.main()
