'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const API=require('../research-input.js'),Core=require('../core.js');
const contract=require('../tools/research-input-contract.cjs'),root=path.resolve(__dirname,'..');
const Profile=require('../'+contract.PREFIX+'profile.js');
const LUT=fs.readFileSync(path.join(root,contract.PREFIX,'frozen/vendor/normalization-lut.f32le.bin'));
const {fixture,labels}=require('./helpers/model-contract.cjs');
function options(){const w=8,h=6,rgba=new Uint8Array(w*h*4);for(let i=0;i<w*h;i++)rgba.set([i*3%256,i*7%256,i*11%256,255],i*4);return {profileId:API.PROFILE_ID,profileVersion:1,transferOwnership:true,frame:{width:w,height:h,rgba,colorSpace:'srgb',orientationApplied:true,stage:'native-oriented-srgb-no-scale',priorResizeCount:0,jpegRoundTripsCreated:0,route:'photo-file',decoderEvidence:'generated synthetic pixels; no encoded photo was decoded',sourceHeader:{kind:'file-photo',width:w,height:h,exifOrientation:1,orientationEvidence:'synthetic identity fixture',headerCheckedBeforeDecode:true,encodedBytes:0}},normalizedROI:{x0:0,y0:0,x1:1,y1:1},limits:{inputMemoryBudgetBytes:8*1048576,maxNativePixels:40000000}};}
function output(request){const result=Profile.preprocess({...request,geometryLUTBytes:LUT});return {...result,runtimeTensor:Profile.toRuntimeTensor(API.PROFILE_ID,result.tensorFloat32LE)};}
function client(behavior={}){
  const instances=[],timers=new Map();let serial=0;
  class Worker{
    constructor(url){this.url=url;instances.push(this);behavior.construct?.(this);if(behavior.autoReady!==false)queueMicrotask(()=>this.onmessage?.({data:{type:'ready',profileId:API.PROFILE_ID,profileVersion:1}}));}
    postMessage(request,transfer){this.request=structuredClone(request,{transfer});this.transfer=transfer;behavior.post?.(this);if(behavior.autoResult!==false)queueMicrotask(()=>this.onmessage?.({data:{type:'result',result:output(this.request)}}));}
    terminate(){this.terminated=(this.terminated||0)+1;}
  }
  const host={Worker,resourceURL:name=>Core.shellResourceURL(name,'https://app.test/app/'),setTimeout:(fn,ms)=>{const id=++serial;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id)};
  return {api:API.createClient(host),host,instances,timers};
}
test('research assets are exact reviewed code/LUT copies and shell URL closure includes every asset',()=>{
  assert.deepEqual(contract.validate(root),contract.ASSETS);
  const urls=Core.workerAssets('https://app.test/app/').map(url=>new URL(url).pathname.slice('/app/'.length));
  for(const file of contract.ASSETS)assert.ok(urls.includes(file),file);
  assert.ok(contract.ASSETS.every(file=>!file.includes('models/')&&!file.endsWith('.onnx')));
});
test('explicit version, native declarations, ROI, memory and exclusive ownership reject before a Worker starts',async()=>{
  const h=client();
  for(const patch of [{profileId:undefined},{profileId:'legacy'},{profileVersion:2},{transferOwnership:false},{src:undefined},{cropPercent:1},{modelPath:'models/example.onnx'},{researchManifest:{}},{limits:{inputMemoryBudgetBytes:2097152,maxNativePixels:40e6}},{normalizedROI:{x0:-.1,y0:0,x1:1,y1:1}},{timeoutMs:120001}])await assert.rejects(Promise.resolve().then(()=>h.api.prepare({...options(),...patch})));
  for(const patch of [{priorResizeCount:1},{stage:'preview-1536'},{jpegRoundTripsCreated:1},{orientationApplied:false},{colorSpace:'display-p3'},{width:7},{decoderEvidence:''}]){const o=options();Object.assign(o.frame,patch);assert.throws(()=>h.api.prepare(o));}
  for(const patch of [{headerCheckedBeforeDecode:false},{exifOrientation:null},{width:16}]){const o=options();Object.assign(o.frame.sourceHeader,patch);assert.throws(()=>h.api.prepare(o));}
  const oversized=options();oversized.frame.rgba=new Uint8Array(new ArrayBuffer(oversized.frame.rgba.length+1),1);assert.throws(()=>h.api.prepare(oversized),/独占/);
  if(typeof SharedArrayBuffer==='function'){const shared=options();shared.frame.rgba=new Uint8Array(new SharedArrayBuffer(shared.frame.rgba.length));assert.throws(()=>h.api.prepare(shared),/非共享/);}
  assert.equal(h.instances.length,0);
});
test('dedicated Worker transfers native pixels once, snapshots metadata and returns exact frozen tensors',async()=>{
  const h=client({autoReady:false}),o=options(),original=Uint8Array.from(o.frame.rgba),expected=output(o),pending=h.api.prepare(o);
  const w=h.instances[0];o.frame.sourceHeader.width=999;o.frame.decoderEvidence='mutated';o.normalizedROI.x1=.5;o.limits.maxNativePixels=9;
  w.onmessage({data:{type:'ready',profileId:API.PROFILE_ID,profileVersion:1}});const result=await pending;
  assert.match(w.url,new RegExp('/'+API.RESOURCE_PATH+'\\?v='));assert.equal(o.frame.rgba.byteLength,0);assert.equal(w.transfer.length,1);assert.deepEqual(w.request.frame.rgba,original);assert.equal(w.request.frame.sourceHeader.width,8);assert.notEqual(w.request.frame.decoderEvidence,'mutated');assert.equal(w.request.normalizedROI.x1,1);
  assert.deepEqual(result.runtimeTensor,expected.runtimeTensor);assert.deepEqual(result.rgb224,expected.rgb224);assert.equal(w.terminated,1);assert.equal(h.timers.size,0);
});
test('encoded header format, ICC presence and parser evidence survive the Worker snapshot',async()=>{
  const h=client({autoReady:false}),o=options();Object.assign(o.frame.sourceHeader,{format:'jpeg',profilePresent:true,headerEvidence:'shikuang-encoded-native-header-seek002'});const p=h.api.prepare(o);o.frame.sourceHeader.profilePresent=false;o.frame.sourceHeader.headerEvidence='mutated';
  h.instances[0].onmessage({data:{type:'ready',profileId:API.PROFILE_ID,profileVersion:1}});const r=await p;assert.equal(r.sourceHeader.format,'jpeg');assert.equal(r.sourceHeader.profilePresent,true);assert.equal(r.sourceHeader.headerEvidence,'shikuang-encoded-native-header-seek002');
  for(const patch of [{format:'avif'},{profilePresent:1},{headerEvidence:''}]){const bad=options();Object.assign(bad.frame.sourceHeader,patch);assert.throws(()=>API.validateRequest(bad),/证据无效/);}
});
test('cancel before dispatch keeps source; cancel during work terminates and retry has independent callbacks',async()=>{
  const h=client({autoReady:false,autoResult:false}),pre=new AbortController();pre.abort();assert.throws(()=>h.api.prepare({...options(),signal:pre.signal}),{name:'AbortError'});assert.equal(h.instances.length,0);
  const c=new AbortController(),o=options(),pending=h.api.prepare({...o,signal:c.signal}),first=h.instances[0];c.abort();await assert.rejects(pending,{name:'AbortError'});assert.equal(o.frame.rgba.byteLength,8*6*4);assert.equal(first.terminated,1);
  const secondController=new AbortController(),second=h.api.prepare({...options(),signal:secondController.signal}),worker=h.instances[1];worker.onmessage({data:{type:'ready',profileId:API.PROFILE_ID,profileVersion:1}});secondController.abort();await assert.rejects(second,{name:'AbortError'});assert.equal(worker.terminated,1);assert.equal(h.timers.size,0);
  const retry=h.api.prepare(options()),last=h.instances[2];last.onmessage({data:{type:'ready',profileId:API.PROFILE_ID,profileVersion:1}});last.onmessage({data:{type:'result',result:output(last.request)}});assert.equal((await retry).modelForwards,0);
});
test('bootstrap identity, errors and total timeout fail closed with Worker cleanup',async()=>{
  for(const message of [{type:'ready',profileId:'legacy',profileVersion:1},{type:'boot-error',message:'missing frozen module'},{type:'result',result:{}},{type:'error',message:'bad contract'}]){const h=client({autoReady:false}),p=h.api.prepare(options()),w=h.instances[0];w.onmessage({data:message});await assert.rejects(p);assert.equal(w.terminated,1);assert.equal(h.timers.size,0);}
  const h=client({autoReady:false}),p=h.api.prepare({...options(),timeoutMs:25}),w=h.instances[0];[...h.timers.values()].find(timer=>timer.ms===25).fn();await assert.rejects(p,/整体上限/);assert.equal(w.terminated,1);assert.equal(h.timers.size,0);
  const c=new AbortController(),race=client({construct(){c.abort();}});await assert.rejects(race.api.prepare({...options(),signal:c.signal}),{name:'AbortError'});assert.equal(race.instances[0].terminated,1);assert.equal(race.timers.size,0);
});
test('invalid Worker result cannot be accepted as a research input',()=>{
  const good=output(options());API.validateResult(good);
  for(const patch of [{profileId:'legacy'},{normId:'legacy'},{modelForwards:1},{modelRegistered:true},{productionRegistration:true},{runtimeTensor:new Float32Array(1)}])assert.throws(()=>API.validateResult({...good,...patch}));
  const bad=new Float32Array(good.runtimeTensor);bad[3]=Infinity;assert.throws(()=>API.validateResult({...good,runtimeTensor:bad}));
});
test('production schema1 still rejects research contracts and resource paths',()=>{
  Core.validateManifest(fixture().manifest,labels);
  for(const mutate of [m=>m.schemaVersion=2,m=>m.input.crop='native ROI',m=>m.input.profileId=API.PROFILE_ID,m=>m.profileId=API.PROFILE_ID,m=>m.models[0].path=contract.PREFIX+'model.onnx']){const m=fixture().manifest;mutate(m);assert.throws(()=>Core.validateManifest(m,labels));}
});
test('public engine shares its active/cancel gate and never routes a research selection into production',async()=>{
  const h=client({autoReady:false,autoResult:false}),window={Worker:h.host.Worker,ShikuangResearchInput:{createClient:()=>h.api}},context={window,MineralCore:Core,location:{href:'https://app.test/app/'},setTimeout,clearTimeout,DOMException,AbortController,MINERAL_CLASSES:{},fetch(){throw Error('production fetch prohibited');}};
  vm.runInNewContext(fs.readFileSync(path.join(root,'inference.js'),'utf8'),context);
  const engine=window.MineralEngine;
  for(const key of ['profileId','profileVersion','inputProfile','researchProfile','researchManifest']){await assert.rejects(engine.prepare({[key]:undefined}),/schema1/);await assert.rejects(engine.analyze([{src:'not-decoded'}],{[key]:undefined}),/schema1/);}
  const controller=new AbortController(),p=engine.prepareResearchInput({...options(),signal:controller.signal});
  await assert.rejects(engine.analyze([{src:'not-decoded'}]),/已有分析/);await assert.rejects(engine.prepareResearchInput(options()),/已有分析/);controller.abort();await assert.rejects(p,{name:'AbortError'});
  assert.equal(engine.configuration,null);assert.equal(engine.manifestCacheState,'unprepared');
  const retry=engine.prepareResearchInput(options()),w=h.instances[1];w.onmessage({data:{type:'ready',profileId:API.PROFILE_ID,profileVersion:1}});w.onmessage({data:{type:'result',result:output(w.request)}});assert.equal((await retry).modelForwards,0);
});
test('direct production Worker research selection is rejected before manifest/model resource access',async()=>{
  let fetches=0;const messages=[],context={URL,Map,Set,self:{location:{origin:'https://app.test'}},importScripts(){},postMessage:m=>messages.push(m),MineralCore:Core,fetch(){fetches++;throw Error('resource reads forbidden');},onmessage:null};
  vm.runInNewContext(fs.readFileSync(path.join(root,'engine-worker.js'),'utf8'),context);await context.onmessage({data:{type:'analyze',profileId:API.PROFILE_ID}});
  assert.equal(fetches,0);assert.equal(messages.at(-1).type,'error');assert.match(messages.at(-1).message,/研究profile/);
});
test('public research input passes window-bound browser timers to its Worker client',async()=>{
  const h=client(),window={Worker:h.host.Worker,ShikuangResearchInput:API};let calls=0;
  window.setTimeout=function(fn,ms){assert.equal(this,window,'native DOM timers require their Window receiver');calls++;return h.host.setTimeout(fn,ms);};window.clearTimeout=function(id){assert.equal(this,window);return h.host.clearTimeout(id);};
  vm.runInNewContext(fs.readFileSync(path.join(root,'inference.js'),'utf8'),{window,MineralCore:Core,location:{href:'https://app.test/app/'},setTimeout:window.setTimeout,clearTimeout:window.clearTimeout,DOMException,AbortController});
  assert.equal((await window.MineralEngine.prepareResearchInput(options())).modelForwards,0);assert.equal(calls,2);assert.equal(h.timers.size,0);
});
test('research Worker source/compiled closure use shell-specific imports, without ORT or model loading',()=>{
  const shell=require('../tools/shell-release.cjs'),compat=require('../tools/compat-js.cjs'),compile=compat.transformer(),id='a'.repeat(64);
  for(const file of contract.ASSETS.filter(file=>file.endsWith('.js'))){const bytes=shell.render(file,fs.readFileSync(path.join(root,file)),id),compiled=compile(file,bytes);compat.assertSyntax(file,compiled.toString());}
  const source=fs.readFileSync(path.join(root,API.RESOURCE_PATH),'utf8'),rendered=shell.render(API.RESOURCE_PATH,Buffer.from(source),id).toString();
  assert.doesNotMatch(source,/ort\.|InferenceSession|\.onnx/);for(const match of rendered.matchAll(/importScripts\('([^']+)'\)/g))assert.equal(new URL(match[1],'https://app.test/app/'+API.RESOURCE_PATH).searchParams.get('v'),'shell-'+id);
});
