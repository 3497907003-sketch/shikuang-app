'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const C=require('../candidate-model.js'),Core=require('../core.js');
const {fixture,result,clone}=require('./helpers/candidate.cjs');
test('candidate binds exact87 scientific order and real catalogue IDs without changing schema1',()=>{
 const f=fixture(),m=C.validateManifest(f.manifest,f.legacy,f.legacyHash);
 assert.equal(m.labels.length,87);assert.equal(m.classifier.fold,0);assert.equal(Object.isFrozen(m.classifier.provenance),true);
 const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/catalog.json'),'utf8')),ids=new Set(catalog.minerals.map(r=>r.id));
 assert.equal(m.catalogMap.every((x,i)=>x.index===i&&x.label===m.labels[i]&&x.catalogId===x.label&&ids.has(x.catalogId)),true);
 assert.throws(()=>Core.validateManifest(f.manifest));assert.equal(Core.MODEL_MAX_BYTES,80000000);
});
test('only candidate hash-addressed artifacts receive128MiB; schema1 still rejects over80MB',()=>{
 const f=fixture();for(const bytes of [80000001,88450004,128*1048576]){const m=clone(f.manifest);m.classifier.bytes=bytes;assert.equal(C.validateManifest(m,f.legacy,f.legacyHash).classifier.bytes,bytes);}
 for(const bytes of [128*1048576+1,0,NaN,1.1]){const m=clone(f.manifest);m.classifier.bytes=bytes;assert.throws(()=>C.validateManifest(m,f.legacy,f.legacyHash));}
 const old=JSON.parse(f.legacyRaw);old.models[0].bytes=80000001;assert.throws(()=>Core.validateManifest(old));
});
test('candidate rejects provenance, profile, labels, catalogue, gate and acceptance drift',()=>{
 const changes=[m=>m.schemaVersion=1,m=>m.productionRegistered=true,m=>m.independentAcceptance=true,m=>m.labels.reverse(),m=>m.catalogMap[0].catalogId='ima-quartz',m=>m.inputProfile.normId='legacy',m=>m.classifier.path='models/efficientnet.onnx',m=>m.classifier.sha256='x'.repeat(64),m=>m.classifier.fold=2,m=>m.classifier.id='other',m=>m.classifier.provenance.officialBaseSha256='0'.repeat(64),m=>m.classifier.provenance.selectedDeltaSha256='',m=>m.classifier.provenance.selectionRule='best_outer_score',m=>m.classifier.provenance.independentKappa=.8,m=>m.gate.inputProfile=C.PROFILE.profileId,m=>m.gate.legacyManifestSha256='0'.repeat(64),m=>m.gate.model.sha256='0'.repeat(64),m=>m.policy.calibrated=true,m=>m.policy.modelSelection='ensemble'];
 const f=fixture();for(const mutate of changes){const m=clone(f.manifest);mutate(m);assert.throws(()=>C.validateManifest(m,f.legacy,f.legacyHash));}
});
test('candidate resource URLs stay in explicit same-app namespaces',()=>{
 const f=fixture(),base='https://app.test/app/index.html';assert.equal(C.manifestURL(f.manifestURL,base).href,f.manifestURL);
 for(const value of ['https://other.test/app/research/candidates/x.json','../research/candidates/x.json','./model-manifest.json','./research/candidates/../secret.json','./research/candidates/x.json#token'])assert.throws(()=>C.manifestURL(value,base));
 const url=C.modelURL(f.manifest.classifier,f.manifestHash,base,f.manifestURL,f.legacyHash);assert.equal(url.searchParams.get('model'),f.manifest.classifier.sha256);assert.throws(()=>C.modelURL({...f.manifest.classifier,path:'models/imagenet_gate.onnx'},f.manifestHash,base,f.manifestURL,f.legacyHash));
});
test('candidate requires separate finite legacy-gate and research tensors',()=>{
 const a=new Float32Array(3*224*224),b=new Float32Array(3*224*224);C.validateInputs([a],[b]);assert.throws(()=>C.validateInputs([a],[a]));a[0]=NaN;assert.throws(()=>C.validateInputs([a],[b]));
 assert.throws(()=>C.validateInputs([new Float32Array(1)],[b]));assert.throws(()=>C.validateInputs([],[]));
 if(typeof SharedArrayBuffer==='function')assert.throws(()=>C.validateInputs([new Float32Array(new SharedArrayBuffer(3*224*224*4))],[b]));
});
test('candidate returns complete per-photo raw diagnostics and catalogue rankings without old thresholds',()=>{
 const f=fixture(),m=C.validateManifest(f.manifest,f.legacy,f.legacyHash),r=result(f,2);C.validateResult(r,m,f.manifestHash,2);const d=C.diagnostics(r,m);
 assert.equal(d.rankings[0].candidates[0].catalogId,C.LABELS[86]);assert.equal(d.status,'diagnostic');assert.equal(d.independentKappa,null);assert.equal(d.confidenceCalibrated,false);assert.equal(d.productionRegistered,false);assert.equal(d.rankings[0].candidates[0].score,undefined);
 for(const mutate of [r=>r.runs.pop(),r=>r.runs[0].values.pop(),r=>r.screening[0].values.pop(),r=>r.modelVersion='old',r=>r.productionRegistered=true,r=>r.runs[0].values[0]=NaN]){const v=clone(r);mutate(v);assert.throws(()=>C.validateResult(v,m,f.manifestHash,2));}
});

test('manifest builder fills fixed scientific mapping and never invents quality or model evidence',()=>{
 const f=fixture(),m=C.createManifest({version:f.manifest.version,classifier:f.manifest.classifier},f.legacy,f.legacyHash);
 assert.deepEqual(JSON.parse(JSON.stringify(m)),f.manifest);assert.equal(m.independentAcceptance,false);assert.equal(m.policy.independentKappa,null);
 const classifier=clone(f.manifest.classifier);delete classifier.provenance;assert.throws(()=>C.createManifest({version:'candidate',classifier},f.legacy,f.legacyHash));
});
