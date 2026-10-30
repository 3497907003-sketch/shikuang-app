#!/usr/bin/env python3
"""Exact approved40 secondary statements; no extraction, model use or publishing.

The unchanged candidate records/source_pages are only a correspondence source.
The pinned Root ledger is the sole approval. Private PDFs/renders are hash-only.
"""
from copy import deepcopy
from pathlib import Path
import argparse,hashlib,json,re
import book42_profile as profile
from book_evidence_import import (digest,encoded,need,pinned,read_json,public_text_only,
    prepare_increment,transactional_replace,validate_overlay)
from book_pdf_increment import canonical_sha,file_pin

LEDGER_BYTES=91126
CANDIDATE_BYTES=91650
CANDIDATE_SHA='a0d7f41500901dda3e13a1d59f942c21d8b8daad0fd4e2f6d88389fd6facd77a'
METADATA_BYTES=11519
METADATA_SHA='e72da14f2224668fa30df532135bbf8e07bb850f4eadcb3a1aa461dccf14ba1f'
CATALOG_SHA='34e1dc4c293ddab612025eb797353e31a4d41fcf9c298c774bafc41e057b24a8'
CATALOG_BYTES=4759703
WITHHELD_SHA='3a55fbb0a560f3bbc2a66b08016de3891e2538e43d154f42c4e40ff1815065e2'
PRIVATE_BYTES={'new-book-04':53730340,'new-book-07':179514039}
ROOT_FIELDS=('catalog_id','name_en','source_id','source_book_sha256','source_pages','field','value_zh',
             'quantity_kind','unit','hardness_scale','conditions','comparison_status','limits')

def approved_inputs(candidate_raw,ledger_raw,metadata_raw):
    need((len(candidate_raw),digest(candidate_raw))==(CANDIDATE_BYTES,CANDIDATE_SHA)
      and (len(ledger_raw),digest(ledger_raw))==(LEDGER_BYTES,profile.REVIEW_SHA)
      and (len(metadata_raw),digest(metadata_raw))==(METADATA_BYTES,METADATA_SHA),'exact candidate, Root40 ledger and source metadata bytes')
    draft=json.loads(candidate_raw);review=json.loads(ledger_raw);metadata=json.loads(metadata_raw)
    need(review['schema']=='Root-book42-reviewed40-source-statements-v1' and review['authorizer']=='Root'
      and review['state']=='approved_short_source_faithful_statements_only_not_primary_measurements'
      and review['all40Approved'] is True and review['all8_HOLD_must_remain'] is True
      and review['previous_source_conflict_HOLD_must_remain_unchanged'] is True
      and review['whole_book_or_page_image_publication_authorized'] is False
      and review['training_or_model_or_independent_test_admission'] is False
      and review['whole_books_fully_read'] is False,'Root exact secondary-only approval required')
    need(review['source_candidates_pin']['sha256']==CANDIDATE_SHA and review['source_candidates_pin']['bytes']==CANDIDATE_BYTES
      and review['source_metadata_pin']['sha256']==METADATA_SHA and review['source_metadata_pin']['bytes']==METADATA_BYTES
      and review['catalog_at_review_pin']['sha256']==CATALOG_SHA and review['catalog_at_review_pin']['bytes']==CATALOG_BYTES
      and review['withheld_pin']['sha256']==WITHHELD_SHA,'complete approved provenance binding')
    candidates={r['candidate_id']:r for r in draft['records']};approved={}
    need(len(candidates)==len(draft['records'])==len(review['records'])==40,'exact40 unique candidates')
    for row in review['records']:
        cid=row['candidate_id'];need(cid in candidates and cid not in approved,'unique Root-approved candidate identity')
        candidate=candidates[cid]
        need(all(row[k]==candidate[k] for k in ROOT_FIELDS),'candidate/Root source statement correspondence')
        need(row['Root_actual_review'] is row['Root_approved'] is True
          and row['decision']=='approved_as_explicit_book_source_statement_with_conditions'
          and row['no_primary_property_or_current_catalog_formula_overwrite'] is row['no_model_score_or_training_use'] is True
          and re.fullmatch('[a-f0-9]{64}',row['proposal_field_sha256']),'per-record final Root approval')
        need(row['source_id'] in profile.SOURCES and row['source_book_sha256']==profile.SOURCES[row['source_id']],
          'exact two new private source identities')
        approved[cid]=row
    need(set(approved)==set(candidates),'no dropped/unapproved statements')
    return draft,review,metadata,approved

def verify_private_files(review_root,candidate_raw,ledger_raw,metadata_raw):
    _,review,metadata,approved=approved_inputs(candidate_raw,ledger_raw,metadata_raw)
    need(Path(review['source_candidates_pin']['path'])==review_root/'short-candidates.json'
      and Path(review['source_metadata_pin']['path'])==review_root/'source-pins-and-selection.json','exact input owners')
    sources={r['source_id']:r for r in metadata['book_read_allowlist']}
    need(set(sources)==set(profile.SOURCES),'exact two source files; no duplicate edition')
    for sid,size in PRIVATE_BYTES.items():
        source=sources[sid];path=Path(source['private_source_path'])
        need(source['source_bytes']==path.stat().st_size==size and source['source_sha256']==profile.SOURCES[sid],'exact PDF bytes')
        file_pin(path,profile.SOURCES[sid],size)
    views={(v['source_id'],v['pdf_page_1based']):v for v in review['Root_actual_complete_page_views']}
    need(len(views)==len(review['Root_actual_complete_page_views'])==6,'all six distinct actual Root page views')
    for (sid,page),view in views.items():
        need(view['Root_actual_full_page_view'] is True and profile.PAGES[sid][str(page)]=={
          'printed_page':view['printed_page'],'render_sha256':view['sha256']} and 0<view['bytes']<=4*1024**2,'actual complete rendered page pin')
        path=Path(view['path']);need(path.stat().st_size==view['bytes'],'exact render bytes');file_pin(path,view['sha256'],view['bytes'])
    for row in approved.values():
        for page in row['source_pages']:
            v=views.get((row['source_id'],page['pdf_page_1based']))
            need(v is not None and page['printed_page']==v['printed_page'] and page['full_page_render']==v['path']
              and page['full_page_render_sha256']==v['sha256'],'all contributing pages bound to actual Root view')
    held=pinned(review_root/'withheld-fields.json',WITHHELD_SHA,4456);need(len(held)==4456,'all8 withheld bytes retained')
    return {'PDF_files_SHA_verified':2,'PDF_bytes_stream_hashed':sum(PRIVATE_BYTES.values()),'Root_viewed_render_pins_SHA_verified':6,
      'withheld_ledger_unchanged':True,'native_text_or_full_page_extraction_performed':False,'Root_actual_page_views_not_reclaimed_as_agent_views':True}

def public_increment(catalog,candidate_raw,ledger_raw,metadata_raw):
    _,review,metadata,approved=approved_inputs(candidate_raw,ledger_raw,metadata_raw)
    minerals={r['id']:r for r in catalog['minerals']};sources={r['source_id']:r for r in metadata['book_read_allowlist']}
    books={};rows=[]
    for cid,fact in approved.items():
        mid=fact['catalog_id'];need(mid in minerals and minerals[mid]['name_en']==fact['name_en']
          and minerals[mid]['formula']==fact['current_catalog_formula'],'exact existing catalog species/formula')
        sid=fact['source_id'];source=sources[sid]
        if sid not in books:
            books[sid]={'source_id':sid,**profile.public_bibliography(sid),
              'book_sha256':profile.SOURCES[sid],'root_review_sha256':profile.REVIEW_SHA,'status':'reviewed_selected_pages',
              'source_format':'PDF','full_book_reviewed':False,'subjects':[]}
        pages=[{'pdf_page_1based':v['pdf_page_1based'],'printed_page':v['printed_page'],'render_sha256':v['full_page_render_sha256']} for v in fact['source_pages']]
        row={'catalog_id':mid,'name_en':fact['name_en'],'source_id':sid,'pdf_page_1based':pages[0]['pdf_page_1based'],
          'printed_page':pages[0]['printed_page'],'table_number':None,'source_pages':pages,'field':fact['field'],'value':fact['value_zh'],
          'status':'reviewed_source_statement','quantity_kind':fact['quantity_kind'],'unit':fact['unit'],'hardness_scale':fact['hardness_scale'],
          'limits':deepcopy(fact['limits']),'conditions':deepcopy(fact['conditions']),'comparison_status':fact['comparison_status'],
          'review':{'decision':'approved_source_statement','approved_candidate_id':cid,'root_record_sha256':profile.REVIEW_SHA,
            'source_book_sha256':profile.SOURCES[sid],'source_evidence_sha256':canonical_sha(pages),'proposal_field_sha256':fact['proposal_field_sha256']}}
        profile.validate_row(row);rows.append(row)
        subject=next((s for s in books[sid]['subjects'] if s['catalog_id']==mid and s['pdf_page_1based']==row['pdf_page_1based']),None)
        if subject is None:
            subject={k:row[k] for k in ('catalog_id','name_en','pdf_page_1based','printed_page','table_number')};subject['approved_fields']=[];books[sid]['subjects'].append(subject)
        subject['approved_fields'].append(row['field'])
    need(len(rows)==40 and len(books)==2,'exact40 statements / two distinct new sources')
    incoming={'schema_version':1,'scope':'secondary_book_source_statements','primary_properties_changed':False,'model_scope_changed':False,
      'books':list(books.values()),'records':rows,'withheld':[],
      'counts':{'reviewed_source_statements':40,'selected_source_pages':6,'withheld_fields':0,'full_book_reviewed':False}}
    validate_overlay(incoming,catalog);public_text_only(incoming);return incoming

def prepare_bibliography_appendix(catalog_raw,manifest_raw,approval_raw):
    """Exact Root bibliography correction only; all statement decisions immutable."""
    need((len(approval_raw),digest(approval_raw))==(profile.BIBLIOGRAPHY_REVIEW_BYTES,profile.BIBLIOGRAPHY_REVIEW_SHA),'exact Root bibliography approval bytes')
    approval=json.loads(approval_raw);need(approval['authorizer']=='Root' and approval['content40_ledger_unchanged'] is True,'Root bibliography-only scope required')
    catalog=json.loads(catalog_raw);manifest=json.loads(manifest_raw);old=catalog['reviewed_book_evidence']
    need(catalog['count']==len(catalog['minerals'])==6239 and len(old['records'])==118 and len(old['books'])==9,'exact current6239/118/9 bibliography appendix baseline')
    entries=[row for row in manifest['files'] if row['path']=='data/catalog.json'];need(len(entries)==1,'one current catalog manifest member')
    entry=entries[0]
    need(entry['bytes']==len(catalog_raw) and entry['sha256']==digest(catalog_raw),'current catalog/manifest binding')
    result=deepcopy(catalog);overlay=result['reviewed_book_evidence'];updated=[]
    for book in overlay['books']:
        sid=book['source_id']
        if sid not in profile.SOURCES:continue
        need(book['book_sha256']==profile.SOURCES[sid]==approval['approved_books'][sid]['source_sha256'],'exact two source identities')
        book.update(profile.public_bibliography(sid));updated.append(sid)
    need(set(updated)==set(profile.SOURCES) and len(updated)==2,'only exact two bibliography owners')
    validate_overlay(overlay,result)
    need(overlay['records']==old['records'] and overlay['withheld']==old['withheld'] and overlay['counts']==old['counts']
      and overlay['books'][:7]==old['books'][:7]
      and all(a['subjects']==b['subjects'] for a,b in zip(overlay['books'],old['books'])),'all118 statements/old7/HOLD/subjects unchanged')
    after=encoded(result)
    def mineral_bytes(raw):
        text=raw.decode('utf-8');start=text.index('"minerals":')+len('"minerals":')
        while text[start].isspace():start+=1
        _,end=json.JSONDecoder().raw_decode(text,start)
        return text[start:end].encode('utf-8')
    need(mineral_bytes(after)==mineral_bytes(catalog_raw),'all6239 primary array original bytes unchanged')
    updated_manifest=deepcopy(manifest)
    next(row for row in updated_manifest['files'] if row['path']=='data/catalog.json').update(bytes=len(after),sha256=digest(after))
    return after,(json.dumps(updated_manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode(),{'schema':'book42-Root-bibliography-appendix-v1','Root_bibliography_sha256':profile.BIBLIOGRAPHY_REVIEW_SHA,
      'updated_sources':updated,'all118_statements_old7_HOLD_and_subjects_exact':True,'all6239_primary_array_bytes_exact':True,
      'counts_unchanged':overlay['counts'],'only_book_bibliography_and_catalog_manifest_identity_changed':True}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--review-root',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--apply-to-local-app',action='store_true');a=parser.parse_args()
    repo=a.repo.resolve();root=a.review_root.resolve();out=a.output_dir.resolve();need(not out.exists(),'fresh bounded output directory')
    candidate=pinned(root/'short-candidates.json',CANDIDATE_SHA,CANDIDATE_BYTES)
    ledger=pinned(root/'Root-approved-source-statements40.json',profile.REVIEW_SHA,LEDGER_BYTES)
    metadata=pinned(root/'source-pins-and-selection.json',METADATA_SHA,METADATA_BYTES)
    checks=verify_private_files(root,candidate,ledger,metadata)
    cp=repo/'data/catalog.json';mp=repo/'data/reference-manifest.json';before=[cp.read_bytes(),mp.read_bytes()]
    need((len(before[0]),digest(before[0]))==(CATALOG_BYTES,CATALOG_SHA),'exact Root-reviewed78 catalog baseline')
    catalog=read_json(cp);manifest=read_json(mp);old=catalog['reviewed_book_evidence']
    need(catalog['count']==len(catalog['minerals'])==6239 and len(old['records'])==78 and len(old['books'])==7,'old6239/78/7 baseline')
    entries=[v for v in manifest['files'] if v['path']=='data/catalog.json']
    need(len(entries)==1 and entries[0]['bytes']==len(before[0]) and entries[0]['sha256']==digest(before[0]),'catalog manifest baseline identity')
    incoming=public_increment(catalog,candidate,ledger,metadata);catraw,manraw,overlay=prepare_increment(catalog,manifest,incoming)
    need(json.loads(catraw)['minerals']==catalog['minerals'] and overlay['records'][:78]==old['records']
      and overlay['books'][:7]==old['books'] and overlay['withheld']==old['withheld'],'all primary objects /78 statements /old7 books /HOLD unchanged')
    out.mkdir(parents=True);(out/'public-book-increment.json').write_bytes(encoded(incoming))
    if a.apply_to_local_app:transactional_replace(cp,mp,catraw,manraw,before)
    result={'schema':'exact-Root-book42-local-secondary-import-v1','Root_ledger_sha256':profile.REVIEW_SHA,'local_App_applied':a.apply_to_local_app,
      'new_source_statements':40,'new_books':2,'new_complete_source_pages':6,'counts':overlay['counts'],
      'all6239_primary_objects_unchanged':True,'previous78_statements_and7_books_exact':True,'previous_HOLD_exact':True,
      'private_checks':checks,'only_short_Chinese_statements_and_bibliography_public':True,'no_private_paths_full_text_or_page_images':True,
      'primary_property_model_or_training_scope_changed':False,'catalog_bytes':len(catraw),'catalog_sha256':digest(catraw),
      'manifest_sha256':digest(manraw),'commit_push_sync_build_or_deploy':False}
    (out/'local-import-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
