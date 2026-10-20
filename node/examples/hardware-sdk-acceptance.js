import {fileURLToPath} from 'node:url';
import {RS4Mini} from '../src/index.js';import fs from 'node:fs';
// Explicit real-device runner: never imported by default tests or CI.
if(process.argv.includes('--help')){console.log('Requires RS4MINI_DEVICE_ID and explicit session authorization. See docs/HARDWARE_FULL_ACCEPTANCE.md.');process.exit(0);}
if(!process.env.RS4MINI_DEVICE_ID)throw Error('Explicit RS4MINI_DEVICE_ID required');
if(!['queries'].includes(process.argv[2])&&process.env.RS4MINI_ALLOW_MAINTENANCE!=='yes')throw Error('Explicit approval for selected maintenance case required');
fs.mkdirSync(new URL('../captures/',import.meta.url),{recursive:true});

const action=process.argv[2];if(!['settings','autotune','component','queries','recenter'].includes(action))throw Error('Explicit named case required');
const id=process.env.RS4MINI_DEVICE_ID.replaceAll('-','').toLowerCase(),g=new RS4Mini({deviceId:id}),a=g.appCommands,t={timeoutMs:5000},file=fileURLToPath(new URL('../captures/full-',import.meta.url))+action+'-'+Date.now()+'.jsonl';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));let counts={},jointSamples=[];
function save(type,data){fs.appendFileSync(file,JSON.stringify({at:Date.now(),type,data})+'\n');}
g.onMessage=x=>save('raw',x);g.onTelemetry=x=>{save('telemetry',x);if(x.jointAngles)jointSamples.push(x.jointAngles);};g.onAppStatus=x=>{counts[x.kind]=(counts[x.kind]||0)+1;save('status',x);};
async function task(name,fn){try{const r=await fn();save(name,{ok:true,result:r});console.log('CALL_OK',name,JSON.stringify({statusCode:r?.statusCode,rawValue:r?.rawValue,calibration:r?.calibration,balance:r?.balance,systemCalibration:r?.systemCalibration,requestedEnabled:r?.requestedEnabled}));return r;}catch(e){process.exitCode=1;save(name,{ok:false,code:e.code,message:e.message});console.log('FAIL',name,e.code,e.message);return null;}}
async function observe(seconds){for(let i=0;i<seconds;i++){await sleep(1000);if((i+1)%10===0)console.log('OBSERVE',i+1,JSON.stringify(counts));}save('observation',{seconds,counts,joints:jointSamples.slice(-5)});}
try{
 await g.connect({timeoutMs:15000,directConnectTimeoutMs:8000});a.useProfile('ronin-2.2.2');console.log('CONNECTED',action);save('motorBefore',await a.getMotorSettings(t));
 if(action==='settings'){
  save('standaloneBefore',await a.getStandaloneTuning(t));await task('setStandaloneTuning.input2.pitch.speed50',()=>a.setStandaloneTuning({...t,inputSource:2,axis:'pitch',parameter:'speed',value:50}));await task('standalone.readback',()=>a.getStandaloneTuning(t));
  for(const axis of ['pitch','roll'])await task('fine.'+axis+'.0',()=>a.sendFineTuneRequest({...t,axis,adjustmentDegrees:0}));await observe(5);
 }else if(action==='autotune'){
  await task('sendAutoTuneRequest.start',()=>a.sendAutoTuneRequest({start:true}));await observe(30);
  await task('sendAutoTuneRequest.stop',()=>a.sendAutoTuneRequest({start:false}));await observe(10);
 }else if(action==='component'){
  await task('sendComponentCalibrationRequest.AUTO',()=>a.sendComponentCalibrationRequest({...t,sourcePart:'AUTO'}));await observe(60);
 }else if(action==='queries'){
  g.experimental.useProfile('rs3');for(const kind of ['version','position','controlStatus','type'])await task('experimental.query.'+kind,()=>g.experimental.query({kind,timeoutMs:3000}));a.useProfile('ronin-2.2.2');
 }else if(action==='recenter'){
  save('before',await g.getJointAngles({fresh:true}));await task('recenter',()=>g.recenter());await observe(10);save('after',await g.getJointAngles({fresh:true}));
 }
 save('decoder',{invalidFrames:g.decoder.invalidFrames,discardedBytes:g.decoder.discardedBytes});
}catch(e){save('sessionError',{code:e.code,message:e.message});console.log('SESSION_ERROR',e.code,e.message);process.exitCode=1;}
finally{try{await g.close();save('close',{ok:true});}catch(e){process.exitCode=1;save('close',{ok:false,message:e.message,connected:g.connected,closed:g.closed});console.log('CLOSE_ERROR',e.message);}console.log('LOG',file);}
