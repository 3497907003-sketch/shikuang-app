'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),crypto=require('node:crypto'),vm=require('node:vm'),fs=require('node:fs');
const C=require('../candidate-model.js'),API=require('../candidate-inference.js'),Core=require('../core.js'),{fixture,result}=require('./helpers/candidate.cjs'),{response}=require('./helpers/model-contract.cjs');
function photo(){return {encodedPhoto:new Blob(['synthetic encoded fixture']),route:'photo-file',normalizedROI:{x0:0,y0:0,x1:1,y1:1},gateCropPercent:1,limits:{inputMemoryBudgetBytes:8*1048576,maxNativePixels:40000000}};}
function harness(config={}){
 const f=fixture(),workers=[],stages=[],requests=[],timers=new Set();
 const set=(fn,ms)=>{const t=setTimeout(()=>{timers.delete(t);fn();},ms);timers.add(t);return t;},clear=t=>{clearTimeout(t);timers.delete(t);};
 class Worker{
  constructor(url){this.url=url;this.terminated=0;workers.push(this);queueMicrotask(()=>this.onmessage?.({data:{type:'ready',purpose:C.PURPOSE}}));}
  postMessage(request,transfer){requests.push({request,transfer});if(config.noResult)return;queueMicrotask(()=>this.onmessage?.({data:result(f,request.inputs.length)}));}
  terminate(){this.terminated++;}
 }
 const host={base:'https://app.test/app/',Worker,crypto:crypto.webcrypto,blocked:Array(1000).fill(false),setTimeout:set,clearTimeout:clear,resourceURL:name=>'https://app.test/app/'+name,
  prepareLegacy:async()=>f.legacy,legacyHash:()=>f.legacyHash,fetch:async()=>response(f.manifestRaw),readResource:Core.readResource,
  validateFrame:request=>({request}),decodePhoto:async options=>{stages.push('native-decode');if(config.decode)return config.decode(options);return {width:3,height:3,rgba:new Uint8ClampedArray(36).fill(255),route:options.route};},
  prepareLegacyGate:()=>{stages.push('legacy-gate');return new Float32Array(3*224*224).fill(42);},
  prepareInput:async options=>{stages.push('research-Q16');return {profileId:C.PROFILE.profileId,normId:C.PROFILE.normId,contractId:C.PROFILE.inputContract,productionRegistration:false,nativeROI:{x0:0,y0:0,x1:3,y1:3},runtimeTensor:new Float32Array(3*224*224).fill(7)};}};
 const client=API.createClient(host),options={diagnostic:true,manifestURL:f.manifestURL,manifestSha256:f.manifestHash};
 return {f,client,options,host,workers,stages,requests,timers};
}
test('candidate prepare is SHA-bound metadata only and cannot become production configuration',async()=>{
 const h=harness(),p=await h.client.prepare(h.options);assert.equal(p.manifest.labels.length,87);assert.equal(p.productionRegistered,false);assert.equal(h.workers.length,0);assert.equal(h.stages.length,0);assert.equal(h.timers.size,0);
 assert.throws(()=>h.client.prepare({}),/diagnostic/);await assert.rejects(h.client.prepare({...h.options,manifestSha256:'0'.repeat(64)}),/SHA/);
});
test('candidate analyze prepares legacy gate before research ownership transfer and returns diagnostic IDs',async()=>{
 const h=harness(),prepared=await h.client.prepare(h.options),r=await h.client.analyze([photo()],{diagnostic:true,prepared});
 assert.deepEqual(h.stages,['native-decode','legacy-gate','research-Q16']);assert.equal(r.rankings[0].candidates[0].catalogId,C.LABELS[86]);assert.equal(r.status,'diagnostic');assert.equal(r.independentKappa,null);assert.equal(h.workers[0].terminated,1);assert.equal(h.timers.size,0);
 const {request,transfer}=h.requests[0];assert.equal(request.inputs[0][0],7);assert.equal(request.gateInputs[0][0],42);assert.notEqual(transfer[0],transfer[1]);assert.equal(request.gateProfileId,C.GATE_PROFILE);
});
test('candidate rejects preview, ambiguous source, unbound config and missing explicit crop',async()=>{
 const h=harness();for(const patch of [{src:'preview1536'},{frame:{}},{gateCropPercent:undefined},{crop:1}])assert.throws(()=>h.client.analyze([{...photo(),...patch}],h.options));
 await assert.rejects(h.client.analyze([photo()],{diagnostic:true,prepared:{}}),/客户端校验/);assert.equal(h.workers.length,0);
});
test('candidate timeout and cancellation stop worker and permit a fresh retry',async()=>{
 const h=harness({noResult:true}),prepared=await h.client.prepare(h.options);
 await assert.rejects(h.client.analyze([photo()],{diagnostic:true,prepared,timeoutMs:25}),/整体上限/);assert.equal(h.workers[0].terminated,1);assert.equal(h.timers.size,0);
 const controller=new AbortController(),pending=h.client.analyze([photo()],{diagnostic:true,prepared,signal:controller.signal});while(h.workers.length<2)await new Promise(r=>setImmediate(r));controller.abort();await assert.rejects(pending,{name:'AbortError'});assert.equal(h.workers[1].terminated,1);assert.equal(h.timers.size,0);
});
test('public candidate API shares production/research active gate and never changes schema1 manifest on its own',async()=>{
 let release;const waiting=new Promise(r=>release=r),candidate={prepare:()=>waiting,analyze:()=>waiting};
 const window={setTimeout,clearTimeout,crypto:crypto.webcrypto,IMAGENET_BLOCKED:Array(1000).fill(false),ShikuangResearchInput:{createClient:()=>({})},ShikuangResearchPhoto:{createClient:()=>({})},ShikuangCandidateInference:{createClient:()=>candidate}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../inference.js'),'utf8'),{window,MineralCore:Core,location:{href:'https://app.test/app/'},setTimeout,clearTimeout,DOMException,AbortController,crypto:crypto.webcrypto});
 const engine=window.MineralEngine,pending=engine.prepareCandidate({diagnostic:true});await assert.rejects(engine.analyze([{src:'not-decoded'}]),/已有分析/);await assert.rejects(engine.prepareResearchInput({}),/已有分析/);await assert.rejects(engine.analyzeCandidate([],{}),/已有分析/);assert.equal(engine.configuration,null);release({purpose:C.PURPOSE});await pending;assert.equal(engine.configuration,null);assert.equal(engine.manifestCacheState,'unprepared');
});

test('public native-frame route uses actual legacy normalization separately from frozen Q16 preprocessing',async()=>{
 const f=fixture(),Input=require('../research-input.js'),Profile=require('../research/shikuang-research-native-roi-q16-torchf32-v1/profile.js');
 const LUT=fs.readFileSync(require.resolve('../research/shikuang-research-native-roi-q16-torchf32-v1/frozen/vendor/normalization-lut.f32le.bin'));
 const rgba=new Uint8ClampedArray(36);for(let i=0;i<9;i++)rgba.set([6,0,32,255],i*4);let dispatched;
 const canvases=[],document={createElement(){const canvas={width:0,height:0,getContext(){return {createImageData(w,h){return {data:new Uint8ClampedArray(w*h*4)};},putImageData(p){canvas.pixels=p.data;},drawImage(source){canvas.pixels=new Uint8ClampedArray(224*224*4);for(let i=0;i<224*224;i++)canvas.pixels.set(source.pixels.subarray(0,4),i*4);},getImageData(){return {data:canvas.pixels};}};}};canvases.push(canvas);return canvas;}};
 class Worker{constructor(){queueMicrotask(()=>this.onmessage?.({data:{type:'ready',purpose:C.PURPOSE}}));}postMessage(data){dispatched=data;queueMicrotask(()=>this.onmessage?.({data:result(f)}));}terminate(){}}
 const inputClient={prepare(o){const p=Profile.preprocess({...o,geometryLUTBytes:LUT});return Promise.resolve({...p,runtimeTensor:Profile.toRuntimeTensor(C.PROFILE.profileId,p.tensorFloat32LE)});}};
 const classes=Object.fromEntries(f.legacy.labels.map(k=>[k,{}]));
 const window={setTimeout,clearTimeout,crypto:crypto.webcrypto,Worker,IMAGENET_BLOCKED:Array(1000).fill(false),MINERAL_CLASSES:classes,ShikuangCandidateInference:API,ShikuangResearchInput:{validateRequest:Input.validateRequest,createClient:()=>inputClient},ShikuangResearchPhoto:{createClient:()=>({decodePhoto(){throw Error('native frame must not be decoded again');}})}};
 const context={URL,TextDecoder,window,document,MineralCore:Core,MINERAL_CLASSES:classes,location:{href:'https://app.test/app/'},setTimeout,clearTimeout,DOMException,AbortController,crypto:crypto.webcrypto,fetch:async url=>response(new URL(url).pathname.endsWith('/model-manifest.json')?f.legacyRaw:f.manifestRaw)};
 vm.runInNewContext(fs.readFileSync(require.resolve('../inference.js'),'utf8'),context);
 const prepared=await window.MineralEngine.prepareCandidate({diagnostic:true,manifestURL:f.manifestURL,manifestSha256:f.manifestHash});
 const native={width:3,height:3,rgba,colorSpace:'srgb',orientationApplied:true,stage:'native-oriented-srgb-no-scale',priorResizeCount:0,jpegRoundTripsCreated:0,route:'video-file-frame',decoderEvidence:'synthetic already-presented frame',sourceHeader:{kind:'decoder-frame',width:3,height:3,frameOrientationApplied:true,orientationEvidence:'synthetic presented-frame orientation'}};
 const r=await window.MineralEngine.analyzeCandidate([{frame:native,gateCropPercent:1,normalizedROI:{x0:0,y0:0,x1:1,y1:1},limits:{inputMemoryBudgetBytes:8*1048576,maxNativePixels:40000000}}],{diagnostic:true,prepared});
 const legacyPixels=new Uint8ClampedArray(224*224*4);for(let i=0;i<224*224;i++)legacyPixels.set([6,0,32,255],i*4);
 assert.deepEqual(dispatched.gateInputs[0],Core.pixelsToInput(legacyPixels,f.legacy.input));
 const strict=Profile.preprocess({profileId:C.PROFILE.profileId,frame:native,normalizedROI:{x0:0,y0:0,x1:1,y1:1},geometryLUTBytes:LUT,limits:{inputMemoryBudgetBytes:8*1048576,maxNativePixels:40000000}});
 assert.deepEqual(dispatched.inputs[0],Profile.toRuntimeTensor(C.PROFILE.profileId,strict.tensorFloat32LE));assert.notDeepEqual(dispatched.inputs[0],dispatched.gateInputs[0]);
 assert.equal(r.inputEvidence[0].route,'video-file-frame');assert.equal(canvases.every(c=>c.width===0&&c.height===0),true);assert.equal(window.MineralEngine.configuration.version,f.legacy.version);
});

test('production entry rejects candidate diagnostics before any resource access',async()=>{
 let fetches=0;const window={},context={window,MineralCore:Core,location:{href:'https://app.test/app/'},setTimeout,clearTimeout,DOMException,AbortController,fetch(){fetches++;throw Error('forbidden');}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../inference.js'),'utf8'),context);
 for(const extra of [{diagnostic:true},{candidateManifest:{}},{candidateProfile:C.PROFILE.profileId}])await assert.rejects(window.MineralEngine.analyze([{src:'preview'}],extra),/研究profile/);
 assert.equal(fetches,0);
});
