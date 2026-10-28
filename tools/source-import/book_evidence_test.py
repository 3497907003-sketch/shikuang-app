"""Book source publication and two-file failure boundaries; no book/image I/O."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from book_evidence_import import (ROOT_REVIEW_SHA,public_overlay,prepare,transactional_replace,merge_overlay,validate_overlay)

ROOT=Path(__file__).resolve().parents[4]
UNIT=ROOT/'work/user-books-intake-resume37-20261028-001'
APP=UNIT/'App-secondary-evidence-resume38-001'

def read(p):return json.loads(p.read_text())

class BookImport(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.stage=read(UNIT/'preparation-resume38/reviewed001/book-evidence-overlay.staged-no-App-import.json')
  cls.bib=read(UNIT/'preparation-resume38/bibliography-display-profile.proposed.json')
  cls.catalog=read(APP/'before/catalog.json');cls.manifest=read(APP/'before/reference-manifest.json')
 def test_deterministic_top_level_only_and_primary_objects_preserved(self):
  before=copy.deepcopy(self.catalog);a,b,o=prepare(self.catalog,self.manifest,self.stage,self.bib,ROOT_REVIEW_SHA)
  self.assertEqual((a,b,o),prepare(self.catalog,self.manifest,self.stage,self.bib,ROOT_REVIEW_SHA))
  after=json.loads(a);self.assertEqual(after['minerals'],before['minerals'])
  self.assertEqual({k:v for k,v in after.items() if k!='reviewed_book_evidence'},before)
  self.assertEqual(self.catalog,before);self.assertEqual(len(o['records']),27)
  self.assertEqual(o['withheld'][0]['reason'],'source_internal_ambiguity')
 def test_missing_root_field_review_and_wrong_source_species_rejected(self):
  for mode in ['review','species','root']:
   s=copy.deepcopy(self.stage)
   if mode=='review':del s['approved_secondary_facts'][0]['trusted_ledger_canonical_sha256']
   if mode=='species':s['approved_secondary_facts'][0]['catalog_id']='ima-jadeite'
   with self.subTest(mode=mode),self.assertRaises(ValueError):public_overlay(self.catalog,s,self.bib,'0'*64 if mode=='root' else ROOT_REVIEW_SHA)
 def test_unsupported_units_or_scale_never_promoted(self):
  for field in ['hardness','relative_density']:
   s=copy.deepcopy(self.stage);r=next(r for r in s['approved_secondary_facts'] if r['field']==field)
   r['normalized_source_value']['unit']='Mohs' if field=='hardness' else 'g/cm³'
   with self.subTest(field=field),self.assertRaises(ValueError):public_overlay(self.catalog,s,self.bib,ROOT_REVIEW_SHA)
 def test_public_payload_contains_no_private_locator_image_or_HOLD_sentence(self):
  o=public_overlay(self.catalog,self.stage,self.bib,ROOT_REVIEW_SHA);text=json.dumps(o,ensure_ascii=False)
  for value in ['/Users/','EPUB/','image_member','source_page_image','无解理，一组不完全至中等解理','Root_review_note']:
   self.assertNotIn(value,text)
 def test_source_history_cannot_be_silently_replaced(self):
  c=copy.deepcopy(self.catalog);c['reviewed_book_evidence']={'arbitrary':'old source'}
  with self.assertRaisesRegex(ValueError,'schema'):prepare(c,self.manifest,self.stage,self.bib,ROOT_REVIEW_SHA)
 def test_exception_during_second_replace_restores_both_original_files(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);cat=p/'catalog.json';man=p/'manifest.json';cat.write_bytes(b'old catalog');man.write_bytes(b'old manifest');calls=[]
   def fail_second(src,dest):
    calls.append(dest)
    if len(calls)==2:raise OSError('UNIT_ONLY forced second replacement failure')
    os.replace(src,dest)
   with self.assertRaises(OSError):transactional_replace(cat,man,b'new catalog',b'new manifest',[b'old catalog',b'old manifest'],fail_second)
   self.assertEqual(cat.read_bytes(),b'old catalog');self.assertEqual(man.read_bytes(),b'old manifest')
   self.assertEqual({f.name for f in p.iterdir()},{'catalog.json','manifest.json'})
 def test_concurrent_edit_rejected_without_overwrite(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);cat=p/'catalog.json';man=p/'manifest.json';cat.write_bytes(b'other edit');man.write_bytes(b'old manifest')
   with self.assertRaisesRegex(ValueError,'changed'):transactional_replace(cat,man,b'new',b'new',[b'old catalog',b'old manifest'])
   self.assertEqual(cat.read_bytes(),b'other edit');self.assertEqual(man.read_bytes(),b'old manifest')


 def increment(self,source='user-book-02',page='190',review='b'*64,field='luster'):
  # Synthetic contract increment; no new book/source fact is being approved.
  full=public_overlay(self.catalog,self.stage,self.bib,ROOT_REVIEW_SHA)
  row=copy.deepcopy(next(r for r in full['records'] if r['catalog_id']=='ima-jadeite' and r['field']==field))
  row.update(source_id=source,printed_page=page);row['review']['root_record_sha256']=review
  book=copy.deepcopy(full['books'][0]);book.update(source_id=source,root_review_sha256=review)
  book['subjects']=[{'catalog_id':'ima-jadeite','name_en':'Jadeite','printed_page':page,'approved_fields':[field]}]
  result={k:copy.deepcopy(v) for k,v in full.items() if k not in ('books','records','withheld','counts')}
  result.update(books=[book],records=[row],withheld=[],counts={'reviewed_source_statements':1,'selected_source_pages':1,'withheld_fields':0,'full_book_reviewed':False})
  return result
 def test_new_book_increment_appends_without_removing_old_sources(self):
  old=public_overlay(self.catalog,self.stage,self.bib,ROOT_REVIEW_SHA);saved=copy.deepcopy(old);new=self.increment(source='user-book-103')
  result=merge_overlay(old,new,self.catalog)
  self.assertEqual(old,saved);self.assertEqual(result['books'][0],old['books'][0]);self.assertEqual(result['records'][:27],old['records']);self.assertEqual(result['withheld'],old['withheld'])
  self.assertEqual(len(result['records']),28);self.assertEqual(len(result['books']),2)
  self.assertEqual(result,merge_overlay(result,new,self.catalog))
 def test_new_same_book_page_binds_subject_review_preserving_old_subjects(self):
  old=public_overlay(self.catalog,self.stage,self.bib,ROOT_REVIEW_SHA);new=self.increment();result=merge_overlay(old,new,self.catalog)
  self.assertEqual(result['books'][0]['subjects'][:4],old['books'][0]['subjects'])
  self.assertEqual(result['books'][0]['root_review_sha256'],old['books'][0]['root_review_sha256'])
  subject=result['books'][0]['subjects'][-1];self.assertEqual(subject['printed_page'],'190');self.assertEqual(subject['root_review_sha256'],'b'*64)
  self.assertEqual(result['records'][:27],old['records']);validate_overlay(result,self.catalog)
 def test_same_printed_page_can_add_disjoint_fields_under_new_review(self):
  old=self.increment(page='189',review=ROOT_REVIEW_SHA,field='luster');new=self.increment(page='189',field='hardness');result=merge_overlay(old,new,self.catalog)
  self.assertEqual(result['books'][0]['subjects'][0],old['books'][0]['subjects'][0]);self.assertEqual(len(result['books'][0]['subjects']),2)
  self.assertEqual(len(result['records']),2);self.assertEqual(result['counts']['selected_source_pages'],1);validate_overlay(result,self.catalog)
 def test_old_statement_credit_and_ambiguous_duplicate_cannot_change(self):
  old=public_overlay(self.catalog,self.stage,self.bib,ROOT_REVIEW_SHA)
  for mode in ('value','credit','duplicate','held-overwrite'):
   incoming=copy.deepcopy(old)
   if mode=='value':incoming['records'][0]['value']+=' UNIT_ONLY'
   if mode=='credit':incoming['books'][0]['authors']=['UNIT_ONLY other author']
   if mode=='duplicate':incoming['records'].append(copy.deepcopy(incoming['records'][0]))
   if mode=='held-overwrite':incoming['withheld'][0]['reason']='UNIT_ONLY changed decision'
   with self.subTest(mode=mode),self.assertRaises(ValueError):merge_overlay(old,incoming,self.catalog)

if __name__=='__main__':unittest.main()
