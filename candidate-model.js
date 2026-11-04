/* Explicit engineering candidate contract. It never changes schema1 or loads a model. */
(function(root,factory){
  const api=factory();
  const commonJS=typeof module==='object'&&module&&module.exports;
  if(commonJS)module.exports=api;
  if(typeof window==='object'&&window||!commonJS)root.ShikuangCandidateModel=api;
})(typeof window==='object'&&window?window:typeof globalThis==='object'?globalThis:this,function(){
  'use strict';
  const LABELS=Object.freeze(["ima-graphite","ima-gold","ima-silver","ima-stibnite","ima-copper","ima-sulphur","ima-hematite","ima-cassiterite","ima-microcline","ima-quartz","ima-bournonite","ima-pyrargyrite","ima-marcasite","ima-arsenopyrite","ima-cobaltite","ima-arsenic","ima-pyrite","ima-chromite","ima-opal","ima-bismuth","ima-magnetite","ima-chrysoberyl","ima-topaz","ima-cinnabar","ima-beryl","ima-gypsum","ima-proustite","ima-spodumene","ima-augite","ima-spinel","ima-andalusite","ima-pollucite","ima-cuprite","ima-hedenbergite","ima-ilmenite","ima-actinolite","ima-diopside","ima-tremolite","ima-albite","ima-rutile","ima-zircon","ima-corundum","ima-celestine","ima-malachite","ima-sphalerite","ima-wollastonite","ima-rhodonite","ima-fluorite","ima-orthoclase","ima-aragonite","ima-dolomite","ima-pectolite","ima-grossular","ima-kyanite","ima-cancrinite","ima-andradite","ima-almandine","ima-baryte","ima-galena","ima-muscovite","ima-calcite","ima-aegirine","ima-eudialyte","ima-azurite","ima-goethite","ima-epidote","ima-scheelite","ima-vesuvianite","ima-chalcopyrite","ima-analcime","ima-natrolite","ima-molybdenite","ima-pyrrhotite","ima-prehnite","ima-siderite","ima-creedite","ima-vivianite","ima-titanite","ima-elbaite","ima-fluorapatite","ima-diamond","ima-lazurite","ima-phlogopite","ima-rhodochrosite","ima-smithsonite","ima-clinochlore","ima-halite"]);
  const PROFILE=Object.freeze({profileId:'shikuang-research-native-roi-q16-torchf32-v1',profileVersion:1,inputContract:'shikuang-native-roi-q16-rgba8-torchf32-001',normId:'imagenet-rgb-stepwise-f32-div-sub-div-001',geometryAlgorithm:'shikuang-private-full-aspect-virtual-rgba8-q16-v3-003',shape:Object.freeze([1,3,224,224]),dtype:'float32',encoding:'float32-le'});
  const LABEL_ORDER_SHA256='c167fa68e1019852a93d7b304237baf5ebe3e7ed4d0eb5a50b4e4dc1214c67bc';
  const PURPOSE='candidate-engineering-validation',GATE_PROFILE='schema1-center-square-bilinear-final-f32-v1';
  const MODEL_MAX_BYTES=128*1048576,INPUT_ELEMENTS=3*224*224;
  const MAP=Object.freeze(LABELS.map((id,index)=>Object.freeze({index,label:id,catalogId:id})));
  const hash=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
  const fail=message=>{throw new Error('候选模型契约不匹配：'+message);};
  function exactKeys(value,keys){return value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join('|')===[...keys].sort().join('|');}
  function same(a,b){
    if(Array.isArray(a)||Array.isArray(b))return Array.isArray(a)&&Array.isArray(b)&&a.length===b.length&&a.every((x,i)=>same(x,b[i]));
    if(a&&b&&typeof a==='object'&&typeof b==='object')return exactKeys(a,Object.keys(b))&&Object.keys(b).every(k=>same(a[k],b[k]));
    return a===b;
  }
  function identity(model){return {id:model.id,role:model.role,path:model.path,bytes:model.bytes,sha256:model.sha256,classes:model.classes,inputName:model.inputName,outputName:model.outputName,output:model.output};}
  function validateManifest(value,legacy,legacyHash){
    if(!exactKeys(value,['schemaVersion','version','purpose','productionRegistered','independentAcceptance','inputProfile','labelOrderSha256','labels','catalogMap','classifier','gate','policy']))fail('字段');
    if(value.schemaVersion!==2||value.purpose!==PURPOSE||value.productionRegistered!==false||value.independentAcceptance!==false||typeof value.version!=='string'||!/^[A-Za-z0-9._-]{1,80}$/.test(value.version))fail('版本或诊断用途');
    if(!same(value.inputProfile,PROFILE)||value.labelOrderSha256!==LABEL_ORDER_SHA256||!same(value.labels,LABELS)||!same(value.catalogMap,MAP))fail('预处理或科学87类序/目录ID');
    const m=value.classifier;
    if(!exactKeys(m,['id','role','path','bytes','sha256','classes','inputName','outputName','output','backbone','descriptor','fold','selectedEpoch','provenance']))fail('分类器字段');
    if(!hash(m.sha256)||m.path!=='models/candidates/'+m.sha256+'.onnx'||!Number.isSafeInteger(m.bytes)||m.bytes<1||m.bytes>MODEL_MAX_BYTES||m.classes!==87||m.role!=='mineral-classifier'||m.backbone!=='dinov2_vits14'||m.descriptor!=='CLS384'||m.inputName!=='input'||m.outputName!=='logits'||m.output!=='logits'||![0,1].includes(m.fold)||!Number.isInteger(m.selectedEpoch)||m.selectedEpoch<1||m.selectedEpoch>24||m.id!=='dinov2-s14-capture24-fold'+m.fold)fail('绑定的DINO artifact');
    const proof=m.provenance;
    if(!exactKeys(proof,['trainingPlanSha256','trainingCompletionSha256','selectedLockSha256','selectedDeltaSha256','officialBaseSha256','captureKernelSha256','exporterSha256','exportCompletionSha256','condition','trainingPhotos','selectionRule','independentKappa']))fail('导出出处字段');
    for(const k of ['trainingPlanSha256','trainingCompletionSha256','selectedLockSha256','selectedDeltaSha256','captureKernelSha256','exporterSha256','exportCompletionSha256'])if(!hash(proof[k]))fail('导出出处SHA');
    if(proof.officialBaseSha256!=='b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9'||proof.condition!=='capture24'||!Number.isSafeInteger(proof.trainingPhotos)||proof.trainingPhotos<87||proof.selectionRule!=='min_full87_group_mean_CE_tie_earliest_at_declared_condition_horizon'||proof.independentKappa!==null)fail('训练选择或未验收状态');
    if(!legacy||!hash(legacyHash)||!exactKeys(value.gate,['legacyManifestSha256','inputProfile','model'])||value.gate.legacyManifestSha256!==legacyHash||value.gate.inputProfile!==GATE_PROFILE)fail('独立legacy gate预处理');
    const gate=legacy.models?.find(row=>row.role==='input-gate');
    if(!gate||!same(value.gate.model,identity(gate)))fail('旧gate身份');
    if(!same(value.policy,{modelSelection:'explicit-single-fold',output:'raw87-per-photo-diagnostic',calibrated:false,unknownRejectionValidated:false,independentKappa:null}))fail('禁止旧阈值或隐式ensemble');
    return Object.freeze({...value,inputProfile:PROFILE,labels:LABELS,catalogMap:MAP,classifier:Object.freeze({...m,provenance:Object.freeze({...proof})}),gate:Object.freeze({legacyManifestSha256:legacyHash,inputProfile:GATE_PROFILE,model:Object.freeze(identity(gate))}),policy:Object.freeze({...value.policy})});
  }
  function createManifest(options,legacy,legacyHash){
    return validateManifest({schemaVersion:2,version:options.version,purpose:PURPOSE,productionRegistered:false,independentAcceptance:false,inputProfile:PROFILE,labelOrderSha256:LABEL_ORDER_SHA256,labels:LABELS,catalogMap:MAP,classifier:options.classifier,gate:{legacyManifestSha256:legacyHash,inputProfile:GATE_PROFILE,model:identity(legacy.models.find(row=>row.role==='input-gate'))},policy:{modelSelection:'explicit-single-fold',output:'raw87-per-photo-diagnostic',calibrated:false,unknownRejectionValidated:false,independentKappa:null}},legacy,legacyHash);
  }
  function manifestURL(value,base){
    if(typeof value!=='string')fail('需显式清单URL');const origin=new URL('./',base),url=new URL(value,origin);
    const prefix=origin.pathname+'research/candidates/';
    if(!['http:','https:'].includes(url.protocol)||url.origin!==origin.origin||url.username||url.password||url.hash||url.search||!url.pathname.startsWith(prefix)||!/^[A-Za-z0-9_.-]+\.json$/.test(url.pathname.slice(prefix.length)))fail('清单须来自本App候选目录');
    return url;
  }
  function modelURL(model,manifestHash,base,candidateManifestURL,legacyManifestHash){
    if(!hash(manifestHash)||!hash(model?.sha256)||model.path!=='models/candidates/'+model.sha256+'.onnx')fail('候选artifact资源身份');
    if(!hash(legacyManifestHash))fail('候选gate清单身份');const selected=manifestURL(candidateManifestURL,base);
    const url=new URL(model.path,new URL('./',base));url.searchParams.set('manifest',manifestHash);url.searchParams.set('model',model.sha256);url.searchParams.set('candidate',selected.href);url.searchParams.set('legacy',legacyManifestHash);return url;
  }
  function validInput(value){return value instanceof Float32Array&&value.buffer instanceof ArrayBuffer&&value.buffer.resizable!==true&&value.length===INPUT_ELEMENTS&&!value.some(x=>!Number.isFinite(x));}
  function validateInputs(inputs,gates){
    if(!Array.isArray(inputs)||inputs.length<1||inputs.length>3||!Array.isArray(gates)||gates.length!==inputs.length||inputs.some(x=>!validInput(x))||gates.some(x=>!validInput(x)))fail('双路图像张量');
    if(new Set([...inputs,...gates].map(x=>x.buffer)).size!==inputs.length+gates.length)fail('gate与研究张量不得共用缓冲区');
  }
  function validateResult(result,manifest,manifestHash,photoCount){
    if(!result||result.type!=='result'||result.purpose!==PURPOSE||result.productionRegistered!==false||result.independentAcceptance!==false||result.manifestSha256!==manifestHash||result.modelVersion!==manifest.version||result.classifierId!==manifest.classifier.id||result.profileId!==PROFILE.profileId||!same(result.labels,LABELS)||!Array.isArray(result.runs)||!Array.isArray(result.screening)||result.runs.length!==photoCount||result.screening.length!==photoCount)fail('推理结果身份或完成状态');
    for(let i=0;i<photoCount;i++){
      const r=result.runs[i],s=result.screening[i];
      if(!r||r.photo!==i||r.model!==manifest.classifier.id||!Array.isArray(r.values)||r.values.length!==87||r.values.some(x=>!Number.isFinite(x))||!s||s.photo!==i||!Array.isArray(s.values)||s.values.length!==1000||s.values.some(x=>!Number.isFinite(x)))fail('完整逐图输出');
    }
    return result;
  }
  function diagnostics(result,manifest){
    return {...result,catalogMap:MAP,rankings:result.runs.map(run=>({photo:run.photo,candidates:LABELS.map((id,index)=>({catalogId:id,label:id,index,logit:run.values[index]})).sort((a,b)=>b.logit-a.logit||a.index-b.index).slice(0,5)})),status:'diagnostic',confidenceCalibrated:false,unknownRejectionValidated:false,independentKappa:null,engine:'onnx-candidate-worker-wasm',warnings:['开发候选模型，仅供受控验证；尚未完成独立识别验收，原始logit不是准确率。'],selectedFold:manifest.classifier.fold};
  }
  return Object.freeze({LABELS,PROFILE,LABEL_ORDER_SHA256,CATALOG_MAP:MAP,PURPOSE,GATE_PROFILE,MODEL_MAX_BYTES,identity,validateManifest,createManifest,manifestURL,modelURL,validateInputs,validateResult,diagnostics});
});
