"""Finite public semantics for the exact Root-reviewed book42 increment."""
import hashlib,json,re
from copy import deepcopy
REVIEW_SHA='ac37968d5d88c49cef73182cd5cf5426991922540fce73d7c4f190ae5cb3fe56'
SOURCES={'new-book-04': '2a85c6aa9b07c88f114c393bfcb5f61d14062da9052194f1ed6cac6ad6c0366b', 'new-book-07': '5d4d810a96f8905e0ddb3603424627b3e74b6fce00e5872e7c051a337cc1740d'}
PAGES={'new-book-04': {'49': {'printed_page': '48', 'render_sha256': 'cbe182b5a52132f3c36eb0f8849c30e5b74bbb89aa67e2c1bce912b8935fd2dc'}, '50': {'printed_page': '49', 'render_sha256': '8973e582bf1075025efc09d93f4bcde4c2c6cce9d4148871f28851fb63056f2e'}}, 'new-book-07': {'64': {'printed_page': '62', 'render_sha256': '2f3f746252c8a760931539cd992121141badad37b3b6c1ae6a4acfb9ce421b19'}, '65': {'printed_page': '63', 'render_sha256': 'e454abddb3c637730c34f32a824affd39e6425623a8ca7a3c4b2814501affa6a'}, '92': {'printed_page': '90', 'render_sha256': '0cd03493e81119c12eb2417732fd13c5e22bbd890eed4ca2ed2d99d1dd2618f5'}, '93': {'printed_page': '91', 'render_sha256': '74f4497bc9abb7faf04f188f4aae2903f015aeae17413ba3457e02897afcbde4'}}}
FIELD_KINDS={'aggregate_and_occurrence_example': ['literal_source_statement'], 'aggregate_habit': ['literal_source_statement'], 'cleavage': ['literal_source_statement'], 'color': ['literal_source_statement'], 'crystal_habit': ['literal_source_statement'], 'crystal_system': ['crystal_system_terminology'], 'density_comparison': ['qualitative_mass_density_comparison'], 'form_and_use_description': ['literal_source_statement'], 'form_description': ['literal_source_statement'], 'formation': ['literal_source_statement', 'qualitative_formation_condition'], 'fracture': ['literal_source_statement'], 'hardness': ['Mohs_hardness_range', 'Mohs_hardness_reference_value', 'Mohs_scale_reference_standard'], 'hardness_comparison': ['qualitative_hardness_comparison'], 'luster': ['literal_source_statement'], 'optical_effect': ['literal_source_statement'], 'processed_material_use': ['literal_source_statement'], 'processing': ['literal_source_statement'], 'streak': ['literal_source_statement'], 'structure_description': ['atomic_layer_structure_source_model', 'atomic_neighbor_count_in_source_model'], 'surface_finish_example': ['literal_source_statement'], 'twin_example': ['literal_source_statement'], 'uses': ['literal_source_statement']}
EXTRA_FIELDS=set(FIELD_KINDS)-{'formula','hardness','relative_density','density','crystal_system','cleavage','luster','streak','uses','occurrence','habit'}
MOHS_KINDS={'Mohs_hardness_reference_value','Mohs_hardness_range','Mohs_scale_reference_standard'}
REQUIRED_LIMITS={'selected_page_secondary_book_statement_only','no_full_book_review_claim','no_current_specimen_measurement_or_truth_claim','no_primary_property_replacement','no_model_score_or_training_use'}
def need(ok,message):
 if not ok:raise ValueError(message)
def canonical_sha(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
BIBLIOGRAPHY_REVIEW_SHA='5b82c863a8c5f70acb2ff264b157c4bb71141d660ee644975ea75cdb3e03842d'
BIBLIOGRAPHY_REVIEW_BYTES=4132
BIBLIOGRAPHY={
 'new-book-04':{'title':'Eyewitness Rocks & Minerals','authors':['Dr R. F. Symes','伦敦自然历史博物馆工作人员'],'credit_role':'author','publisher':'DK Publishing','edition':'美国修订版，2008','isbn':'978-0-7566-3777-4','bibliographic_pdf_pages':[4,5],'bibliography_note':'仅核对所列资料页，未通读全书。'},
 'new-book-07':{'title':'The Rock & Gem Book: And Other Treasures of the Natural World','authors':[],'author_credit_status':'not_stated_on_reviewed_bibliographic_pages','publisher':'DK Publishing','edition':'美国第一版，2016','isbn':'978-1-4654-5070-8','bibliographic_pdf_pages':[1,6],'bibliography_note':'仅核对所列资料页，未通读全书。'}}
def public_bibliography(source):
 need(source in BIBLIOGRAPHY,'exact reviewed bibliography source required')
 result=deepcopy(BIBLIOGRAPHY[source])
 result['bibliography_review']={'decision':'Root_approved_bibliographic_pages','root_record_sha256':BIBLIOGRAPHY_REVIEW_SHA,'root_record_bytes':BIBLIOGRAPHY_REVIEW_BYTES,'source_book_sha256':SOURCES[source]}
 return result
def valid_bibliography(book):
 source=book.get('source_id')
 if source not in BIBLIOGRAPHY or book.get('book_sha256')!=SOURCES[source]:return False
 if source=='new-book-07' and 'credit_role' in book:return False
 expected=public_bibliography(source)
 try:return canonical_sha({key:book.get(key) for key in expected})==canonical_sha(expected)
 except (TypeError,ValueError):return False
def owns(row):return row.get('source_id') in SOURCES and row.get('review',{}).get('root_record_sha256')==REVIEW_SHA

def validate_row(row):
 need(owns(row) and row['review']['source_book_sha256']==SOURCES[row['source_id']] and re.fullmatch(r'book42-(00[1-9]|0[1-3][0-9]|040)',row['review'].get('approved_candidate_id','')),'exact book42 source and Root record required')
 need(row['field'] in FIELD_KINDS and row['quantity_kind'] in FIELD_KINDS[row['field']] and REQUIRED_LIMITS<=set(row['limits']),'finite approved book42 field semantics')
 need(isinstance(row.get('conditions'),list) and all(isinstance(v,str) and len(v)<=200 for v in row['conditions']),'source conditions required')
 if row['field']=='hardness':need(row['quantity_kind'] in MOHS_KINDS and row['unit']==row['hardness_scale']=='Mohs' and 'ordinal_scale_not_a_ratio_scale' in row['limits'],'explicit ordinal Mohs must retain its scale, never ratio or unknown')
 else:
  expected='neighbor_atoms' if row['quantity_kind']=='atomic_neighbor_count_in_source_model' else None
  need(row['unit']==expected and row['hardness_scale'] is None,'qualitative/source-model unit cannot become primary quantitative property')
 pages=row.get('source_pages');need(isinstance(pages,list) and 1<=len(pages)<=2 and all(isinstance(p,dict) and 'pdf_page_1based' in p for p in pages) and len({p['pdf_page_1based'] for p in pages})==len(pages),'exact nonduplicate public page locators required')
 for page in pages:
  need(set(page)=={'pdf_page_1based','printed_page','render_sha256'} and PAGES[row['source_id']].get(str(page['pdf_page_1based']))=={k:page[k] for k in ('printed_page','render_sha256')},'exact approved six-page locator/render binding')
 need(pages[0]['pdf_page_1based']==row['pdf_page_1based'] and pages[0]['printed_page']==row['printed_page'] and row['review']['source_evidence_sha256']==canonical_sha(pages),'all contributing pages bound to source evidence')
