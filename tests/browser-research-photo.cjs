'use strict';
/* Actual Chrome harness, following browser-preprocessing.cjs. A reviewed plan
 * is mandatory; preflight never opens the encoded file. --execute performs
 * one complete encoded-file read/hash and serves that in-memory Buffer once.
 * No models, app startup, protected source, training, or remote requests. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),http=require('node:http');
const WEB=path.resolve(__dirname,'..'),hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const P='research/shikuang-research-native-roi-q16-torchf32-v1/';
const scripts=['compat.js','core.js','research-input.js',P+'encoded-header.js','research-photo.js','inference.js'];
const allowed=new Set([...scripts,...require('../tools/research-input-contract.cjs').ASSETS]);
const readJSON=p=>JSON.parse(fs.readFileSync(p,'utf8'));
async function main(){
  const planPath=path.resolve(process.argv[2]||'');if(!process.argv[2])throw Error('Expected reviewed exact-source plan.json');
  const plan=readJSON(planPath),execute=process.argv.includes('--execute');
  if(plan.schema!=='research-native-photo-chrome-exact1-v1'||plan.fixedSourceIDs?.length!==1||plan.fixedSourceIDs[0]!==plan.source.id||plan.originalFullReads!==1||plan.originalServes!==1||plan.explicitChromeDecodes!==1||plan.wallSeconds!==90||plan.totalOutputBytes!==128*1048576||plan.photoNominalMemoryBytes!==512*1048576||plan.snapshotNominalMemoryBytes!==768*1048576||plan.modelForwards!==0||plan.modelWeightReads!==0||plan.remoteRequests!==0)throw Error('Plan is outside reviewed exact-one-photo limits');
  if(!/^[a-f0-9]{64}$/.test(plan.source.sha256)||!Number.isSafeInteger(plan.source.bytes)||plan.source.bytes<12||plan.source.bytes>20*1048576||plan.source.path!==path.resolve(plan.source.path))throw Error('Invalid encoded source pin');
  const st=fs.lstatSync(plan.source.path);if(!st.isFile()||st.isSymbolicLink()||st.size!==plan.source.bytes||fs.realpathSync(plan.source.path)!==plan.source.path)throw Error('Original stat/pin mismatch');
  const nominal=plan.source.width*plan.source.height*16+2097152+plan.source.bytes;
  if(nominal>plan.photoNominalMemoryBytes||nominal+plan.source.width*plan.source.height*12>plan.snapshotNominalMemoryBytes)throw Error('Native photo/snapshot nominal reservation exceeds approved limits');
  const staticFiles=new Map([...allowed].map(name=>[name,fs.readFileSync(path.join(WEB,name))]));
  const sourcePins=[...staticFiles].map(([name,b])=>({name,bytes:b.length,sha256:hash(b)}));
  const harnessBytes=fs.readFileSync(__filename),chromeBin=process.env.CHROME_BIN||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const preflight={harnessPin:{path:__filename,bytes:harnessBytes.length,sha256:hash(harnessBytes)},chromeBin,planSHA256:hash(fs.readFileSync(planPath)),fixedSourceIDs:plan.fixedSourceIDs,originalStatOnly:true,originalFullReads:0,originalServes:0,explicitChromeDecodes:0,nominalPhotoReservationBytes:nominal,nominalSnapshotReservationBytes:nominal+plan.source.width*plan.source.height*12,sourcePins};
  if(!execute){console.log(JSON.stringify(preflight,null,2));return;}
  if(plan.authorizedByRoot!==true)throw Error('Reviewed plan must record exact Root authorization');
  const out=path.resolve(path.dirname(planPath),plan.outputDirectory);fs.mkdirSync(out); // exclusive; failures remain intact
  const summary={status:'started',...preflight,sourceKind:plan.source.kind||'root-approved-own-source',sourceAdmission:plan.sourceAdmission,startedAt:new Date().toISOString(),originalStatOnly:false,originalReadAttempts:0,originalServeAttempts:0,explicitChromeDecodes:null,browserLaunched:false,browserInstrumentationObserved:false,modelWeightReads:0,modelForwards:0,remoteRequests:0,deniedRequests:[],serverRequests:[],physicalDevice:false,decoderCrossPlatformParity:false};
  let written=0,original=null,browser=null,page=null,server=null,origin,timer,expired=false;
  const began=Date.now(),deadline=began+plan.wallSeconds*1000;
  const guard=()=>{if(expired||Date.now()>=deadline)throw Error('90s overall harness deadline');};
  const write=(name,value)=>{const b=Buffer.from(JSON.stringify(value,null,2)+'\n');if(written+b.length>plan.totalOutputBytes)throw Error('128MiB total output cap');fs.writeFileSync(path.join(out,name),b,{flag:'wx'});written+=b.length;};
  try{
    guard();summary.originalReadAttempts++;
    original=fs.readFileSync(plan.source.path); // sole encoded source body open/read/hash
    summary.originalFullReads++;
    if(original.length!==plan.source.bytes||hash(original)!==plan.source.sha256)throw Error('Original first-buffer size/SHA256 mismatch');
    summary.originalFirstBufferVerified=true;
    server=http.createServer((req,res)=>{
      try{
        guard();if(req.method!=='GET'||req.headers.host!==new URL(origin).host)throw Error('Only exact loopback GET is allowed');
        const name=new URL(req.url,origin).pathname.slice(1);summary.serverRequests.push(name);
        if(name===''){res.setHeader('Content-Type','text/html; charset=utf-8');return res.end('<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,">'+scripts.map(s=>'<script src="/'+s+'"></script>').join(''));}
        if(name==='approved-source'){
          if(summary.originalServeAttempts!==0)throw Error('Encoded source may be served only once from the validated in-memory Buffer');
          summary.originalServeAttempts++;res.once('finish',()=>summary.originalServes++);res.setHeader('Content-Type',plan.source.mime);res.setHeader('Content-Length',original.length);return res.end(original);
        }
        if(!allowed.has(name))throw Error('Resource not allowlisted');
        res.setHeader('Content-Type',name.endsWith('.js')?'application/javascript':'application/octet-stream');res.end(staticFiles.get(name));
      }catch(e){summary.deniedRequests.push({url:req.url,message:e.message});res.writeHead(403);res.end('not allowed');}
    });
    await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});origin='http://127.0.0.1:'+server.address().port;
    timer=setTimeout(()=>{expired=true;void browser?.close().catch(()=>{});server?.closeAllConnections();server?.close();},Math.max(1,deadline-Date.now()));
    const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');guard();
    browser=await chromium.launch({headless:true,executablePath:chromeBin,args:['--disable-background-networking'],timeout:Math.max(1,Math.min(30000,deadline-Date.now()))});
    summary.browserLaunched=true;
    guard();
    summary.browser={version:browser.version(),headless:true,engine:'actual Chrome process, not Node VM'};
    page=await browser.newPage();guard();await page.route('**/*',route=>{const url=route.request().url();if(new URL(url).origin===origin)return route.continue();summary.remoteRequests++;return route.abort();});
    await page.goto(origin+'/',{timeout:Math.max(1,Math.min(30000,deadline-Date.now()))});await page.waitForFunction(()=>!!window.MineralEngine?.prepareResearchPhoto);
    summary.explicitChromeDecodes=null;
    const result=await page.evaluate(async({plan,remaining})=>{
      const digest=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
      const events=window.__ResearchPhotoEvents={explicitChromeDecodes:0,nativeCanvases:[],draws:[],workers:[],posts:[],terminations:0};
      const nativeDecode=HTMLImageElement.prototype.decode;
      HTMLImageElement.prototype.decode=function(...args){events.explicitChromeDecodes++;if(events.explicitChromeDecodes>1)throw Error('More than one explicit source decode');return nativeDecode.apply(this,args);};
      let nativeHashPromise;
      const getContext=HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext=function(...args){
        const c=getContext.apply(this,args);if(!c||args[0]!=='2d')return c;
        const draw=c.drawImage.bind(c),pixels=c.getImageData.bind(c);
        c.drawImage=(image,...geometry)=>{events.draws.push({geometry,source:[image.naturalWidth,image.naturalHeight],canvas:[this.width,this.height]});return draw(image,...geometry);};
        c.getImageData=(...geometry)=>{const p=pixels(...geometry);events.nativeCanvases.push({geometry,bytes:p.data.byteLength,colorSpace:p.colorSpace});nativeHashPromise=digest(p.data);return p;};return c;
      };
      const NativeWorker=window.Worker;
      window.Worker=class extends NativeWorker{
        constructor(url){super(url);events.workers.push(String(url));}
        postMessage(data,transfer){const record={type:data.type,nativeDimensions:[data.frame?.width,data.frame?.height],sourceBytes:data.frame?.rgba.byteLength,transferBytes:transfer?.map(b=>b.byteLength)};events.posts.push(record);super.postMessage(data,transfer);record.sourceBytesAfterTransfer=data.frame.rgba.byteLength;}
        terminate(){events.terminations++;return super.terminate();}
      };
      const response=await fetch('/approved-source',{cache:'no-store'});if(!response.ok)throw Error('approved cache serve failed');const encodedPhoto=await response.blob();if(encodedPhoto.size!==plan.source.bytes)throw Error('approved cached response body size mismatch');
      const options={profileId:ShikuangResearchInput.PROFILE_ID,profileVersion:1,transferOwnership:true,encodedPhoto,route:'photo-file',normalizedROI:plan.source.normalizedROI,limits:{inputMemoryBudgetBytes:plan.photoNominalMemoryBytes,maxNativePixels:40e6},timeoutMs:Math.max(1,remaining)};
      const pending=MineralEngine.prepareResearchPhoto(options);
      let busyRejected=false;try{await MineralEngine.analyze([{src:'never-decoded'}]);}catch(e){busyRejected=/已有分析/.test(e.message);}
      const output=await pending;
      const hashes={inputRGBA:await nativeHashPromise,rgb224:await digest(output.rgb224),tensorFloat32LE:await digest(output.tensorFloat32LE),runtimeTensor:await digest(output.runtimeTensor)};
      let productionRejected=false;try{await MineralEngine.prepare({profileId:options.profileId});}catch(e){productionRejected=/schema1/.test(e.message);}
      return {hashes,events,busyRejected,productionRejected,configuration:MineralEngine.configuration,manifestCacheState:MineralEngine.manifestCacheState,sourceHeader:output.sourceHeader,decodeStage:output.decodeStage,decoderEvidence:output.decoderEvidence,nativeROI:output.nativeROI,normalizedROI:output.normalizedROI,geometry:output.geometry,memoryLedger:output.memoryLedger,reservation:output.reservation,priorResizeCount:output.priorResizeCount,jpegRoundTripsCreated:output.jpegRoundTripsCreated,profileId:output.profileId,normId:output.normId,algorithmVersion:output.algorithmVersion,modelForwards:output.modelForwards,modelRegistered:output.modelRegistered,productionRegistration:output.productionRegistration,runtimeTensorByteLength:output.runtimeTensor.byteLength,userAgent:navigator.userAgent};
    },{plan,remaining:Math.max(1,deadline-Date.now())});
    summary.browserResult=result;summary.explicitChromeDecodes=result.events.explicitChromeDecodes;summary.browserInstrumentationObserved=true;guard();
    const expected=plan.source.expected;
    const checks={
      sourceReadExactlyOnce:summary.originalFullReads===1,sourceServedExactlyOnce:summary.originalServes===1,decodeExactlyOnce:summary.explicitChromeDecodes===1,
      nativeRGBA:result.hashes.inputRGBA===expected.inputRGBA,rgb224:result.hashes.rgb224===expected.rgb224,tensor:result.hashes.tensorFloat32LE===expected.tensorFloat32LE,runtimeTensor:result.hashes.runtimeTensor===expected.tensorFloat32LE,
      nativeDimensions:result.sourceHeader.width===plan.source.width&&result.sourceHeader.height===plan.source.height,
      exactNativeCanvas:result.events.draws.length===1&&JSON.stringify(result.events.draws[0].geometry)===JSON.stringify([0,0,plan.source.width,plan.source.height]),
      nativeTransfer:result.events.posts.length===1&&result.events.posts[0].sourceBytes===plan.source.width*plan.source.height*4&&result.events.posts[0].sourceBytesAfterTransfer===0,
      workerDedicated:result.events.workers.length===1&&new URL(result.events.workers[0]).pathname.endsWith('/'+P+'worker.js')&&result.events.terminations===1,
      nativeROI:['x0','y0','x1','y1'].every(k=>result.nativeROI[k]===plan.source.nativeROI[k]),noPriorResize:result.priorResizeCount===0&&result.jpegRoundTripsCreated===0,
      encodedHeader:result.sourceHeader.exifOrientation===1&&result.sourceHeader.profilePresent===plan.source.ICCProfilePresent&&/default1/.test(result.sourceHeader.orientationEvidence),
      productionUnprepared:result.configuration===null&&result.manifestCacheState==='unprepared',productionRejected:result.productionRejected,busyRejected:result.busyRejected,
      noModel:result.modelForwards===0&&result.modelRegistered===false&&result.productionRegistration===false,noRemoteRequests:summary.remoteRequests===0,noDeniedRequests:summary.deniedRequests.length===0
    };
    summary.checks=checks;if(Object.values(checks).some(v=>v!==true))throw Error('Actual Chrome check failed: '+Object.entries(checks).filter(([,v])=>!v).map(([k])=>k).join(','));
    summary.status='passed';
  }catch(error){summary.status='failed';summary.error={message:error.message,stack:error.stack};try{const observed=await page?.evaluate(()=>window.__ResearchPhotoEvents||null);if(observed){summary.failureBrowserEvents=observed;summary.explicitChromeDecodes=observed.explicitChromeDecodes;summary.browserInstrumentationObserved=true;}}catch(_){}process.exitCode=1;}
  finally{
    clearTimeout(timer);await browser?.close().catch(()=>{});server?.closeAllConnections();await new Promise(resolve=>server?server.close(resolve):resolve());original=null;
    summary.decodeCountQualification=summary.browserInstrumentationObserved?'actual observed browser instrumentation':summary.browserLaunched?'unknown; browser instrumentation was not read back':'browser not launched; no source decode was started';
    summary.elapsedSeconds=(Date.now()-began)/1000;summary.finishedAt=new Date().toISOString();summary.outputBytesBeforeSummary=written;write('summary.json',summary);console.log(JSON.stringify({status:summary.status,output:path.join(out,'summary.json'),elapsedSeconds:summary.elapsedSeconds,originalReadAttempts:summary.originalReadAttempts,originalFullReads:summary.originalFullReads,originalServeAttempts:summary.originalServeAttempts,originalServes:summary.originalServes,explicitChromeDecodes:summary.explicitChromeDecodes}));
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
