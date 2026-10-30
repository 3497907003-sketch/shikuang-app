#!/usr/bin/env python3
"""Import this exact Root-reviewed PDF increment as separate book statements.

Reads the pinned private sources locally; ships short paraphrases and bibliography
only. No network, extraction/OCR, model operation, primary-property edit or deploy.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import html
import json

from book_evidence_import import (digest, encoded, merge_overlay, need, pinned,
    prepare_increment, public_text_only, read_json, transactional_replace, validate_overlay)

ROOT_REVIEW_SHA='5a84f85f40546a73970d30a7cad3ef2321e47ec6a0c81f7c34ffe5fc534aced5'
CANDIDATE_SHA='0c1c0ae7e78cc477fc0bc51a304dfd939253a62aaf6f0ac5c2fbb62cc9a4aebd'
SOURCE_IDS={
 'new-book-03':('new-book-03','6b61c081c7f630e787486cadb2fcaf40539f746a47f69f2aa43a42e16c9765f1'),
 'new-book-08':('new-book-08','af7dc5ce2fd8e6c9c1d05025521d249fecb5afcbad5490f3ee642c5eb5132a89'),
 'new-book-02':('user-book-17','66b43cd348f1f902380d86a3fb2c1db005990ece468c6428cff82d44d57c9702'),
}
METHOD_IDS=('resume41-book-fact-021','resume41-book-fact-022','resume41-book-fact-023')
GUIDE_START='          <!-- reviewed-pdf-book-methods:start -->'
GUIDE_END='          <!-- reviewed-pdf-book-methods:end -->'


def canonical_sha(value):
 return digest(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode())


def file_pin(path,expected,maximum):
 need(path.is_absolute() and path.resolve()==path and path.is_file() and not path.is_symlink(),'closed private source file')
 need(0<path.stat().st_size<=maximum,'private source size bound')
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 need(h.hexdigest()==expected,'reviewed source/render SHA changed')


def approved_inputs(candidate_raw,review_raw):
 """No arbitrary approved-looking JSON: both exact immutable files are required."""
 need(digest(candidate_raw)==CANDIDATE_SHA and digest(review_raw)==ROOT_REVIEW_SHA,'exact Root-approved candidate and ledger bytes required')
 draft=json.loads(candidate_raw);review=json.loads(review_raw)
 need(review['state']=='approved_short_source_faithful_statements_only_not_primary_measurements' and
      review['whole_book_or_page_image_publication_authorized'] is False and
      review['training_or_model_or_independent_test_admission'] is False,'source review scope changed')
 need(review['source_candidates_pin']['sha256']==CANDIDATE_SHA and
      review['source_candidates_pin']['bytes']==len(candidate_raw),'Root candidate binding changed')
 candidates={r['candidate_id']:r for r in draft['candidates']}
 need(len(candidates)==len(draft['candidates'])==27 and len(review['records'])==27,'exact approved increment required')
 approved={}
 for row in review['records']:
  cid=row['candidate_id'];need(cid in candidates and cid not in approved,'duplicate or unapproved candidate')
  source=candidates[cid];copy=deepcopy(source);claimed=copy.pop('proposal_field_sha256')
  need(canonical_sha(copy)==claimed==row['proposal_field_sha256'],'candidate field hash changed')
  need(row.get('Root_actual_review') is row.get('Root_approved') is True and
       row.get('decision')=='approved_as_explicit_book_source_statement_with_conditions' and
       row['no_primary_property_or_current_catalog_formula_overwrite'] is row['no_model_score_or_training_use'] is True,
       'actual per-field Root review required')
  for key in ('catalog_id','field','value_zh','source_id','source_sha256','quantity_kind','unit','hardness_scale','conditions'):
   need(row[key]==source[key],'Root/source field correspondence changed: '+key)
  need(row['limits_retained']==source['limits'] and all(row[key]==source['source_locator'][key]
       for key in ('pdf_page_1based','printed_page','table_number')),'Root source locator or limits changed')
  need(source['source_id'] in SOURCE_IDS and source['source_sha256']==SOURCE_IDS[source['source_id']][1],'exact source identity required')
  approved[cid]=source
 need(set(approved)==set(candidates),'unreviewed field cannot pass publication')
 need(review['source_conflict_HOLD_retained']==['Celsian.crystal_system','Celsian.space_group','Cummingtonite.crystal_system','Grunerite.crystal_system'],'all four source conflicts must stay withheld')
 return draft,review,approved


def verify_private_files(root,candidate_raw,review_raw):
 draft,review,_=approved_inputs(candidate_raw,review_raw)
 need(Path(review['source_candidates_pin']['path'])==root/'selected-fact-candidates.Root-review-pending.json','candidate private owner changed')
 sources={r['source_id']:r for r in draft['source_sources']}
 need(set(sources)==set(SOURCE_IDS),'exact three private source files required')
 for sid,(_,expected) in SOURCE_IDS.items():
  source=sources[sid];need(source['source_sha256']==expected,'source pin mismatch')
  file_pin(Path(source['private_source_path']),expected,100*1024*1024)
 views={r['path']:r for r in review['Root_actual_complete_page_views']}
 need(len(views)==6,'exact six Root-viewed complete pages required')
 for view in views.values():
  path=Path(view['path']);need(path.stat().st_size==view['bytes'],'render size mismatch');file_pin(path,view['sha256'],2*1024*1024)
 for source in draft['candidates']:
  loc=source['source_locator'];view=views.get(loc['render_path'])
  need(view is not None and view['sha256']==loc['render_sha256'] and loc['source_sha256']==source['source_sha256'],
       'candidate must use its actual Root-viewed complete page')
 return {'source_files_sha_verified':3,'Root_viewed_complete_pages_sha_verified':6,'no_text_extraction_or_OCR':True}


def public_increment(catalog,candidate_raw,review_raw):
 draft,review,approved=approved_inputs(candidate_raw,review_raw)
 minerals={r['id']:r for r in catalog['minerals']};sources={r['source_id']:r for r in draft['source_sources']}
 books={};rows=[]
 for cid,fact in approved.items():
  if fact['catalog_id'] is None:
   need(cid in METHOD_IDS,'only three approved general methods');continue
  mid=fact['catalog_id'];need(mid in minerals and minerals[mid]['name_en']==fact['name_en'] and minerals[mid]['formula']==fact['current_catalog_formula'],'existing catalog identity changed')
  sid,source_sha=SOURCE_IDS[fact['source_id']];source=sources[fact['source_id']];loc=fact['source_locator']
  if sid not in books:
   books[sid]={'source_id':sid,'title':source['title'],'authors':source.get('authors',source.get('editors')),
    'book_sha256':source_sha,'root_review_sha256':ROOT_REVIEW_SHA,'status':'reviewed_selected_pages','source_format':'PDF',
    'full_book_reviewed':False,'subjects':[]}
   if sid=='user-book-17':books[sid].update(credit_role='editor',intake_aliases=['new-book-02'])
  row={'catalog_id':mid,'name_en':fact['name_en'],'source_id':sid,'pdf_page_1based':loc['pdf_page_1based'],
   'printed_page':loc['printed_page'],'table_number':loc['table_number'],'field':fact['field'],'value':fact['value_zh'],
   'status':'reviewed_source_statement','quantity_kind':fact['quantity_kind'],'unit':fact['unit'],'hardness_scale':fact['hardness_scale'],
   'limits':fact['limits'],'conditions':fact['conditions'],'comparison_status':fact['source_comparison']['status'],
   'review':{'decision':'approved_source_statement','root_record_sha256':ROOT_REVIEW_SHA,'source_book_sha256':source_sha,
    'source_evidence_sha256':loc['render_sha256'],'proposal_field_sha256':fact['proposal_field_sha256']}}
  rows.append(row);subjects=books[sid]['subjects']
  subject=next((s for s in subjects if s['catalog_id']==mid and s['pdf_page_1based']==loc['pdf_page_1based']),None)
  if subject is None:
   subject={k:row[k] for k in ('catalog_id','name_en','pdf_page_1based','printed_page','table_number')};subject['approved_fields']=[];subjects.append(subject)
  subject['approved_fields'].append(fact['field'])
 need(len(rows)==24 and len(books)==3,'exact24 mineral statements and three distinct sources required')
 overlay={'schema_version':1,'scope':'secondary_book_source_statements','primary_properties_changed':False,'model_scope_changed':False,
  'books':list(books.values()),'records':rows,'withheld':[],
  'counts':{'reviewed_source_statements':24,'selected_source_pages':3,'withheld_fields':0,'full_book_reviewed':False}}
 validate_overlay(overlay,catalog);public_text_only(overlay)
 return overlay


def guide_markup(candidate_raw,review_raw):
 _,_,approved=approved_inputs(candidate_raw,review_raw)
 lines=[GUIDE_START,'          <div data-reviewed-pdf-book-methods>','            <ul class="guide-steps">']
 for cid in METHOD_IDS:
  fact=approved[cid];loc=fact['source_locator'];need(fact['catalog_id'] is None,'guide cannot claim a mineral measurement')
  cite='印刷页 '+loc['printed_page']+' · PDF 第 '+str(loc['pdf_page_1based'])+' 页'
  lines.append('              <li>'+html.escape(fact['value_zh'])+'<small class="property-source">'+html.escape(cite)+'</small></li>')
 lines+=['            </ul>','            <p class="guide-note">依据：Hans-Rudolf Wenk、Andrei Bulakh《Minerals: Their Constitution and Origin》。以上是鉴定方法参考，照片不能提供所有实测物性。</p>','          </div>',GUIDE_END]
 return '\n'.join(lines)


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',type=Path,required=True)
 parser.add_argument('--review-root',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
 parser.add_argument('--apply-to-local-app',action='store_true');args=parser.parse_args()
 repo=args.repo.resolve();root=args.review_root.resolve();out=args.output_dir.resolve();need(not out.exists(),'fresh output directory required')
 candidate_raw=pinned(root/'selected-fact-candidates.Root-review-pending.json',CANDIDATE_SHA)
 review_raw=pinned(root/'Root-approved-source-statements27.json',ROOT_REVIEW_SHA)
 checks=verify_private_files(root,candidate_raw,review_raw)
 cp=repo/'data/catalog.json';mp=repo/'data/reference-manifest.json';before=[cp.read_bytes(),mp.read_bytes()]
 catalog=read_json(cp);manifest=read_json(mp);need(catalog['count']==len(catalog['minerals'])==6239,'existing6239 catalog required')
 old=[r for r in manifest['files'] if r['path']=='data/catalog.json'];need(len(old)==1 and old[0]['sha256']==digest(before[0]) and old[0]['bytes']==len(before[0]),'existing catalog manifest mismatch')
 incoming=public_increment(catalog,candidate_raw,review_raw);catraw,manraw,overlay=prepare_increment(catalog,manifest,incoming)
 guide=guide_markup(candidate_raw,review_raw);index=(repo/'index.html').read_text()
 need(index.count(guide)==1,'the three exact approved guide methods must already appear once in index.html')
 need(json.loads(catraw)['minerals']==catalog['minerals'],'all current mineral objects must remain unchanged')
 out.mkdir(parents=True);(out/'public-book-increment.json').write_bytes(encoded(incoming));(out/'guide-methods.html').write_text(guide+'\n')
 if args.apply_to_local_app:transactional_replace(cp,mp,catraw,manraw,before)
 report={'schema':'Root-reviewed-PDF-book-local-import-v1','Root_review_sha256':ROOT_REVIEW_SHA,'candidate_sha256':CANDIDATE_SHA,
  'local_App_applied':args.apply_to_local_app,'new_mineral_book_statements':24,'new_guide_methods':3,
  'counts':overlay['counts'],'private_checks':checks,'all6239_mineral_objects_preserved':True,
  'previous_book_statements_preserved':all(r in overlay['records'] for r in catalog.get('reviewed_book_evidence',{}).get('records',[])),
  'primary_measurements_or_model_scope_changed':False,'source_images_or_paths_in_public_bundle':False,
  'catalog_sha256':digest(catraw),'manifest_sha256':digest(manraw),'deployed_or_synced':False}
 (out/'local-import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
