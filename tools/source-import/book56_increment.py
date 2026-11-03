#!/usr/bin/env python3
"""Append exact10 Root-reviewed secondary statements to existing book17.

Only metadata is read. Book/image/model/network I/O and primary edits are absent.
--apply-to-local-app uses the existing transactional catalog/manifest update.
"""
from copy import deepcopy
from pathlib import Path
import argparse,json
import book56_profile as profile
from book_evidence_import import digest,encoded,need,pinned,prepare_increment,transactional_replace,validate_overlay,public_text_only
from book43_increment import value_bytes

CANDIDATE_BYTES=25294
CANDIDATE_SHA='cdbf100e2d5ee48dc9b0abaeaa8e4b463b54dc82c45d5966342f07e964824b5d'
APPROVAL_BYTES=2029
CATALOG_BYTES=4934911
CATALOG_SHA='d615612b316b355486d16c4e965a63570da716ba329da0dfe408fbbe48c62698'

def canonical_sha(value):
    return digest(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode())

def approved_inputs(candidate_raw,approval_raw):
    need((len(candidate_raw),digest(candidate_raw))==(CANDIDATE_BYTES,CANDIDATE_SHA)
      and (len(approval_raw),digest(approval_raw))==(APPROVAL_BYTES,profile.REVIEW_SHA),
      'exact immutable candidate and separate Root10 source approval required')
    proposal=json.loads(candidate_raw);approval=json.loads(approval_raw)
    need(approval['schema']=='Root-book56-secondary-source-review-v1' and approval['reviewer']=='Root'
      and approval['source_id']==profile.SOURCE_ID and approval['source_book_sha256']==profile.SOURCE_SHA
      and approval['candidate_pin']['bytes']==CANDIDATE_BYTES and approval['candidate_pin']['sha256']==CANDIDATE_SHA
      and approval['English_names_only_where_Chinese_unreviewed'] is True
      and approval['page332_arsenopyrite_HOLD_retained'] is True and approval['full_book_reviewed'] is False,
      'Root-approved secondary-only scope and source/HOLD bindings required')
    candidates={r['candidate_id']:r for r in proposal['candidates']}
    need(len(candidates)==10 and set(candidates)==set(profile.ROWS)==set(approval['approved_secondary_statement_ids'])
      and proposal['approved_by_Root'] is proposal['App_or_training_imported'] is False,
      'pending original proposal remains immutable; all10 require separate Root authority')
    views={Path(v['path']).name:v for v in approval['actually_viewed_full_rendered_pages']}
    for cid,fact in candidates.items():
        original={k:v for k,v in fact.items() if k!='proposal_field_sha256'}
        need(canonical_sha(original)==fact['proposal_field_sha256'],'original field proposal hash changed')
        loc=fact['source_locator'];view=views.get('page-%03d.png'%loc['pdf_page_1based'])
        need(view and view['sha256']==loc['render_sha256'] and fact['name_zh'] is None
          and fact['source_id']==profile.SOURCE_ID and fact['source_sha256']==profile.SOURCE_SHA,
          'exact Root-viewed source page and unreviewed Chinese name scope')
        row=profile.ROWS[cid]
        need(all(row[k]==fact[k] for k in ('catalog_id','name_en','source_id','field','quantity_kind','unit','hardness_scale','conditions','limits'))
          and row['value']==fact['value_zh'] and row['review']['proposal_field_sha256']==fact['proposal_field_sha256']
          and row['pdf_page_1based']==loc['pdf_page_1based'] and row['printed_page']==loc['printed_page'],
          'finite public row must reproduce exact original facts, page and quantity semantics')
        profile.validate_row(row)
    return proposal,approval

def public_increment(catalog,candidate_raw,approval_raw):
    proposal,_=approved_inputs(candidate_raw,approval_raw);old=catalog['reviewed_book_evidence']
    need(len(old['records'])==190 and len(old['books'])==11 and old['counts']['selected_source_pages']==23,'exact190/11/23 baseline required')
    books=[b for b in old['books']if b['source_id']==profile.SOURCE_ID];need(len(books)==1 and profile.valid_book(books[0]),'existing book17 identity/editor metadata must stay exact')
    minerals={m['id']:m for m in catalog['minerals']};book=deepcopy(books[0]);book['subjects']=[];subjects={};rows=[]
    for fact in proposal['candidates']:
        row=deepcopy(profile.ROWS[fact['candidate_id']]);mid=row['catalog_id'];m=minerals.get(mid)
        need(m and m['name_en']==fact['name_en'] and m['formula']==fact['current_catalog_formula']
          and 'physical_properties'not in m and not any(x['catalog_id']==mid for x in old['records']),
          'exact original catalog identity and genuinely new secondary subjects required')
        rows.append(row);subject=subjects.setdefault((mid,row['pdf_page_1based']),{k:row[k]for k in ('catalog_id','name_en','pdf_page_1based','printed_page','table_number')})
        subject.setdefault('approved_fields',[]).append(row['field']);subject['root_review_sha256']=profile.REVIEW_SHA
    book['subjects']=list(subjects.values())
    incoming=dict(schema_version=1,scope='secondary_book_source_statements',primary_properties_changed=False,model_scope_changed=False,books=[book],records=rows,withheld=[],counts=dict(reviewed_source_statements=10,selected_source_pages=2,withheld_fields=0,full_book_reviewed=False))
    validate_overlay(incoming,catalog);public_text_only(incoming);return incoming

def prepare(catalog_raw,manifest_raw,candidate_raw,approval_raw):
    need((len(catalog_raw),digest(catalog_raw))==(CATALOG_BYTES,CATALOG_SHA),'exact reviewed190 baseline; changed or repeated baseline rejected')
    c=json.loads(catalog_raw);m=json.loads(manifest_raw);entries=[r for r in m['files']if r['path']=='data/catalog.json']
    need(len(entries)==1 and entries[0]['bytes']==len(catalog_raw) and entries[0]['sha256']==digest(catalog_raw),'current reference manifest/catalog binding')
    incoming=public_increment(c,candidate_raw,approval_raw);catraw,manraw,overlay=prepare_increment(c,m,incoming);old=c['reviewed_book_evidence']
    need(value_bytes(catraw,'minerals')==value_bytes(catalog_raw,'minerals'),'all6239 primary object bytes preserved')
    need(overlay['records'][:190]==old['records'] and overlay['withheld']==old['withheld'] and len(overlay['books'])==11,'all190 records/11 owners/HOLD preserved')
    before=value_bytes(catalog_raw,'reviewed_book_evidence');after=value_bytes(catraw,'reviewed_book_evidence')
    need(value_bytes(after,'records').startswith(value_bytes(before,'records')[:-1]+b',') and value_bytes(after,'withheld')==value_bytes(before,'withheld'),'old190 record and HOLD bytes unchanged')
    for oldbook,newbook in zip(old['books'],overlay['books']):
        need({k:v for k,v in oldbook.items()if k!='subjects'}=={k:v for k,v in newbook.items()if k!='subjects'} and newbook['subjects'][:len(oldbook['subjects'])]==oldbook['subjects'],'existing owner metadata and subjects unchanged')
    need(overlay['counts']==dict(reviewed_source_statements=200,selected_source_pages=25,withheld_fields=1,full_book_reviewed=False) and len({r['catalog_id']for r in overlay['records']})==71,'exact200/25/71 secondary result')
    return catraw,manraw,overlay,incoming

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--review-root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--apply-to-local-app',action='store_true');a=p.parse_args()
    repo=a.repo.resolve();review=a.review_root.resolve();out=a.output_dir.resolve();need(not out.exists(),'fresh output evidence directory')
    candidate=pinned(review/'book56-candidates.Root-review-pending.json',CANDIDATE_SHA,CANDIDATE_BYTES)
    approval=pinned(review/'ROOT-SECONDARY-SOURCE-REVIEW.json',profile.REVIEW_SHA,APPROVAL_BYTES)
    cp=repo/'data/catalog.json';mp=repo/'data/reference-manifest.json';before=[cp.read_bytes(),mp.read_bytes()]
    catraw,manraw,o,incoming=prepare(*before,candidate,approval);out.mkdir(parents=True);(out/'public-increment.json').write_bytes(encoded(incoming))
    if a.apply_to_local_app:transactional_replace(cp,mp,catraw,manraw,before)
    report=dict(schema='book56-local-secondary-increment-v1',applied=a.apply_to_local_app,added_statements=10,added_subject_species=8,book_owners=11,counts=o['counts'],all_old190_primary6239_and_HOLD_bytes_preserved=True,book17_existing_owner_and_editor_metadata_preserved=True,new_primary_verified_properties=0,new_model_labels=0,Chinese_names_invented=0,book_or_render_or_training_IO=False,catalog_bytes=len(catraw),catalog_sha256=digest(catraw),manifest_bytes=len(manraw),manifest_sha256=digest(manraw),Root_review_sha256=profile.REVIEW_SHA)
    (out/'import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
