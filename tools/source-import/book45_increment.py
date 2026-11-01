#!/usr/bin/env python3
"""Deterministic Root16 secondary increment; no book, picture, model or network I/O.

Reproduce from the exact174 baseline. Reapplying to another baseline is rejected
instead of duplicating statements. Only --apply-to-local-app mutates two local
public data files, with the existing transactional rollback mechanism.
"""
from copy import deepcopy
from pathlib import Path
import argparse,json
import book45_profile as profile
from book_evidence_import import (digest,encoded,need,pinned,public_text_only,
    prepare_increment,transactional_replace,validate_overlay)
from book43_increment import value_bytes

APPROVAL_BYTES=44420
CANDIDATE_BYTES=45777
CANDIDATE_SHA='adda16d442c2d45cc4b6fc87cc9623c00121f42f52687dcee9a15c3054b6f24a'
HOLD_BYTES=1942
HOLD_SHA='979d679f932ab2bbd8872b3b508cc951b12f6a56ef72b1293c4761e3ca4a68fa'
CATALOG_BYTES=4909626
CATALOG_SHA='0ec5ec2d6cf44da6e3d5dc1425cdf40c2d9cb1282192a11e6283053c1745d00d'

def source_field_hash(record):
    return digest((json.dumps({k:v for k,v in record.items() if k!='proposal_field_sha256'},
        ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode())

def approved_inputs(candidate_raw,approval_raw,hold_raw):
    need((len(candidate_raw),digest(candidate_raw))==(CANDIDATE_BYTES,CANDIDATE_SHA)
      and (len(approval_raw),digest(approval_raw))==(APPROVAL_BYTES,profile.REVIEW_SHA)
      and (len(hold_raw),digest(hold_raw))==(HOLD_BYTES,HOLD_SHA),
      'exact immutable proposal, Root16 approval and five HOLD groups required')
    candidate=json.loads(candidate_raw);approval=json.loads(approval_raw);held=json.loads(hold_raw)
    need(approval['schema']=='Root-reviewed-China-minerals16-secondary-statement-approval-v1'
      and approval['decision']=='approved_source_statements_for_App_integration'
      and approval['approved_statements']==16 and approval['all5_withheld_groups_retained'] is True,
      'final Root16 selected-page source authority required')
    need(approval['proposal']['sha256']==CANDIDATE_SHA and approval['proposal']['bytes']==CANDIDATE_BYTES
      and approval['withheld']['sha256']==HOLD_SHA and approval['withheld']['bytes']==HOLD_BYTES
      and approval['current_catalog_pin']['sha256']==CATALOG_SHA
      and approval['current_catalog_pin']['bytes']==CATALOG_BYTES,'exact approval source/baseline bindings')
    originals={r['candidate_id']:r for r in candidate['records']}
    need(len(originals)==len(candidate['records'])==16 and set(originals)==set(profile.APPROVED)
      and all(source_field_hash(r)==r['proposal_field_sha256'] for r in originals.values()),
      'all16 original proposal hashes and exact candidate IDs must reproduce')
    need(approval['records']==candidate['records'] and set(approval['approved_candidate_IDs'])==set(originals),
      'Root approved the exact original narratives/conditions, not mutated pending flags')
    need(candidate['Root_approved'] is candidate['App_import_approved'] is False,
      'immutable proposal remains pending; separate exact Root authority is required')
    views=approval['Root_actual_full_page_visual_review']
    need(views['content_PDF_pages']==[10,11,12,13] and views['bibliography_PDF_pages']==[3,4]
      and views['source_content_pages_with_fields']==[10,11,13] and views['page12_does_not_add_fields'] is True,
      'pure-photo page12 cannot add a field or an admitted source page')
    req=approval['integration_requirements']
    need(req['source_credit_role']=='compiler' and req['visible_credit_label']=='编者'
      and req['bibliography']=={'publisher':'上海科学技术出版社','edition':'1980年12月第1版、第1次印刷',
        'publication_year':1980,'ISBN':None,'do_not_invent_ISBN':True}
      and req['formula_display']=={'Chinese44-001':'Cu','Chinese44-008':'CuFeS₂'}
      and req['printed_page_must_remain_null'] is True,'exact compiler, historical bibliography and literal formulas')
    need(len(held)==5 and all(r['App_import_approved'] is False for r in held),
      'all five private HOLD groups remain excluded')
    return candidate,approval,held

def public_increment(catalog,candidate_raw,approval_raw,hold_raw):
    _,approval,_=approved_inputs(candidate_raw,approval_raw,hold_raw)
    minerals={m['id']:m for m in catalog['minerals']};old=catalog['reviewed_book_evidence']
    need(len(old['records'])==174 and len(old['books'])==10
      and old['counts']['selected_source_pages']==20
      and not any(b['source_id']==profile.SOURCE_ID for b in old['books']),
      'exact174/10/20 before a new reviewed source')
    rows=[];subjects={};existing={(r['catalog_id'],r['field']) for r in old['records']}
    book=deepcopy(profile.PROFILE['book']);book['subjects']=[]
    for fact in approval['records']:
        cid=fact['candidate_id'];mid=fact['catalog_id'];need(mid in minerals
          and minerals[mid]['name_en']==fact['name_en'] and minerals[mid]['formula']==fact['current_catalog_formula']
          and (mid,fact['field']) not in existing,'exact catalog identity; no old174 source-field replacement')
        pages=[{'pdf_page_1based':p['pdf_page_1based'],'printed_page':p['printed_page'],
          'render_sha256':p['render_pin']['sha256']} for p in fact['source_pages']]
        row={'catalog_id':mid,'name_en':fact['name_en'],'source_id':profile.SOURCE_ID,
          'pdf_page_1based':pages[0]['pdf_page_1based'],'printed_page':None,'table_number':None,
          'source_pages':pages,'field':fact['field'],'value':fact['value_zh'],'status':'reviewed_source_statement',
          'quantity_kind':fact['quantity_kind'],'unit':None,'hardness_scale':None,
          'conditions':deepcopy(fact['conditions']),'limits':sorted(profile.REQUIRED_LIMITS),
          'comparison_status':'source_statement_only','review':{'decision':'approved_source_statement',
            'approved_candidate_id':cid,'root_record_sha256':profile.REVIEW_SHA,
            'source_book_sha256':profile.SOURCE_SHA,'source_evidence_sha256':profile.canonical_sha(pages),
            'proposal_field_sha256':fact['proposal_field_sha256']}}
        if fact['field']=='formula':row['formula_display']=approval['integration_requirements']['formula_display'][cid]
        profile.validate_row(row);rows.append(row)
        subject=subjects.setdefault((mid,row['pdf_page_1based']),
          {k:row[k] for k in ('catalog_id','name_en','pdf_page_1based','printed_page','table_number')})
        subject.setdefault('approved_fields',[]).append(row['field'])
    book['subjects']=list(subjects.values())
    incoming={'schema_version':1,'scope':'secondary_book_source_statements','primary_properties_changed':False,
      'model_scope_changed':False,'books':[book],'records':rows,'withheld':[],
      'counts':{'reviewed_source_statements':16,'selected_source_pages':3,'withheld_fields':0,'full_book_reviewed':False}}
    validate_overlay(incoming,catalog);public_text_only(incoming);return incoming

def prepare(catalog_raw,manifest_raw,candidate_raw,approval_raw,hold_raw):
    need((len(catalog_raw),digest(catalog_raw))==(CATALOG_BYTES,CATALOG_SHA),
      'exact current Root-approved174 baseline; no changed or repeated baseline')
    catalog=json.loads(catalog_raw);manifest=json.loads(manifest_raw)
    entries=[r for r in manifest['files'] if r['path']=='data/catalog.json']
    need(len(entries)==1 and entries[0]['bytes']==len(catalog_raw)
      and entries[0]['sha256']==digest(catalog_raw),'current reference manifest catalog binding')
    incoming=public_increment(catalog,candidate_raw,approval_raw,hold_raw)
    catraw,manraw,overlay=prepare_increment(catalog,manifest,incoming);old=catalog['reviewed_book_evidence']
    need(overlay['records'][:174]==old['records'] and overlay['books'][:10]==old['books']
      and overlay['withheld']==old['withheld'],'all old174/10/HOLD objects preserved')
    need(value_bytes(catraw,'minerals')==value_bytes(catalog_raw,'minerals'),'all6239 original primary array bytes exact')
    before=value_bytes(catalog_raw,'reviewed_book_evidence');after=value_bytes(catraw,'reviewed_book_evidence')
    for key in ('records','books'):
        prior=value_bytes(before,key);current=value_bytes(after,key)
        need(current.startswith(prior[:-1]+b','),'old '+key+' original element bytes retained as prefix')
    need(value_bytes(before,'withheld')==value_bytes(after,'withheld'),'all old public HOLD bytes preserved')
    need(overlay['counts']=={'reviewed_source_statements':190,'selected_source_pages':23,
      'withheld_fields':1,'full_book_reviewed':False} and len(overlay['books'])==11
      and len({r['catalog_id'] for r in overlay['records']})==63,'exact190/11/23/63 result')
    return catraw,manraw,overlay,incoming

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--review-root',type=Path,required=True);parser.add_argument('--approval',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--apply-to-local-app',action='store_true');a=parser.parse_args()
    repo=a.repo.resolve();review=a.review_root.resolve();out=a.output_dir.resolve();need(not out.exists(),'fresh import evidence directory')
    candidate=pinned(review/'short-candidates.Root-review-pending.json',CANDIDATE_SHA,CANDIDATE_BYTES)
    approval=pinned(a.approval.resolve(),profile.REVIEW_SHA,APPROVAL_BYTES)
    held=pinned(review/'withheld-or-excluded-fields.json',HOLD_SHA,HOLD_BYTES)
    cp=repo/'data/catalog.json';mp=repo/'data/reference-manifest.json';before=[cp.read_bytes(),mp.read_bytes()]
    catraw,manraw,overlay,incoming=prepare(*before,candidate,approval,held)
    out.mkdir(parents=True);(out/'public-book-increment.json').write_bytes(encoded(incoming))
    if a.apply_to_local_app:transactional_replace(cp,mp,catraw,manraw,before)
    report={'schema':'exact-Root16-China-minerals-local-secondary-import-v1','Root_approval_sha256':profile.REVIEW_SHA,
      'local_App_applied':a.apply_to_local_app,'new_source_statements':16,'new_source_books':1,
      'counts':overlay['counts'],'book_sources':11,'book_species':63,'all16_original_proposal_hashes_recomputed':True,
      'old174_old10_primary6239_and_public_HOLD_original_bytes_preserved':True,
      'private_HOLD_groups_retained':5,'source_credit':'compiler/编者','invented_ISBN':False,
      'formula_displays_separate_from_narrative':2,'selected_complete_content_pages_reviewed':4,
      'content_pages_with_new_fields':3,'book_or_render_payloads_reopened':False,
      'model_or_primary_or_training_scope_changed':False,'catalog_bytes':len(catraw),'catalog_sha256':digest(catraw),
      'manifest_bytes':len(manraw),'manifest_sha256':digest(manraw),'commit_push_sync_build_deploy_or_release':False}
    (out/'local-import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
