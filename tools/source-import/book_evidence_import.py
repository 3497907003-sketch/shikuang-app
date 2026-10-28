#!/usr/bin/env python3
"""Verify Root-reviewed private book sources; publish only short secondary facts.
No source images, ZIP locators, full text, training or primary property edits.
--apply-to-local-app is an explicit local file operation, never deployment.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

FIELDS = {'formula','hardness','relative_density','crystal_system','cleavage','luster','streak'}
SUBJECTS = {'ima-cuprite':'Cuprite','ima-aragonite':'Aragonite','ima-andalusite':'Andalusite','ima-jadeite':'Jadeite'}
SOURCE_TITLES = {'ima-cuprite':'赤铜矿','ima-aragonite':'文石（霰石）','ima-andalusite':'红柱石','ima-jadeite':'硬玉'}
SOURCE_PAGES = {'ima-cuprite':'053','ima-aragonite':'092','ima-andalusite':'159','ima-jadeite':'189'}
ROOT_REVIEW_SHA = '12c4a90a1d8e0c51a16f52e0beec9aea828c15c824767f8bb120df24b2f283a1'
ROOT_LEDGER_SHA = '9d5334c2a0e08b257707e0b3f9e820e37d3c370b032e73f14e479401ed657cd0'
SOURCE_PINS = {
 'book_overlay_contract.py':'469a83a8aa6aedd149eb0853b4b7c136075e7c7f3c60d9f701092ad75ae47cd3',
 'prepare_overlay_once.py':'ceaa9d0ec933b5cd77543dfdb65b6bc01a0a8ce10fffae99002fad1e0f712c4a',
 'bind_root_decisions_once.py':'4bd5b87d3b0a5247d4969e2ee8faf8d60aff675f80b6711486b502ee908cc845',
 'bibliography-display-profile.proposed.json':'968a52fe14ce904198894683f3670008a44d2d4540fa99f4b3901e6a3e73e7ae',
 'reviewed001/book-evidence-overlay.staged-no-App-import.json':'d185d7e2d2474842dcbd79e9436e373145d8fef838ffbeda928293650de9ded2',
}


def need(value, message):
 if not value: raise ValueError(message)


def digest(raw): return hashlib.sha256(raw).hexdigest()


def encoded(value): return (json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()


def read_json(path):
 def unique(pairs):
  result={}
  for key,value in pairs:
   need(key not in result,'duplicate JSON key');result[key]=value
  return result
 return json.loads(path.read_text(),object_pairs_hook=unique,
                   parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))


def pinned(path, expected, maximum=262144):
 need(path.resolve()==path and path.is_file() and not path.is_symlink(),'closed regular source metadata')
 with path.open('rb') as stream: raw=stream.read(maximum+1)
 need(0<len(raw)<=maximum and digest(raw)==expected,'source metadata/code changed: '+path.name)
 return raw


def verified_stage(book_root):
 """Rebuild from two exact saved metadata sources and explicit Root decisions.
 Qualified modules are hash checked before import; no image/book bodies read.
 """
 prep=book_root/'preparation-resume38'
 for name,expected in SOURCE_PINS.items():pinned(prep/name,expected)
 for name in ('book_overlay_contract','prepare_overlay_once','bind_root_decisions_once'):
  spec=importlib.util.spec_from_file_location(name,prep/(name+'.py'));module=importlib.util.module_from_spec(spec)
  sys.modules[name]=module;spec.loader.exec_module(module)
 core=sys.modules['book_overlay_contract'];reader=sys.modules['prepare_overlay_once'];adapter=sys.modules['bind_root_decisions_once']
 values={};pins={}
 for key,(name,size,expected) in reader.INPUTS.items():
  path=book_root/'evidence/epub-entry4'/name;raw=pinned(path,expected);need(len(raw)==size,'source size changed')
  values[key]=reader.strict_json(raw);pins[key]={'path':str(path),'bytes':size,'sha256':expected}
 draft=core.build_draft(values['exact_entry_evidence'],values['held_source_proposals'],pins)
 review_path=book_root/'evidence/epub-entry4/Root-field-review-resume38.json'
 raw=pinned(review_path,ROOT_REVIEW_SHA);review=reader.strict_json(raw)
 ledger=adapter.bind(draft,review,{'path':str(review_path),'bytes':len(raw),'sha256':ROOT_REVIEW_SHA})
 stage=core.stage_secondary_view(draft,ledger,core.canonical_sha(ledger))
 saved=read_json(prep/'reviewed001/book-evidence-overlay.staged-no-App-import.json')
 need(stage==saved and stage['unit_fixture'] is False,'saved source staging does not reproduce')
 need(len(stage['approved_secondary_facts'])==27 and len(stage['held_or_rejected'])==1,'source scope differs')
 return stage,read_json(prep/'bibliography-display-profile.proposed.json')


def public_overlay(catalog,stage,bibliography,review_sha):
 need(review_sha==ROOT_REVIEW_SHA and stage.get('unit_fixture') is False,'exact real Root review required')
 need(stage['full_book_read_or_verified'] is False and stage['source_images_for_App_or_training'] is False,
      'source scope must remain secondary-only')
 need(bibliography['source_book_id']==stage['source_book_id'] and bibliography['book_sha256']==stage['source_book_sha256'],
      'book identity mismatch')
 minerals={r['id']:r for r in catalog['minerals']};need(all(minerals[k]['name_en']==v for k,v in SUBJECTS.items()),'catalog subject mismatch')
 rows=[];subjects={}
 for fact in stage['approved_secondary_facts']:
  key,field=fact['catalog_id'],fact['field'];loc=fact['source_locator'];norm=fact['normalized_source_value']
  need(key in SUBJECTS and field in FIELDS and fact['review_status']=='root_source_correspondence_checked',
       'unreviewed or unsupported statement')
  need(fact['primary_Handbook_replacement_allowed'] is fact['automatic_property_conflict_use_allowed'] is False,
       'primary properties cannot be replaced')
  need(loc['source_book_id']==stage['source_book_id'] and loc['book_sha256']==stage['source_book_sha256'],
       'wrong source owner')
  need(loc['navigation_label']==SOURCE_TITLES[key] and loc['printed_page']==SOURCE_PAGES[key],
       'source entry belongs to another mineral')
  need(fact.get('trusted_ledger_canonical_sha256')==ROOT_LEDGER_SHA and
       all(re.fullmatch('[a-f0-9]{64}',fact.get(k,'')) for k in
           ('proposal_field_sha256','source_locator_sha256')), 'missing source field review proof')
  need(not(key=='ima-aragonite' and field=='cleavage'),'ambiguous source cannot be published')
  if field=='hardness':need(norm['kind']=='hardness_scale_unspecified' and norm['unit'] is norm['scale'] is None,'hardness scale changed')
  if field=='relative_density':need(norm['kind']=='relative_density' and norm['unit']=='dimensionless','density conversion forbidden')
  row={'catalog_id':key,'name_en':SUBJECTS[key],'source_id':loc['source_book_id'],'printed_page':loc['printed_page'],
       'field':field,'value':fact['source_text']['verbatim_excerpt'],'status':'reviewed_source_statement',
       'quantity_kind':norm['kind'],'unit':norm.get('unit'),'hardness_scale':None,
       'limits':fact['required_limit_acknowledgements'],'comparison_status':fact['source_comparison_status'],
       'review':{'decision':'approved_source_statement','root_record_sha256':review_sha,
                 'source_book_sha256':stage['source_book_sha256'],'source_evidence_sha256':fact['source_locator_sha256'],
                 'proposal_field_sha256':fact['proposal_field_sha256']}}
  rows.append(row);subject=subjects.setdefault(key,{'catalog_id':key,'name_en':SUBJECTS[key],'printed_page':loc['printed_page'],'approved_fields':[]})
  need(subject['printed_page']==loc['printed_page'],'one exact selected page per subject');subject['approved_fields'].append(field)
 held=stage['held_or_rejected'];need(len(held)==1 and held[0]['catalog_id']=='ima-aragonite' and held[0]['field']=='cleavage' and held[0]['reason']=='source_internal_ambiguity','exact source hold required')
 withheld=[{'catalog_id':'ima-aragonite','name_en':'Aragonite','source_id':stage['source_book_id'],'printed_page':held[0]['printed_page'],
            'field':'cleavage','status':'hold','reason':'source_internal_ambiguity'}]
 need(len(rows)==27 and len({(r['catalog_id'],r['field']) for r in rows})==27,'duplicate or missing source fields')
 book={'source_id':stage['source_book_id'],'title':bibliography['title'],'authors':bibliography['authors'],
       'book_sha256':stage['source_book_sha256'],'root_review_sha256':review_sha,'status':'reviewed_selected_pages',
       'full_book_reviewed':False,'subjects':list(subjects.values())}
 overlay={'schema_version':1,'scope':'secondary_book_source_statements','primary_properties_changed':False,
          'model_scope_changed':False,'books':[book],'records':rows,'withheld':withheld,
          'counts':{'reviewed_source_statements':27,'selected_source_pages':4,'withheld_fields':1,'full_book_reviewed':False}}
 text=encoded(overlay).decode()
 need(not any(s in text for s in ('/Users/','EPUB/','source_page_image','image_member','navigation_src','review_note','无解理，一组不完全至中等解理')),'private/held content leaked')
 return overlay



def validate_overlay(overlay,catalog):
 """Validate public source bindings without opening any book or original image."""
 need(isinstance(overlay,dict) and overlay.get('schema_version')==1 and
      overlay.get('scope')=='secondary_book_source_statements' and
      overlay.get('primary_properties_changed') is overlay.get('model_scope_changed') is False,
      'invalid existing or new secondary book source schema')
 need(all(isinstance(overlay.get(k),list) for k in ('books','records','withheld')),'source collections required')
 minerals={r['id']:r for r in catalog['minerals']};books={};owners={};keys=set()
 ishash=lambda v:isinstance(v,str) and re.fullmatch('[a-f0-9]{64}',v)
 for book in overlay['books']:
  source=book.get('source_id');need(isinstance(source,str) and re.fullmatch('user-book-[0-9]{2,}',source) and source not in books,'duplicate or invalid book identity')
  need(book.get('status')=='reviewed_selected_pages' and book.get('full_book_reviewed') is False and
       ishash(book.get('book_sha256')) and ishash(book.get('root_review_sha256')) and
       isinstance(book.get('title'),str) and 0<len(book['title'])<=200 and
       isinstance(book.get('authors'),list) and 0<len(book['authors'])<=8 and
       all(isinstance(v,str) and 0<len(v)<=80 for v in book['authors']) and isinstance(book.get('subjects'),list),'invalid book source metadata')
  books[source]=book
  for subject in book['subjects']:
   mid=subject.get('catalog_id');page=subject.get('printed_page');fields=subject.get('approved_fields');review=subject.get('root_review_sha256',book['root_review_sha256'])
   need(mid in minerals and subject.get('name_en')==minerals[mid]['name_en'] and
        isinstance(page,str) and re.fullmatch('[0-9]{1,5}',page) and ishash(review) and
        isinstance(fields,list) and len(set(fields))==len(fields) and all(f in FIELDS for f in fields),'invalid source subject')
   for field in fields:
    key=(source,mid,field,page);need(key not in owners,'duplicate subject field ownership');owners[key]=review
 for row in overlay['records']:
  key=tuple(row.get(k) for k in ('source_id','catalog_id','field','printed_page'));source,mid,field,page=key
  need(key not in keys and key in owners,'duplicate or unowned source statement');keys.add(key);book=books[source];review=row.get('review',{})
  need(row.get('name_en')==minerals[mid]['name_en'] and row.get('status')=='reviewed_source_statement' and
       isinstance(row.get('value'),str) and 0<len(row['value'])<=250 and isinstance(row.get('limits'),list) and
       review.get('decision')=='approved_source_statement' and review.get('root_record_sha256')==owners[key] and
       review.get('source_book_sha256')==book['book_sha256'] and all(ishash(review.get(k)) for k in ('source_evidence_sha256','proposal_field_sha256')),'missing or mismatched source review')
  if field=='hardness':need(row.get('quantity_kind')=='hardness_scale_unspecified' and row.get('unit') is row.get('hardness_scale') is None and 'hardness_scale_not_explicit_on_source_page' in row['limits'],'hardness scale changed')
  elif field=='relative_density':need(row.get('quantity_kind')=='relative_density' and row.get('unit')=='dimensionless' and 'relative_density_is_not_measured_density' in row['limits'],'density conversion forbidden')
  else:need(row.get('unit') is None,'source unit changed')
 need(keys==set(owners),'missing source statements')
 heldkeys=set()
 for row in overlay['withheld']:
  key=tuple(row.get(k) for k in ('source_id','catalog_id','field','printed_page'));source,mid,field,page=key
  need(source in books and mid in minerals and row.get('name_en')==minerals[mid]['name_en'] and
       key not in keys and key not in heldkeys and field=='cleavage' and row.get('status')=='hold' and
       row.get('reason')=='source_internal_ambiguity' and 'value' not in row and
       any(s['catalog_id']==mid and s['printed_page']==page for s in books[source]['subjects']),'invalid held marker')
  heldkeys.add(key)
 return books


def merge_overlay(old,incoming,catalog):
 """Append reviewed increments, retaining all old statements and subject objects.
 New subjects bind their own review, while old book-level review remains valid.
 A statement identity is source + catalog mineral + field + printed page.
 """
 newbooks=validate_overlay(incoming,catalog)
 if old is None:return deepcopy(incoming)
 oldbooks=validate_overlay(old,catalog);result=deepcopy(old)
 # An increment may omit old sources: omission never deletes those sources.
 for kind in ('records','withheld'):
  existing={tuple(r[k] for k in ('source_id','catalog_id','field','printed_page')):r for r in old[kind]}
  opposite={tuple(r[k] for k in ('source_id','catalog_id','field','printed_page')) for r in old['withheld' if kind=='records' else 'records']}
  additions=[]
  for row in incoming[kind]:
   key=tuple(row[k] for k in ('source_id','catalog_id','field','printed_page'))
   need(key not in opposite,'old source decision cannot be replaced')
   if key in existing:need(existing[key]==row,'old source statement cannot be changed or removed')
   else:additions.append(deepcopy(row))
  result[kind].extend(sorted(additions,key=lambda r:tuple(r[k] for k in ('source_id','catalog_id','printed_page','field'))))
 resultbooks={b['source_id']:b for b in result['books']}
 oldkeys={tuple(r[k] for k in ('source_id','catalog_id','field','printed_page')) for r in old['records']}
 for source in sorted(newbooks):
  book=newbooks[source]
  if source not in oldbooks:result['books'].append(deepcopy(book));continue
  # Only the subject collection can grow; book identity/credit/source stay exact.
  stable=lambda b:{k:v for k,v in b.items() if k not in ('subjects','root_review_sha256')}
  need(stable(book)==stable(oldbooks[source]),'old book credit or source metadata cannot change')
  added=[]
  for subject in book['subjects']:
   fields=[f for f in subject['approved_fields'] if (source,subject['catalog_id'],f,subject['printed_page']) not in oldkeys]
   # Marker-only increments still need their printed-page subject locator.
   has_old_page=any(s['catalog_id']==subject['catalog_id'] and s['printed_page']==subject['printed_page'] for s in oldbooks[source]['subjects'])
   if not fields and has_old_page:continue
   newsubject=deepcopy(subject);newsubject['approved_fields']=fields
   newsubject['root_review_sha256']=subject.get('root_review_sha256',book['root_review_sha256'])
   added.append(newsubject)
  resultbooks[source]['subjects'].extend(sorted(added,key=lambda s:(s['catalog_id'],s['printed_page'],s['root_review_sha256'],tuple(s['approved_fields']))))
 result['counts']={'reviewed_source_statements':len(result['records']),
                   'selected_source_pages':len({(b['source_id'],s['printed_page']) for b in result['books'] for s in b['subjects']}),
                   'withheld_fields':len(result['withheld']),'full_book_reviewed':False}
 validate_overlay(result,catalog)
 return result


def prepare(catalog,manifest,stage,bibliography,review_sha):
 incoming=public_overlay(catalog,stage,bibliography,review_sha)
 result=deepcopy(catalog);overlay=merge_overlay(catalog.get('reviewed_book_evidence'),incoming,catalog);result['reviewed_book_evidence']=overlay
 need(result['minerals']==catalog['minerals'],'primary mineral objects changed')
 raw=encoded(result);updated=deepcopy(manifest)
 entries=[r for r in updated['files'] if r['path']=='data/catalog.json'];need(len(entries)==1,'one catalog manifest member required')
 entries[0].update(bytes=len(raw),sha256=digest(raw))
 counts=overlay['counts'];updated['counts'].update(reviewed_book_source_statements=counts['reviewed_source_statements'],reviewed_book_source_pages=counts['selected_source_pages'],reviewed_book_withheld_fields=counts['withheld_fields'])
 return raw,(json.dumps(updated,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode(),overlay


def transactional_replace(catalog_path,manifest_path,catalog_raw,manifest_raw,before,replace=os.replace):
 """Stage/flush both files first; rollback both old bytes on replace exceptions.
 Manifest-last makes an interrupted unmatched pair fail reference integrity.
 """
 paths=[catalog_path,manifest_path];new=[catalog_raw,manifest_raw];temps=[];backups=[]
 lock=catalog_path.parent/'.book-evidence-import.lock'
 descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(descriptor)
 try:
  need([p.read_bytes() for p in paths]==before,'catalog/manifest changed during source review')
  for path,newraw,oldraw in zip(paths,new,before):
   for label,raw,population in [('new',newraw,temps),('rollback',oldraw,backups)]:
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.book-'+label+'-',dir=path.parent)
    population.append(Path(name));os.fchmod(fd,path.stat().st_mode & 0o777)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
  need([p.read_bytes() for p in paths]==before,'concurrent catalog/manifest edit')
  try:
   for temp,path in zip(temps,paths):replace(temp,path)
  except BaseException:
   for backup,path in zip(backups,paths):os.replace(backup,path)
   need([p.read_bytes() for p in paths]==before,'rollback could not restore original bytes')
   raise
 finally:
  for path in temps+backups:
   if path.exists():path.unlink()
  lock.unlink()


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',type=Path,required=True)
 parser.add_argument('--book-work-root',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
 parser.add_argument('--apply-to-local-app',action='store_true');args=parser.parse_args()
 repo=args.repo.resolve();book_root=args.book_work_root.resolve();out=args.output_dir.resolve()
 need(not out.exists(),'fresh output directory required')
 cp=repo/'data/catalog.json';mp=repo/'data/reference-manifest.json';before=[cp.read_bytes(),mp.read_bytes()]
 catalog=read_json(cp);manifest=read_json(mp)
 need(catalog.get('count')==len(catalog['minerals'])==6239,'existing6239 mineral catalog required')
 old=[r for r in manifest['files'] if r['path']=='data/catalog.json'];need(len(old)==1 and old[0]['bytes']==len(before[0]) and old[0]['sha256']==digest(before[0]),'existing catalog/manifest mismatch')
 stage,bibliography=verified_stage(book_root);catraw,manraw,overlay=prepare(catalog,manifest,stage,bibliography,ROOT_REVIEW_SHA)
 out.mkdir(parents=True);(out/'catalog.json').write_bytes(catraw);(out/'reference-manifest.json').write_bytes(manraw)
 if args.apply_to_local_app:transactional_replace(cp,mp,catraw,manraw,before)
 report={'local_App_applied':args.apply_to_local_app,'source_pages':overlay['counts']['selected_source_pages'],'reviewed_source_statements':len(overlay['records']),'withheld_fields':len(overlay['withheld']),
         'new_independent_physical_values_claimed':False,'all6239_original_mineral_objects_preserved':catalog['minerals']==json.loads(catraw)['minerals'],
         'source_payloads_reopened':False,'source_images_training_or_App_imported':False,
         'catalog_sha256':digest(catraw),'manifest_sha256':digest(manraw),'Root_review_sha256':ROOT_REVIEW_SHA}
 (out/'book-import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
