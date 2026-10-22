'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),API=require('../research-input.js'),Photo=require('../research-photo.js'),Core=require('../core.js');
function jpeg(w=12,h=8){return new Blob([Uint8Array.from([255,216,255,192,0,17,8,h>>8,h&255,w>>8,w&255,3,1,17,0,2,17,1,3,17,1,255,218,0,2,255,217])],{type:'image/jpeg'});}
function options(extra={}){return {profileId:API.PROFILE_ID,profileVersion:1,transferOwnership:true,encodedPhoto:jpeg(),route:'photo-file',normalizedROI:{x0:0,y0:0,x1:1,y1:1},limits:{inputMemoryBudgetBytes:8*1048576,maxNativePixels:40e6},...extra};}
function host(config={}){
  const images=[],canvases=[],revoked=[],draws=[],prepared=[],timers=new Set();
  class Image{
    constructor(){this.complete=true;this.naturalWidth=config.width??12;this.naturalHeight=8;images.push(this);}
    decode(){return config.decode?config.decode(this):Promise.resolve();}
    removeAttribute(name){this.removed=name;}
  }
  const h={Blob,Image,URL:{createObjectURL:()=> 'blob:synthetic',revokeObjectURL:url=>revoked.push(url)},
    document:{createElement(name){assert.equal(name,'canvas');const c={width:0,height:0,getContext(kind,attrs){assert.equal(kind,'2d');assert.equal(attrs.colorSpace,'srgb');return {drawImage(...args){draws.push(args);},getImageData(x,y,w,h){return {data:new Uint8ClampedArray(w*h*4).fill(255),colorSpace:config.colorSpace??'srgb'};}};}};canvases.push(c);return c;}},
    setTimeout(fn,ms){const id=setTimeout(()=>{timers.delete(id);fn();},ms);timers.add(id);return id;},clearTimeout(id){clearTimeout(id);timers.delete(id);},
    inputClient:{prepare(o){prepared.push(o);return config.prepare?config.prepare(o):Promise.resolve({synthetic:'worker-result',sourceHeader:o.frame.sourceHeader});}}};
  return {...h,client:Photo.createClient(h),images,canvases,revoked,draws,prepared,timers};
}
test('encoded research photo validates exact explicit API before any decoder creation',async()=>{
  const h=host();for(const p of [{profileId:'legacy'},{profileVersion:2},{transferOwnership:false},{route:'video-file-frame'},{frame:{}},{src:'preview1536'},{modelPath:'model.onnx'},{encodedPhoto:{}},{timeoutMs:0},{normalizedROI:{x0:0,y0:0,x1:2,y1:1}}])assert.throws(()=>h.client.prepare(options(p)));
  assert.equal(h.images.length,0);assert.equal(h.timers.size,0);
});
test('malformed header, undersized native ROI and insufficient budget reject before decode/Canvas',async()=>{
  const h=host();await assert.rejects(h.client.prepare(options({encodedPhoto:new Blob(['not JPEG at all'])})));await assert.rejects(h.client.prepare(options({encodedPhoto:jpeg(2048,2048)})),/预算不足/);await assert.rejects(h.client.prepare(options({normalizedROI:{x0:0,y0:0,x1:.1,y1:1}})),/不足3/);
  assert.equal(h.images.length,0);assert.equal(h.canvases.length,0);assert.equal(h.timers.size,0);
});
test('actual header dimensions and absence-default1 feed native 1:1 sRGB pixels and cleanup',async()=>{
  const h=host(),o=options(),frame=await h.client.decodePhoto(o);
  assert.deepEqual([frame.width,frame.height,frame.rgba.byteLength],[12,8,384]);assert.equal(frame.sourceHeader.exifOrientation,1);assert.match(frame.sourceHeader.orientationEvidence,/no_Exif_default1/);assert.equal(frame.sourceHeader.headerCheckedBeforeDecode,true);assert.equal(frame.priorResizeCount,0);assert.equal(frame.jpegRoundTripsCreated,0);API.validateRequest({...o,frame});
  assert.equal(h.draws.length,1);assert.deepEqual(h.draws[0].slice(1),[0,0,12,8]);assert.equal(h.images[0].removed,'src');assert.deepEqual(h.revoked,['blob:synthetic']);assert.deepEqual([h.canvases[0].width,h.canvases[0].height],[1,1]);assert.equal(h.timers.size,0);
});
test('encoded prepare hands decoded native frame to research Worker client, snapshots metadata and shares deadline',async()=>{
  let resolve;const h=host({decode:()=>new Promise(r=>resolve=r)}),o=options({timeoutMs:5000}),p=h.client.prepare(o);
  while(!h.images.length)await new Promise(r=>setImmediate(r));o.normalizedROI.x1=.1;o.limits.maxNativePixels=9;o.route='video-file-frame';resolve();
  const result=await p;assert.equal(result.synthetic,'worker-result');assert.equal(h.prepared.length,1);const request=h.prepared[0];assert.equal(request.frame.width,12);assert.equal(request.normalizedROI.x1,1);assert.equal(request.limits.maxNativePixels,40e6);assert.equal(request.frame.route,'photo-file');assert.ok(request.timeoutMs>0&&request.timeoutMs<=5000);assert.equal(request.transferOwnership,true);assert.equal(h.timers.size,0);
});
test('dimension/color mismatch and decode error clean up and never dispatch a Worker',async()=>{
  for(const config of [{width:6},{colorSpace:'display-p3'},{decode:()=>Promise.reject(Error('codec failed'))}]){const h=host(config);await assert.rejects(h.client.prepare(options()));assert.equal(h.prepared.length,0);assert.equal(h.images[0].removed,'src');assert.equal(h.revoked.length,1);assert.equal(h.timers.size,0);}
});
test('Image construction failure revokes the already-created encoded Blob URL',async()=>{
  const h=host();h.Image=class{constructor(){throw Error('decoder allocation failed');}};
  await assert.rejects(Photo.createClient(h).prepare(options()),/decoder allocation/);assert.deepEqual(h.revoked,['blob:synthetic']);assert.equal(h.prepared.length,0);assert.equal(h.timers.size,0);
});
test('abort during native decode clears resources and never posts stale pixels; retry works',async()=>{
  const c=new AbortController(),h=host({decode:()=>new Promise(()=>{})}),p=h.client.prepare(options({signal:c.signal}));while(!h.images.length)await new Promise(r=>setImmediate(r));c.abort();await assert.rejects(p,{name:'AbortError'});await new Promise(r=>setImmediate(r));assert.equal(h.timers.size,0);assert.equal(h.prepared.length,0);assert.equal(h.revoked.length,1);assert.equal(h.images[0].removed,'src');
  const before=host(),aborted=new AbortController();aborted.abort();assert.throws(()=>before.client.prepare(options({signal:aborted.signal})),{name:'AbortError'});assert.equal(before.images.length,0);
  assert.equal((await host().client.prepare(options())).synthetic,'worker-result');
});
test('one overall timeout includes Worker phase and aborts it without a preview fallback',async()=>{
  let stopped=false;const h=host({prepare:o=>new Promise((resolve,reject)=>o.signal.addEventListener('abort',()=>{stopped=true;reject(new DOMException('stopped','AbortError'));},{once:true}))});
  await assert.rejects(h.client.prepare(options({timeoutMs:25})),/整体上限/);assert.equal(stopped,true);assert.equal(h.prepared.length,1);assert.equal(h.timers.size,0);assert.equal(h.revoked.length,1);
});
test('public engine encoded-photo entry shares the analysis active gate and recovers after cancel',async()=>{
  let hold=true;const h=host({decode:()=>hold?new Promise(()=>{}):Promise.resolve()}),window={...h,ShikuangResearchInput:{createClient:()=>h.inputClient},ShikuangResearchPhoto:{createClient:()=>h.client}};
  vm.runInNewContext(fs.readFileSync(require.resolve('../inference.js'),'utf8'),{window,MineralCore:Core,location:{href:'https://app.test/app/'},setTimeout,clearTimeout,DOMException,AbortController,fetch(){throw Error('production resource read forbidden');}});
  const c=new AbortController(),p=window.MineralEngine.prepareResearchPhoto(options({signal:c.signal}));
  await assert.rejects(window.MineralEngine.analyze([{src:'never-decoded'}]),/已有分析/);await assert.rejects(window.MineralEngine.prepareResearchInput({}),/已有分析/);await assert.rejects(window.MineralEngine.prepareResearchPhoto(options()),/已有分析/);
  c.abort();await assert.rejects(p,{name:'AbortError'});hold=false;assert.equal((await window.MineralEngine.prepareResearchPhoto(options())).synthetic,'worker-result');assert.equal(window.MineralEngine.configuration,null);assert.equal(window.MineralEngine.manifestCacheState,'unprepared');
});
test('public encoded-photo entry passes Window receivers for both research clients timers',async()=>{
  const h=host(),window={...h,ShikuangResearchPhoto:Photo,ShikuangResearchInput:{createClient:timerHost=>{
    const id=timerHost.setTimeout(()=>{},1000);timerHost.clearTimeout(id);return h.inputClient;
  }}};let calls=0;
  window.setTimeout=function(fn,ms){assert.equal(this,window,'native DOM timer receiver');calls++;return h.setTimeout(fn,ms);};window.clearTimeout=function(id){assert.equal(this,window);return h.clearTimeout(id);};
  vm.runInNewContext(fs.readFileSync(require.resolve('../inference.js'),'utf8'),{window,MineralCore:Core,location:{href:'https://app.test/app/'},setTimeout:window.setTimeout,clearTimeout:window.clearTimeout,DOMException,AbortController});
  assert.equal((await window.MineralEngine.prepareResearchPhoto(options())).synthetic,'worker-result');assert.equal(calls,3);assert.equal(h.timers.size,0);
});
