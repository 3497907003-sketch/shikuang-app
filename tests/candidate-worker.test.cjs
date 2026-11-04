'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
const C=require('../candidate-model.js'),Core=require('../core.js'),{fixture}=require('./helpers/candidate.cjs'),{response}=require('./helpers/model-contract.cjs');
function harness(options={}){
 const f=fixture(),messages=[],calls=[],sessions=[],fetches=[];let gateReleased=false;
 class Tensor{constructor(type,data,dims){this.type=type;this.data=data;this.dims=dims;}dispose(){}}
 const context={onmessage:null,URL,TextDecoder,Float32Array,ArrayBuffer,DOMException,crypto:crypto.webcrypto,self:{location:{origin:'https://app.test'}},MineralCore:Core,ShikuangCandidateModel:C,importScripts(){},postMessage:m=>messages.push(m),ort:{env:{wasm:{}},Tensor,InferenceSession:{create:async bytes=>{
  const gate=bytes[0]===1;if(!gate)assert.equal(gateReleased,true,'gate release must finish before candidate allocation');
  const name=gate?f.manifest.gate.model.outputName:'logits',classes=gate?1000:87;
  const s={inputNames:['input'],outputNames:[name],inputMetadata:[{isTensor:true,type:'float32',shape:[1,3,224,224]}],outputMetadata:[{isTensor:true,type:'float32',shape:[1,classes]}],
   async run(inputs){const values=inputs.input.data;calls.push({gate,sentinel:values[0]});assert.equal(values[0],gate?42:7,'gate and candidate preprocessing must remain separate');const data=gate?Float32Array.from({length:1000},(_,i)=>i===(options.nonMineral?5:500)?20:0):Float32Array.from({length:options.wrongOutput?86:87},(_,i)=>i);return {[name]:new Tensor('float32',data,[1,data.length])};},
   async release(){if(gate){if(options.failGateRelease)throw Error('release failed');if(options.gateRelease)await options.gateRelease();gateReleased=true;}s.released=true;}};sessions.push(s);return s;
 }}},fetch:async url=>{
  const u=new URL(url);fetches.push(u.href);if(u.pathname.endsWith('/model-manifest.json'))return response(f.legacyRaw);
  if(u.pathname.endsWith('/research/candidates/synthetic-fold0.json'))return response(f.manifestRaw);
  const key=u.pathname.replace('/app/','');const bytes=f.files[key];if(!bytes)return response([],404);return response(options.corruptClassifier&&key.startsWith('models/candidates/')?Buffer.from([3]):bytes);
 }};
 vm.runInNewContext(fs.readFileSync(require.resolve('../candidate-worker.js'),'utf8'),context);
 const data={type:'analyze-candidate',diagnostic:true,base:'https://app.test/app/',manifestURL:f.manifestURL,manifestSha256:f.manifestHash,legacyManifestSha256:f.legacyHash,profileId:C.PROFILE.profileId,profileVersion:1,gateProfileId:C.GATE_PROFILE,inputs:[new Float32Array(3*224*224).fill(7)],gateInputs:[new Float32Array(3*224*224).fill(42)],blocked:Array(1000).fill(false)};
 return {f,messages,calls,sessions,fetches,data,dispatch:d=>context.onmessage({data:d||data})};
}
test('candidate worker verifies both manifests and runs distinct gate/classifier tensors in sequence',async()=>{
 const h=harness();await h.dispatch();const r=h.messages.at(-1);assert.equal(r.type,'result');assert.equal(r.productionRegistered,false);assert.equal(r.runs[0].values.length,87);assert.deepEqual(h.calls,[{gate:true,sentinel:42},{gate:false,sentinel:7}]);assert.equal(h.sessions.every(s=>s.released),true);
 assert.equal(h.fetches.filter(u=>u.includes('/models/candidates/')).length,1);
});
test('candidate worker never allocates candidate before gate release settles',async()=>{
 let release,entered;const blocked=new Promise(r=>release=r),started=new Promise(r=>entered=r);const h=harness({gateRelease:()=>{entered();return blocked;}}),pending=h.dispatch();await started;assert.equal(h.sessions.length,1);assert.equal(h.calls.length,1);release();await pending;assert.equal(h.messages.at(-1).type,'result');
});
test('gate rejection retains exact non-mineral message and never loads a candidate',async()=>{
 const h=harness({nonMineral:true});await h.dispatch();assert.equal(h.messages.at(-1).message,Core.NON_MINERAL);assert.equal(h.sessions.length,1);assert.equal(h.fetches.some(u=>u.includes('/models/candidates/')),false);
});
test('bad candidate SHA or output does not become a result, and resources release',async()=>{
 for(const options of [{corruptClassifier:true},{wrongOutput:true},{failGateRelease:true}]){const h=harness(options);await h.dispatch();assert.equal(h.messages.at(-1).type,'error');assert.equal(h.messages.some(m=>m.type==='result'),false);}
});
test('missing diagnostic intent, research gate profile, and shared tensors fail before model loads',async()=>{
 for(const mutate of [d=>d.diagnostic=false,d=>d.gateProfileId=C.PROFILE.profileId,d=>d.gateInputs=d.inputs]){const h=harness();mutate(h.data);await h.dispatch();assert.equal(h.messages.at(-1).type,'error');assert.equal(h.sessions.length,0);}
});

test('production worker rejects candidate markers before any resource read',async()=>{
 const messages=[],context={onmessage:null,postMessage:m=>messages.push(m),importScripts(){},URL,Map,Set,MineralCore:Core,self:{location:{origin:'https://app.test'}},fetch(){throw Error('production fetch forbidden');}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../engine-worker.js'),'utf8'),context);
 await context.onmessage({data:{type:'analyze',diagnostic:true}});assert.equal(messages.at(-1).type,'error');assert.match(messages.at(-1).message,/研究profile/);
});

test('candidate gate rejection preserves source-bound raw1000 diagnostic before error and no classifier',async()=>{
 const h=harness({nonMineral:true});await h.dispatch();const event=h.messages.find(m=>m.type==='candidate-screening-diagnostic');
 assert.ok(event);assert.equal(event.purpose,C.PURPOSE);assert.equal(event.photo,0);assert.equal(event.legacyManifestSha256,h.f.legacyHash);assert.equal(event.gateModelId,h.f.manifest.gate.model.id);assert.equal(event.gateModelSha256,h.f.manifest.gate.model.sha256);assert.equal(event.values.length,1000);assert.equal(event.values.every(Number.isFinite),true);
 assert.equal(h.messages.at(-1).message,Core.NON_MINERAL);assert.equal(h.sessions.length,1);assert.equal(h.fetches.some(u=>u.includes('/models/candidates/')),false);
 assert.ok(h.messages.indexOf(event)<h.messages.length-1);
});
