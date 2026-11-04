/* Controlled candidate orchestration, separate from production schema1. */
(function(root,factory){
  const browser=typeof window==='object'&&window,commonJS=typeof module==='object'&&module&&module.exports;
  const api=browser||!commonJS?factory(root.ShikuangCandidateModel):factory(require('./candidate-model.js'));
  if(commonJS)module.exports=api;
  if(browser||!commonJS)root.ShikuangCandidateInference=api;
})(typeof window==='object'&&window?window:typeof globalThis==='object'?globalThis:this,function(C){
  'use strict';
  const stopped=()=>new DOMException('候选诊断已停止','AbortError');
  const hash=bytes=>Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');
  function intent(options){
    if(!options||options.diagnostic!==true)throw new Error('开发候选仅接受显式diagnostic调用；未注册为正式识别模型');
    if(options.timeoutMs!==undefined&&(!Number.isInteger(options.timeoutMs)||options.timeoutMs<1||options.timeoutMs>120000))throw new Error('候选诊断整体上限为1–120000毫秒');
  }
  function createClient(host){
    const registered=new WeakMap();
    function job(options,work){
      intent(options);const signal=options.signal;if(signal?.aborted)throw stopped();
      const controller=new AbortController(),deadline=Date.now()+(options.timeoutMs??120000);
      return new Promise((resolve,reject)=>{
        let settled=false,timer;const cleanup=[];
        const finish=(error,result)=>{if(settled)return;settled=true;host.clearTimeout(timer);signal?.removeEventListener('abort',cancel);controller.abort();for(const action of cleanup.reverse())try{action();}catch(_){}error?reject(error):resolve(result);};
        const cancel=()=>finish(stopped());signal?.addEventListener('abort',cancel,{once:true});
        timer=host.setTimeout(()=>finish(new Error('开发候选诊断超过整体上限，已停止')),options.timeoutMs??120000);
        const check=()=>{if(controller.signal.aborted)throw stopped();if(Date.now()>=deadline)throw new Error('开发候选诊断超过整体上限');};
        const j={signal:controller.signal,check,cleanup:fn=>cleanup.push(fn),remaining:()=>Math.max(1,deadline-Date.now())};
        Promise.resolve().then(()=>{check();return work(j);}).then(result=>{try{check();finish(null,result);}catch(e){finish(e);}},error=>finish(error));
      });
    }
    async function prepareWithin(options,j){
      if(typeof options.manifestSha256!=='string'||!/^[a-f0-9]{64}$/.test(options.manifestSha256))throw new Error('候选清单需显式SHA绑定');
      const url=C.manifestURL(options.manifestURL,host.base).href,expected=options.manifestSha256;
      const legacy=await host.prepareLegacy({signal:j.signal});j.check();const legacyHash=host.legacyHash(legacy);
      const response=await host.fetch(url,{cache:'no-cache',signal:j.signal});
      const bytes=await host.readResource(response,100000,undefined,undefined,{signal:j.signal,timeout:Math.min(15000,j.remaining())});j.check();
      if(!host.crypto?.subtle||hash(await host.crypto.subtle.digest('SHA-256',bytes))!==expected)throw new Error('候选模型清单SHA不匹配');j.check();
      const manifest=C.validateManifest(JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes)),legacy,legacyHash);
      const result=Object.freeze({purpose:C.PURPOSE,productionRegistered:false,independentAcceptance:false,manifest,manifestURL:url,manifestSha256:expected,legacyManifestSha256:legacyHash});
      registered.set(result,{manifest,legacy,manifestURL:url,manifestHash:expected,legacyHash});return result;
    }
    function workerRun(record,inputs,gateInputs,blocked,j,report){
      C.validateInputs(inputs,gateInputs);
      if(!Array.isArray(blocked)||blocked.length!==1000||blocked.some(x=>typeof x!=='boolean'))throw new Error('候选诊断输入筛查清单不完整');
      if(typeof host.Worker!=='function')throw new Error('当前环境不支持后台候选诊断');
      return new Promise((resolve,reject)=>{
        let worker,settled=false,posted=false,bootTimer;
        const finish=(error,value)=>{if(settled)return;settled=true;host.clearTimeout(bootTimer);j.signal.removeEventListener('abort',cancel);if(worker){worker.onmessage=null;worker.onerror=null;worker.terminate();}error?reject(error):resolve(value);};
        const cancel=()=>finish(stopped());j.signal.addEventListener('abort',cancel,{once:true});
        bootTimer=host.setTimeout(()=>finish(new Error('候选识别线程启动超过15秒')),Math.min(15000,j.remaining()));
        try{
          worker=new host.Worker(host.resourceURL('candidate-worker.js'));if(settled){worker.terminate();return;}j.cleanup(()=>finish(stopped()));
          worker.onerror=event=>finish(new Error('候选识别线程失败：'+String(event.message||'未知错误').slice(0,180)));
          worker.onmessage=({data})=>{
            if(settled)return;
            try{
              if(data.type==='ready'){
                if(data.purpose!==C.PURPOSE)throw new Error('候选线程用途不匹配');host.clearTimeout(bootTimer);j.check();
                if(!posted){posted=true;worker.postMessage({type:'analyze-candidate',diagnostic:true,base:new URL('./',host.base).href,manifestURL:record.manifestURL,manifestSha256:record.manifestHash,legacyManifestSha256:record.legacyHash,profileId:C.PROFILE.profileId,profileVersion:1,gateProfileId:C.GATE_PROFILE,inputs,gateInputs,blocked},[...inputs,...gateInputs].map(x=>x.buffer));}
              }else if(data.type==='progress')report(String(data.message||''));
              else if(data.type==='result'){if(!posted)throw new Error('候选线程尚未接收输入');j.check();finish(null,C.validateResult(data,record.manifest,record.manifestHash,inputs.length));}
              else if(data.type==='error'||data.type==='boot-error')throw new Error(String(data.message||'开发候选诊断失败'));
            }catch(error){finish(error);}
          };
          if(j.signal.aborted)cancel();
        }catch(error){finish(error);}
      });
    }
    return Object.freeze({
      prepare(options){return job(options,j=>prepareWithin(options,j));},
      analyze(photos,options){
        intent(options);
        if(!Array.isArray(photos)||photos.length<1||photos.length>3)throw new Error('候选诊断需1–3张同一标本的原图或原尺寸帧');
        const snapshots=photos.map(p=>{
          if(!p||['src','crop','legacyInput'].some(k=>Object.prototype.hasOwnProperty.call(p,k)))throw new Error('候选诊断禁止生产预览或隐式中心ROI');
          if(!Number.isFinite(p.gateCropPercent)||p.gateCropPercent<.5||p.gateCropPercent>1)throw new Error('旧gate中心区域需显式0.5–1');
          if(!!p.frame===!!p.encodedPhoto)throw new Error('候选诊断需明确一个原图Blob或原尺寸帧');
          return {...p,frame:p.frame?{...p.frame,sourceHeader:{...p.frame.sourceHeader}}:undefined,normalizedROI:{...p.normalizedROI},limits:{...p.limits}};
        });
        const report=typeof options.report==='function'?options.report:()=>{};
        return job(options,async j=>{
          const prepared=options.prepared||await prepareWithin(options,j),record=registered.get(prepared);
          if(!record)throw new Error('候选清单必须先由当前诊断客户端校验');j.check();
          const inputs=[],gateInputs=[],inputEvidence=[];
          for(let i=0;i<snapshots.length;i++){
            const photo=snapshots[i];report(`准备开发候选原图 ${i+1}/${snapshots.length}…`);j.check();
            const request={profileId:C.PROFILE.profileId,profileVersion:1,transferOwnership:true,normalizedROI:photo.normalizedROI,limits:photo.limits,signal:j.signal,timeoutMs:j.remaining()};
            let frame;
            if(photo.frame)frame=host.validateFrame({...request,frame:photo.frame}).request.frame;
            else frame=await host.decodePhoto({...request,encodedPhoto:photo.encodedPhoto,route:photo.route});j.check();
            // Legacy gate gets its own center-square/bilinear/final-cast tensor
            // before transfer of original pixels into the research Q16 Worker.
            const gate=host.prepareLegacyGate(frame,photo.gateCropPercent,record.legacy.input);j.check();
            const native=await host.prepareInput({...request,timeoutMs:j.remaining(),frame});j.check();
            if(native.profileId!==C.PROFILE.profileId||native.normId!==C.PROFILE.normId||native.contractId!==C.PROFILE.inputContract||native.productionRegistration!==false)throw new Error('研究预处理结果不能与候选profile绑定');
            gateInputs.push(gate);inputs.push(native.runtimeTensor);
            inputEvidence.push({photo:i,route:frame.route,nativeROI:native.nativeROI,gateCropPercent:photo.gateCropPercent,gateProfileId:C.GATE_PROFILE,researchProfileId:C.PROFILE.profileId});
          }
          const result=await workerRun(record,inputs,gateInputs,host.blocked,j,report);j.check();
          return {...C.diagnostics(result,record.manifest),inputEvidence};
        });
      }
    });
  }
  return Object.freeze({createClient});
});
