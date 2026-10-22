'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const Profile=require('../research/shikuang-research-native-roi-q16-torchf32-v1/profile.js');
const Norm=require('../research/shikuang-research-native-roi-q16-torchf32-v1/frozen/vendor/normalization.js');
const LUT=fs.readFileSync(path.join(__dirname,'../research/shikuang-research-native-roi-q16-torchf32-v1/frozen/vendor/normalization-lut.f32le.bin'));
const ID=Profile.PROFILE_ID,DEFAULT_LIMITS={inputMemoryBudgetBytes:512*1048576,maxNativePixels:40000000};
const full={x0:0,y0:0,x1:1,y1:1};
function frame(w,h,paint=(x,y)=>[x%256,y%256,(x+y)%256,255]){
 const rgba=new Uint8Array(w*h*4);
 for(let y=0;y<h;y++)for(let x=0;x<w;x++)rgba.set(paint(x,y),(y*w+x)*4);
 return {width:w,height:h,rgba,colorSpace:'srgb',orientationApplied:true,stage:'native-oriented-srgb-no-scale',priorResizeCount:0,jpegRoundTripsCreated:0,route:'photo-file',decoderEvidence:'synthetic pixel fixture; not a decoded photo',sourceHeader:{kind:'file-photo',width:w,height:h,exifOrientation:1,orientationEvidence:'synthetic fixture orientation identity',encodedBytes:0,headerCheckedBeforeDecode:true}};
}
function run(f,roi=full,extra={}){return Profile.preprocess({profileId:ID,frame:f,normalizedROI:roi,geometryLUTBytes:LUT,limits:DEFAULT_LIMITS,...extra});}
function bits(f){const b=new ArrayBuffer(4),v=new DataView(b);v.setFloat32(0,f,true);return v.getUint32(0,true);}
function rgbAt(r,x,y){return [...r.rgb224.subarray((y*224+x)*3,(y*224+x)*3+3)];}
test('research profile must be explicitly selected and cannot register a model',()=>{
 for(const id of [undefined,null,'','inherited-2.0-audited','center-square'])assert.throws(()=>Profile.selectResearchProfile(id));
 assert.equal(Profile.selectResearchProfile(ID),Profile.PROFILE);
 assert.equal(Profile.PROFILE.productRegistered,false);assert.equal(Profile.PROFILE.decoderCrossPlatformParityProven,false);
 assert.ok(Object.isFrozen(Profile.PROFILE));assert.ok(Object.isFrozen(Profile.PROFILE.outputShape));
 assert.throws(()=>Profile.preprocess({frame:frame(3,3)}),/profile/);
 for(const key of ['cropPercent','legacyInput'])assert.throws(()=>run(frame(3,3),full,{[key]:undefined}),/Legacy/);
});
test('identity 224 geometry preserves every synthetic RGB byte and explicit LE NCHW values',()=>{
 const f=frame(224,224),r=run(f),tensor=Profile.toRuntimeTensor(ID,r.tensorFloat32LE);
 assert.deepEqual(r.tensorShape,[1,3,224,224]);
 for(let k=0;k<224*224;k++)for(let c=0;c<3;c++){
  assert.equal(r.rgb224[k*3+c],f.rgba[k*4+c]);
  assert.equal(bits(tensor[c*224*224+k]),bits(Norm.value(c,f.rgba[k*4+c])));
 }
 assert.equal(r.productionRegistration,false);assert.equal(r.trainingAdmissionGrantedByThisModule,false);
 assert.equal(r.memoryLedger.sourceROICopyBytes,0);assert.equal(r.memoryLedger.materializedPaddingRGBABytes,0);
});
test('all 768 channel/u8 values match independent bit-level f32 operation order and differ from legacy',()=>{
 const means=[.485,.456,.406],stds=[.229,.224,.225],f=Math.fround;let legacyDifferent=0;
 for(let c=0;c<3;c++)for(let v=0;v<256;v++){
  const divided=f(v/255),subtracted=f(divided-f(means[c])),expected=f(subtracted/f(stds[c]));
  assert.equal(bits(Norm.value(c,v)),bits(expected));
  if(bits(expected)!==bits(f((v/255-means[c])/stds[c])))legacyDifferent++;
 }
 assert.ok(legacyDifferent>100,'test must detect legacy final-cast mismatch');
 assert.equal(bits(Norm.value(0,0)),0xc0078bbd); // independently checked with Python struct f32 operations
 assert.equal(bits(Norm.value(2,255)),0x4028f5c3);
});
test('full aspect gray127 padding retains rectangular content and native quality excludes padding',()=>{
 const r=run(frame(448,224,()=>[0,40,240,255]));
 assert.deepEqual(r.geometry.offsetXY,[0,112]);assert.equal(r.geometry.virtualEdge,448);
 assert.deepEqual(rgbAt(r,100,0),[127,127,127]);assert.deepEqual(rgbAt(r,100,100),[0,40,240]);
 assert.deepEqual(rgbAt(r,100,223),[127,127,127]);
 assert.equal(r.quality.pixelCount,448*224);assert.equal(r.quality.grayPaddingIncluded,false);
 const tall=run(frame(224,448,()=>[240,40,0,255]));
 assert.deepEqual(tall.geometry.offsetXY,[112,0]);assert.deepEqual(rgbAt(tall,0,100),[127,127,127]);
 assert.deepEqual(rgbAt(tall,100,100),[240,40,0]);
});
test('odd virtual padding is top/left floor-biased as frozen geometry specifies',()=>{
 const r=run(frame(3,4,()=>[255,0,0,255]));
 assert.deepEqual(r.geometry.offsetXY,[0,0]);assert.equal(r.geometry.virtualEdge,4);
 assert.deepEqual(rgbAt(r,0,100),[255,0,0]);assert.deepEqual(rgbAt(r,223,100),[127,127,127]);
});
test('native normalized ROI floor/ceil, coordinate order, and outside-ROI pixels',()=>{
 const f=frame(8,6,(x,y)=>x>=2&&x<6&&y>=1&&y<5?[25,50,75,255]:[255,255,255,0]);
 const r=run(f,{y1:5/6,x1:6/8,y0:1/6,x0:2/8});
 assert.deepEqual(r.nativeROI,{x0:2,y0:1,x1:6,y1:5});
 for(const p of [[0,0],[111,111],[223,223]])assert.deepEqual(rgbAt(r,...p),[25,50,75]);
 const q=run(frame(10,10),{x0:.21,y0:.21,x1:.59,y1:.59});assert.deepEqual(q.nativeROI,{x0:2,y0:2,x1:6,y1:6});
});
test('invalid ROI is rejected instead of clipped or promoted to a center crop',()=>{
 const f=frame(10,10);
 for(const roi of [null,{x0:-.01,y0:0,x1:1,y1:1},{x0:0,y0:0,x1:1.01,y1:1},{x0:0,y0:0,x1:NaN,y1:1},{x0:.5,y0:0,x1:.5,y1:1},{x0:0,y0:0,x1:.2,y1:1}])assert.throws(()=>run(f,roi));
});
test('pre-scaled, re-encoded, wrong orientation/color, and absent decode evidence fail closed',()=>{
 for(const patch of [{priorResizeCount:1},{jpegRoundTripsCreated:1},{colorSpace:'display-p3'},{orientationApplied:false},{decoderEvidence:''},{stage:'preview-1536'}])assert.throws(()=>run({...frame(3,3),...patch}));
 const f=frame(3,4);f.sourceHeader.exifOrientation=6;assert.throws(()=>run(f),/原尺寸/);
 f.width=4;f.height=3;assert.deepEqual(run(f).reservation.orientedDimensions,[4,3]);
});
test('selected ROI must be opaque and real stable byte storage; offset views are supported',()=>{
 const f=frame(3,3);f.rgba[3]=254;assert.throws(()=>run(f),/alpha255/);
 for(const rgba of [Array(36).fill(255),new Uint16Array(36),new Uint8Array(35),{length:36,[Symbol.toStringTag]:'Uint8Array'}])assert.throws(()=>run({...frame(3,3),rgba}));
 if(typeof SharedArrayBuffer==='function')assert.throws(()=>run({...frame(3,3),rgba:new Uint8Array(new SharedArrayBuffer(36))}));
 const real=frame(3,3),larger=new Uint8Array(39);larger.set(real.rgba,3);real.rgba=larger.subarray(3);assert.equal(run(real).rgb224.length,224*224*3);
});
test('explicit budgets and immutable exact LUT prevent silent downscaling or alternate normalization',()=>{
 assert.throws(()=>run(frame(3,3),full,{limits:undefined}),/预算/);
 assert.throws(()=>run(frame(400,400),full,{limits:{inputMemoryBudgetBytes:2097152,maxNativePixels:40000000}}),/预算不足/);
 assert.throws(()=>run(frame(3,3),full,{limits:{inputMemoryBudgetBytes:512*1048576,maxNativePixels:8}}));
 const altered=Uint8Array.from(LUT);altered[0]^=1;assert.throws(()=>run(frame(3,3),full,{geometryLUTBytes:altered}),/LUT/);
 assert.throws(()=>run(frame(3,3),full,{geometryLUTBytes:LUT.subarray(1)}),/LUT/);
});
test('presented video frame has separate orientation declaration and cannot be fake file EXIF',()=>{
 const f=frame(3,4);f.route='video-file-frame';f.sourceHeader={kind:'decoder-frame',width:3,height:4,frameOrientationApplied:true,orientationEvidence:'synthetic already-presented video frame'};
 assert.equal(run(f).route,'video-file-frame');
 f.sourceHeader.exifOrientation=1;assert.throws(()=>run(f),/EXIF/);
 const bad=frame(3,4);bad.route='video-file-frame';assert.throws(()=>run(bad),/视频帧/);
});
test('runtime tensor conversion reads LE unaligned views and rejects non-finite/wrong/shared buffers',()=>{
 const n=3*224*224*4,storage=new Uint8Array(n+3),bytes=storage.subarray(3),v=new DataView(bytes.buffer,bytes.byteOffset,n);
 for(let i=0;i<n/4;i++)v.setFloat32(i*4,i%2?-0:Math.fround((i%769-384)/127),true);
 const tensor=Profile.toRuntimeTensor(ID,bytes);assert.equal(tensor.byteLength,n);assert.equal(Object.is(tensor[1],-0),true);
 assert.equal(bits(tensor[100]),v.getUint32(400,true));
 assert.throws(()=>Profile.toRuntimeTensor('legacy',bytes),/profile/);
 for(const input of [new Uint8Array(n-1),new Float32Array(n/4),Array(n).fill(0)])assert.throws(()=>Profile.toRuntimeTensor(ID,input));
 v.setFloat32(0,NaN,true);assert.throws(()=>Profile.toRuntimeTensor(ID,bytes),/non-finite/);
 v.setFloat32(0,Infinity,true);assert.throws(()=>Profile.toRuntimeTensor(ID,bytes),/non-finite/);
 if(typeof SharedArrayBuffer==='function')assert.throws(()=>Profile.toRuntimeTensor(ID,new Uint8Array(new SharedArrayBuffer(n))),/unshared/);
});
test('browser classic-script module path supports synthetic native pixels without DOM or Node globals',()=>{
 const context=vm.createContext({});
 for(const name of ['frozen/vendor/native-roi-q16.js','frozen/vendor/normalization.js','frozen/native-roi-entry.js','profile.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../research/shikuang-research-native-roi-q16-torchf32-v1/',name),'utf8'),context,{filename:name});
 const result=vm.runInContext(`(()=>{const api=ShikuangResearchPreprocessProfile,rgba=new Uint8Array(3*3*4);rgba.fill(255);const lut=new Uint8Array(${JSON.stringify([...LUT])});const f={width:3,height:3,rgba,colorSpace:'srgb',orientationApplied:true,stage:'native-oriented-srgb-no-scale',priorResizeCount:0,jpegRoundTripsCreated:0,route:'photo-file',decoderEvidence:'synthetic VM fixture',sourceHeader:{kind:'file-photo',width:3,height:3,exifOrientation:1,orientationEvidence:'synthetic fixture'}};const r=api.preprocess({profileId:api.PROFILE_ID,frame:f,normalizedROI:{x0:0,y0:0,x1:1,y1:1},geometryLUTBytes:lut,limits:{inputMemoryBudgetBytes:8388608,maxNativePixels:100}});return {rgb0:r.rgb224[0],tensor0:api.toRuntimeTensor(api.PROFILE_ID,r.tensorFloat32LE)[0],registered:r.productionRegistration};})()`,context);
 assert.equal(result.rgb0,255);assert.equal(bits(result.tensor0),bits(Norm.value(0,255)));assert.equal(result.registered,false);
});
test('classic-script dependency version mismatch is rejected before a profile can be used',()=>{
 const context=vm.createContext({ShikuangNativeROIEntry:{CONTRACT_ID:'legacy'},ShikuangNativeROIQ16:{},ShikuangInputNormalization:{}});
 assert.throws(()=>vm.runInContext(fs.readFileSync(path.join(__dirname,'../research/shikuang-research-native-roi-q16-torchf32-v1/profile.js'),'utf8'),context),/dependency version mismatch/);
 assert.equal(context.ShikuangResearchPreprocessProfile,undefined);
});
