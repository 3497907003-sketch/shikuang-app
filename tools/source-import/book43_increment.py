#!/usr/bin/env python3
"""Append the exact Root-approved Chinese56 metadata. No book/image/model I/O."""
from copy import deepcopy
from pathlib import Path
import argparse,hashlib,json
import book43_profile as profile
from book_evidence_import import (digest,encoded,need,pinned,public_text_only,read_json,
    prepare_increment,transactional_replace,validate_overlay)

LEDGER_BYTES=145838
CANDIDATE_BYTES=155329
CANDIDATE_SHA='c55c9ff9548fb32707c70f9aa048b73256559ee2fa9f23adaf22b601d93b51e8'
HOLD_BYTES=6152
HOLD_SHA='f3864b3eaf0232c031cfb7b8eb96d011627962c5675d3d342c8e2341a10da176'
CATALOG_BYTES=4819086
CATALOG_SHA='16d8b65bed358cfbe494e1a6ed1158c80560dc360cad4ec360cc68e6b24714f9'
HISTORICAL_CATALOG_SHA='dcae79545479d3a8d3045c5d0fcd33b1970419a56e3580bedddbbe5f37f79954'
HASH_ALGORITHM='SHA256 UTF8(json.dumps(original record excluding proposal_field_sha256, ensure_ascii=False, sort_keys=True, default separators, no indent) plus LF)'


def source_field_hash(record):
    original={k:v for k,v in record.items() if k!='proposal_field_sha256'}
    return digest((json.dumps(original,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode())


def approved_inputs(candidate_raw,ledger_raw,hold_raw):
    need((len(candidate_raw),digest(candidate_raw))==(CANDIDATE_BYTES,CANDIDATE_SHA)
      and (len(ledger_raw),digest(ledger_raw))==(LEDGER_BYTES,profile.REVIEW_SHA)
      and (len(hold_raw),digest(hold_raw))==(HOLD_BYTES,HOLD_SHA),'exact immutable candidate, Root56 approval and prior14 HOLD pins required')
    candidate=json.loads(candidate_raw);ledger=json.loads(ledger_raw);held=json.loads(hold_raw)
    need(ledger['schema']=='Root-Chinese56-reviewed-source-statements-v1' and ledger['authorizer']=='Root'
      and ledger['state']=='approved_short_source_faithful_statements_only_not_primary_measurements'
      and ledger['all56Approved'] is True and ledger['all_prior_HOLD_or_exclusions_retained'] is True
      and ledger['current_ID_name_formula_and_no_prior118_field_duplicates_revalidated'] is True
      and ledger['whole_books_fully_read'] is ledger['whole_page_images_or_native_OCR_publication'] is ledger['training_or_model_or_independent_test_admission'] is False,'final Root secondary-only authority required')
    need(ledger['source_field_hash_algorithm']==HASH_ALGORITHM,'explicit original-candidate hash semantics required')
    need(ledger['candidate_pin']['bytes']==CANDIDATE_BYTES and ledger['candidate_pin']['sha256']==CANDIDATE_SHA
      and ledger['prior14_HOLD_and_exclusion_pin']['bytes']==HOLD_BYTES and ledger['prior14_HOLD_and_exclusion_pin']['sha256']==HOLD_SHA
      and ledger['current_catalog_at_approval']['bytes']==CATALOG_BYTES and ledger['current_catalog_at_approval']['sha256']==CATALOG_SHA
      and ledger['candidate_historical_catalog_pin_retained']['sha256']==candidate['catalog_pin']['sha256']==HISTORICAL_CATALOG_SHA,'historical/current provenance must remain distinct')
    originals={r['candidate_id']:r for r in candidate['records']}
    need(len(originals)==len(candidate['records'])==57 and candidate['Root_approved'] is candidate['App_import_approved'] is False,'57 immutable pending proposals required')
    need(all(source_field_hash(r)==r['proposal_field_sha256'] for r in originals.values()),'all57 original proposal hashes must recompute with declared default separators and LF')
    approved={r['candidate_id']:r for r in ledger['records']}
    need(len(approved)==len(ledger['records'])==56 and set(approved)==set(profile.APPROVED)
      and set(approved)==set(originals)-{'Chinese42-023'},'exact56 exclude unresolved Qusongite occurrence')
    excluded={'agent_checks','status','Root_approved','App_import_approved'}
    for cid,row in approved.items():
        original=originals[cid]
        need(all(row[k]==v for k,v in original.items() if k not in excluded),'every approved source value/condition/locator must match original proposal')
        need(row['Root_actual_review'] is row['Root_approved'] is True
          and row['no_primary_property_or_current_catalog_formula_overwrite'] is row['no_model_score_or_training_use'] is True
          and row['decision']=='approved_as_explicit_book_source_statement_with_conditions','per-row Root approval required')
        if row['field']=='formula':
            formula='Zr[SiO4]' if cid=='Chinese42-007' else original['source_short_evidence']
            need(row.get('approved_formula_display')==formula,'separate exact approved formula display required')
        else:need('approved_formula_display' not in row,'nonformula cannot gain a formula')
    extra=ledger['additional_HOLD']
    need(len(extra)==1 and extra[0]['candidate_id']=='Chinese42-023' and extra[0]['Root_approved'] is False
      and extra[0]['decision']=='HOLD_pending_primary_occurrence_verification'
      and extra[0]['source_field_hash']==source_field_hash(originals['Chinese42-023']),'new unresolved locality HOLD retained')
    need(len(held['records'])==14 and sum(r['status']=='hold' for r in held['records'])==13
      and sum(r['status']=='excluded_duplicate' for r in held['records'])==1,'prior14 HOLD/exclusions cannot be promoted')
    views={p['pdf_page_1based']:p for p in ledger['Root_actual_complete_page_views']}
    need(len(views)==len(ledger['Root_actual_complete_page_views'])==4,'four actual Root complete-page views required')
    for page,view in views.items():
        need(type(page) is int and view['Root_actual_complete_page_viewed'] is True
          and view['source_id']==profile.SOURCE_ID and view['source_sha256']==profile.SOURCE_SHA
          and profile.PAGES.get(str(page))=={'printed_page':view['printed_page'],'render_sha256':view['sha256']},'Root complete-page source/render pin required')
    for row in approved.values():
        for page in row['source_pages']:
            view=views.get(page['pdf_page_1based']);need(view and page['printed_page']==view['printed_page']
              and page['render_pin']=={k:view[k] for k in ('path','bytes','sha256')},'approved field must bind actual Root-viewed page')
    return candidate,ledger,held


def public_increment(catalog,candidate_raw,ledger_raw,hold_raw):
    _,ledger,_=approved_inputs(candidate_raw,ledger_raw,hold_raw)
    minerals={r['id']:r for r in catalog['minerals']};old=catalog['reviewed_book_evidence']
    need(len(old['records'])==118 and len(old['books'])==9 and old['counts']['selected_source_pages']==16
      and all(b['source_id']!=profile.SOURCE_ID for b in old['books']),'exact118/9/16 before new source')
    existing={(r['catalog_id'],r['field']) for r in old['records']};rows=[];subjects={}
    book=deepcopy(profile.PROFILE['book']);book['subjects']=[]
    bibliography=ledger['bibliography']
    need({k:bibliography[k] for k in ('source_id','title','authors','credit_role')}=={k:book[k] for k in ('source_id','title','authors','credit_role')}
      and bibliography['ISBN'] is None and bibliography['publisher_or_edition_year_not_invented'] is True,'only approved editor credit; no invented ISBN/year/publisher')
    for fact in ledger['records']:
        cid=fact['candidate_id'];mid=fact['catalog_id'];need(mid in minerals and minerals[mid]['name_en']==fact['name_en']
          and minerals[mid]['formula']==fact['current_catalog_formula'] and (mid,fact['field']) not in existing,'current exact catalog identity and no old118 duplicate')
        pages=[{'pdf_page_1based':p['pdf_page_1based'],'printed_page':p['printed_page'],'render_sha256':p['render_pin']['sha256']} for p in fact['source_pages']]
        row={'catalog_id':mid,'name_en':fact['name_en'],'source_id':profile.SOURCE_ID,'pdf_page_1based':pages[0]['pdf_page_1based'],
          'printed_page':pages[0]['printed_page'],'table_number':None,'source_pages':pages,'field':fact['field'],'value':fact['value_zh'],
          'status':'reviewed_source_statement','quantity_kind':fact['quantity_kind'],'unit':None,'hardness_scale':None,
          'conditions':deepcopy(fact['conditions']),'limits':sorted(profile.REQUIRED_LIMITS|{'no_current_specimen_measurement_or_assay_or_origin_assignment'}),
          'comparison_status':'source_statement_only',
          'review':{'decision':'approved_source_statement','approved_candidate_id':cid,'root_record_sha256':profile.REVIEW_SHA,
            'source_book_sha256':profile.SOURCE_SHA,'source_evidence_sha256':profile.canonical_sha(pages),'proposal_field_sha256':fact['proposal_field_sha256']}}
        if fact['field']=='formula':row['formula_display']=fact['approved_formula_display']
        profile.validate_row(row);rows.append(row)
        key=(mid,row['pdf_page_1based'])
        subject=subjects.setdefault(key,{k:row[k] for k in ('catalog_id','name_en','pdf_page_1based','printed_page','table_number')})
        subject.setdefault('approved_fields',[]).append(row['field'])
    book['subjects']=list(subjects.values())
    incoming={'schema_version':1,'scope':'secondary_book_source_statements','primary_properties_changed':False,'model_scope_changed':False,
      'books':[book],'records':rows,'withheld':[],'counts':{'reviewed_source_statements':56,'selected_source_pages':4,'withheld_fields':0,'full_book_reviewed':False}}
    validate_overlay(incoming,catalog);public_text_only(incoming);return incoming


def value_bytes(raw,key):
    text=raw.decode();start=text.index(json.dumps(key)+':')+len(json.dumps(key))+1
    while text[start].isspace():start+=1
    _,end=json.JSONDecoder().raw_decode(text,start)
    return text[start:end].encode()


def prepare(catalog_raw,manifest_raw,candidate_raw,ledger_raw,hold_raw):
    need((len(catalog_raw),digest(catalog_raw))==(CATALOG_BYTES,CATALOG_SHA),'exact current Root-approved catalog binding; old historical pin cannot apply')
    catalog=json.loads(catalog_raw);manifest=json.loads(manifest_raw)
    entry=[r for r in manifest['files'] if r['path']=='data/catalog.json']
    need(len(entry)==1 and entry[0]['bytes']==len(catalog_raw) and entry[0]['sha256']==digest(catalog_raw),'current reference manifest identity required')
    incoming=public_increment(catalog,candidate_raw,ledger_raw,hold_raw)
    catraw,manraw,overlay=prepare_increment(catalog,manifest,incoming);old=catalog['reviewed_book_evidence']
    need(overlay['records'][:118]==old['records'] and overlay['books'][:9]==old['books'] and overlay['withheld']==old['withheld'],'all old118/9/HOLD objects exact')
    need(value_bytes(catraw,'minerals')==value_bytes(catalog_raw,'minerals'),'all6239 primary array original bytes exact')
    before=value_bytes(catalog_raw,'reviewed_book_evidence');after=value_bytes(catraw,'reviewed_book_evidence')
    for key in ('records','books'):
        prior=value_bytes(before,key);next_value=value_bytes(after,key)
        need(next_value.startswith(prior[:-1]+b','),'old '+key+' original array element bytes retained as prefix')
    need(value_bytes(before,'withheld')==value_bytes(after,'withheld'),'old public HOLD array bytes exact')
    need(overlay['counts']=={'reviewed_source_statements':174,'selected_source_pages':20,'withheld_fields':1,'full_book_reviewed':False}
      and len(overlay['books'])==10 and len({r['catalog_id'] for r in overlay['records']})==61,'exact174/10/20/61 result')
    return catraw,manraw,overlay,incoming


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--review-root',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--apply-to-local-app',action='store_true');a=parser.parse_args()
    repo=a.repo.resolve();root=a.review_root.resolve();out=a.output_dir.resolve();need(not out.exists(),'fresh bounded output directory')
    candidate=pinned(root/'short-candidates.Root-review-pending.json',CANDIDATE_SHA,CANDIDATE_BYTES)
    ledger=pinned(root/'Root-approved-source-statements56-resume43.json',profile.REVIEW_SHA,LEDGER_BYTES)
    held=pinned(root/'withheld-or-excluded-fields.json',HOLD_SHA,HOLD_BYTES)
    cp=repo/'data/catalog.json';mp=repo/'data/reference-manifest.json';before=[cp.read_bytes(),mp.read_bytes()]
    catraw,manraw,overlay,incoming=prepare(*before,candidate,ledger,held)
    out.mkdir(parents=True);(out/'public-book-increment.json').write_bytes(encoded(incoming))
    decisions={'prior14_immutable_pin':{'bytes':HOLD_BYTES,'sha256':HOLD_SHA},'prior14_original_file_unchanged':True,
      'additional_HOLD':json.loads(ledger)['additional_HOLD'],'total_HOLD_or_excluded':15,'held_values_added_to_public_App':False}
    (out/'retained-HOLD-decisions.json').write_text(json.dumps(decisions,ensure_ascii=False,indent=2)+'\n')
    if a.apply_to_local_app:transactional_replace(cp,mp,catraw,manraw,before)
    result={'schema':'exact-Root-Chinese56-local-secondary-import-v1','Root_ledger_sha256':profile.REVIEW_SHA,'local_App_applied':a.apply_to_local_app,
      'new_source_statements':56,'new_source_books':1,'counts':overlay['counts'],'book_sources':10,'book_species':61,
      'all57_original_candidate_proposal_hashes_recomputed':True,'candidate_original_pending_flags_unchanged':True,
      'all6239_primary_and_old118_old9_HOLD_original_bytes_preserved':True,'private_HOLD_or_exclusions_preserved':15,
      'formula_displays_separate_from_original_narrative':23,'original_book_PDF_or_render_payloads_reopened':False,
      'primary_property_model_or_training_scope_changed':False,'catalog_bytes':len(catraw),'catalog_sha256':digest(catraw),
      'manifest_bytes':len(manraw),'manifest_sha256':digest(manraw),'commit_push_sync_build_or_deploy':False}
    (out/'local-import-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
