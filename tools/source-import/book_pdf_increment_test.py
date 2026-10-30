"""Publication boundary tests using saved metadata only; no PDF/image/model I/O."""
from copy import deepcopy
from pathlib import Path
import json
import unittest

from book_evidence_import import encoded, merge_overlay, prepare_increment, validate_overlay
from book_pdf_increment import approved_inputs, guide_markup, public_increment

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


if __name__=='__main__':unittest.main()
