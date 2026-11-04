/* Separate controlled candidate worker; production engine-worker remains schema1. */
'use strict';
let bootError;
try{importScripts('./compat.js');importScripts('./vendor/ort.min.js');importScripts('./core.js');importScripts('./candidate-model.js');}catch(error){bootError=error.message||String(error);}
const candidateSessions=new Map();let busy=false,releaseFailed=false;
const send=(type,value)=>postMessage({type,...value});
const hex=bytes=>Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');
const sameShape=(value,wanted)=>Array.isArray(value)&&value.length===wanted.length&&value.every((n,i)=>n===wanted[i]||(i===0&&(n===-1||typeof n==='string')));
async function releaseAll(){
  for(const [key,session]of candidateSessions){
    try{await session.release();}catch(_){releaseFailed=true;throw new Error('候选识别资源释放失败，请重新执行诊断');}
    candidateSessions.delete(key);
  }
}
async function readManifest(url,expected){
  const bytes=await MineralCore.readResource(await fetch(url,{cache:'no-cache'}),100000,undefined,undefined,{timeout:15000});
  if(!crypto.subtle||hex(await crypto.subtle.digest('SHA-256',bytes))!==expected)throw new Error('候选或gate清单SHA不匹配');
  return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
}
async function sessionFor(model,base,manifestHash,candidate,candidateManifestURL,legacyHash){
  const key=manifestHash+'|'+model.path+'|'+model.sha256;
  if(candidateSessions.has(key))return candidateSessions.get(key);
  const url=candidate?ShikuangCandidateModel.modelURL(model,manifestHash,base,candidateManifestURL,legacyHash):MineralCore.modelResourceURL(model,manifestHash,base);
  const maximum=candidate?ShikuangCandidateModel.MODEL_MAX_BYTES:MineralCore.MODEL_MAX_BYTES;
  send('progress',{message:candidate?'校验开发候选模型资源…':'校验原有输入筛查资源…'});
  const bytes=await MineralCore.readResource(await fetch(url,candidate?{cache:'no-store'}:undefined),maximum,model.bytes);
  if(hex(await crypto.subtle.digest('SHA-256',bytes))!==model.sha256)throw new Error('候选或gate模型文件SHA不匹配');
  const session=await ort.InferenceSession.create(bytes,{executionProviders:['wasm'],graphOptimizationLevel:'all'});
  candidateSessions.set(key,session);
  if(session.inputNames.length!==1||session.outputNames.length!==1||session.inputNames[0]!==model.inputName||session.outputNames[0]!==model.outputName)throw new Error('候选模型输入输出名称不匹配');
  const input=session.inputMetadata?.[0],output=session.outputMetadata?.[0];
  if(input&&(input.isTensor!==true||input.type!=='float32'||!sameShape(input.shape,[1,3,224,224])))throw new Error('候选模型输入格式不匹配');
  if(output&&(output.isTensor!==true||output.type!=='float32'||!sameShape(output.shape,[1,model.classes])))throw new Error('候选模型输出格式不匹配');
  return session;
}
async function run(session,values,model){
  const input=new ort.Tensor('float32',values,[1,3,224,224]);let output;
  try{
    output=await session.run({[model.inputName]:input});const tensor=output[model.outputName];
    if(!tensor||tensor.type!=='float32'||JSON.stringify(tensor.dims)!==JSON.stringify([1,model.classes]))throw new Error('候选模型实际输出类型或形状不匹配');
    const result=Array.from(tensor.data);if(result.length!==model.classes||result.some(x=>!Number.isFinite(x)))throw new Error('候选模型实际输出包含无效数值');return result;
  }finally{input.dispose();if(output)Object.values(output).forEach(t=>t.dispose?.());}
}
onmessage=async({data})=>{
  if(data?.type!=='analyze-candidate')return;
  if(busy||releaseFailed){send('error',{message:'候选诊断线程忙或资源未释放，请重试'});return;}
  busy=true;
  try{
    if(bootError)throw new Error('候选诊断依赖加载失败：'+bootError);
    const C=ShikuangCandidateModel;
    if(data.diagnostic!==true||data.profileId!==C.PROFILE.profileId||data.profileVersion!==1||data.gateProfileId!==C.GATE_PROFILE)throw new Error('候选诊断需明确的双路profile');
    const base=new URL('./',data.base);if(!['http:','https:'].includes(base.protocol)||base.origin!==self.location.origin)throw new Error('候选诊断资源必须来自本App');
    const manifestURL=C.manifestURL(data.manifestURL,base);
    const legacy=MineralCore.validateManifest(await readManifest(new URL('model-manifest.json',base),data.legacyManifestSha256));
    const manifest=C.validateManifest(await readManifest(manifestURL,data.manifestSha256),legacy,data.legacyManifestSha256);
    C.validateInputs(data.inputs,data.gateInputs);
    if(!Array.isArray(data.blocked)||data.blocked.length!==1000||data.blocked.some(x=>typeof x!=='boolean'))throw new Error('候选诊断输入筛查清单不完整');
    ort.env.wasm.wasmPaths={mjs:MineralCore.shellResourceURL('vendor/ort-wasm-simd-threaded.mjs',base),wasm:MineralCore.shellResourceURL('vendor/ort-wasm-simd-threaded.wasm',base)};ort.env.wasm.numThreads=1;ort.env.wasm.proxy=false;
    const screening=[],runs=[],gate=manifest.gate.model;
    const gateSession=await sessionFor(gate,base,data.legacyManifestSha256,false);
    for(let i=0;i<data.gateInputs.length;i++){
      send('progress',{message:`原有输入筛查 ${i+1}/${data.gateInputs.length}…`});
      const values=await run(gateSession,data.gateInputs[i],gate);screening.push({photo:i,values});
      send('candidate-screening-diagnostic',{purpose:C.PURPOSE,photo:i,legacyManifestSha256:data.legacyManifestSha256,gateModelId:gate.id,gateModelSha256:gate.sha256,values});
      if(MineralCore.screen(values,data.blocked).rejected)throw new Error(MineralCore.NON_MINERAL);
    }
    // Release old gate before allocating the larger candidate model.
    await releaseAll();
    const classifier=manifest.classifier,session=await sessionFor(classifier,base,data.manifestSha256,true,manifestURL.href,data.legacyManifestSha256);
    for(let i=0;i<data.inputs.length;i++){
      send('progress',{message:`开发候选诊断 ${i+1}/${data.inputs.length} · fold${classifier.fold}…`});
      runs.push({photo:i,model:classifier.id,values:await run(session,data.inputs[i],classifier)});
    }
    await releaseAll();
    send('result',{purpose:C.PURPOSE,productionRegistered:false,independentAcceptance:false,manifestSha256:data.manifestSha256,modelVersion:manifest.version,classifierId:classifier.id,profileId:C.PROFILE.profileId,labels:[...C.LABELS],runs,screening});
  }catch(error){
    if(!releaseFailed)try{await releaseAll();}catch(_){}
    send('error',{message:error.message||'开发候选诊断失败',workerResetRequired:true});
  }finally{busy=false;}
};
postMessage(bootError?{type:'boot-error',message:bootError}:{type:'ready',purpose:'candidate-engineering-validation'});
