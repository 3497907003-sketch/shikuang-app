'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto');
const C=require('../candidate-model.js'),Core=require('../core.js');
async function harness(bridge,available=true){
 let host;
 const window={setTimeout,clearTimeout,crypto:crypto.webcrypto,ShikuangCandidateModel:C,
  Capacitor:{isNativePlatform:()=>true,isPluginAvailable:()=>available,registerPlugin:()=>bridge},
  ShikuangResearchInput:{createClient:()=>({})},ShikuangResearchPhoto:{createClient:()=>({})},
  ShikuangCandidateInference:{createClient:value=>{host=value;return {prepare:async()=>({})};}}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../inference.js'),'utf8'),{window,MineralCore:Core,location:{href:'https://app.test/app/index.html'},URL,setTimeout,clearTimeout,DOMException,AbortController,crypto:crypto.webcrypto,btoa});
 await window.MineralEngine.prepareCandidate({diagnostic:true});
 const controller=new AbortController(),job={signal:controller.signal,check(){if(controller.signal.aborted)throw new DOMException('stopped','AbortError');}};
 return {host,controller,job,record:{manifestURL:'https://app.test/app/research/candidates/fold0.json',manifestHash:'a'.repeat(64),legacyHash:'b'.repeat(64)},inputs:[new Float32Array(3*224*224).fill(7)],gates:[new Float32Array(3*224*224).fill(42)]};
}
test('public Android candidate bridge serializes independent little-endian tensors and explicit identities',async()=>{
 let packet,removed=0,cancelled=0;
 const bridge={addListener:async()=>({remove(){removed++;}}),classifyCandidate:async value=>{packet=value;return {marker:'raw native reply'};},cancel(){cancelled++;}};
 const h=await harness(bridge),reply=await h.host.nativeRun(h.record,h.inputs,h.gates,Array(1000).fill(false),h.job,()=>{});
 assert.equal(reply.marker,'raw native reply');assert.equal(packet.purpose,C.PURPOSE);assert.equal(packet.profileId,C.PROFILE.profileId);assert.equal(packet.gateProfileId,C.GATE_PROFILE);
 assert.equal(packet.candidateManifestPath,'research/candidates/fold0.json');assert.equal(packet.candidateManifestSha256,h.record.manifestHash);assert.equal(packet.legacyManifestSha256,h.record.legacyHash);
 assert.equal(packet.inputEncoding,'float32-le-base64');assert.equal(Buffer.from(packet.inputs[0],'base64').readFloatLE(0),7);assert.equal(Buffer.from(packet.gateInputs[0],'base64').readFloatLE(0),42);
 assert.equal(Buffer.from(packet.inputs[0],'base64').length,602112);assert.equal(packet.mode,undefined);assert.equal(packet.modelIds,undefined);assert.equal(removed,1);assert.equal(cancelled,0);
});
test('aborted Android candidate removes a late progress handle without starting inference',async()=>{
 let resolveHandle,removed=0,classifies=0,cancelled=0;
 const bridge={addListener:()=>new Promise(resolve=>{resolveHandle=resolve;}),classifyCandidate(){classifies++;},cancel(){cancelled++;}};
 const h=await harness(bridge),pending=h.host.nativeRun(h.record,h.inputs,h.gates,Array(1000).fill(false),h.job,()=>{});
 await new Promise(resolve=>setImmediate(resolve));h.controller.abort();await assert.rejects(pending,{name:'AbortError'});
 resolveHandle({remove(){removed++;}});await new Promise(resolve=>setImmediate(resolve));
 assert.equal(removed,1);assert.equal(classifies,0);assert.equal(cancelled,1);
});
test('Android candidate rejects unavailable endpoint or foreign manifest before dispatch',async()=>{
 let calls=0;const bridge={classifyCandidate(){calls++;},addListener(){calls++;}};
 const unavailable=await harness(bridge,false);assert.throws(()=>unavailable.host.nativeRun(unavailable.record,unavailable.inputs,unavailable.gates,[],unavailable.job,()=>{}),/原生候选组件/);
 const missing=await harness({});assert.throws(()=>missing.host.nativeRun(missing.record,missing.inputs,missing.gates,[],missing.job,()=>{}),/尚未接入/);
 const h=await harness(bridge);assert.throws(()=>h.host.nativeRun({...h.record,manifestURL:'https://elsewhere.test/research/candidates/fold0.json'},h.inputs,h.gates,[],h.job,()=>{}),/当前安装包/);
 assert.equal(calls,0);
});
