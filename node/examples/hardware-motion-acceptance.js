import {fileURLToPath} from 'node:url';
import {RS4Mini} from '../src/index.js';import fs from 'node:fs';
// Explicit real-device runner: never imported by default tests or CI.
if(process.argv.includes('--help')){console.log('Requires RS4MINI_DEVICE_ID and explicit session authorization. See docs/HARDWARE_FULL_ACCEPTANCE.md.');process.exit(0);}
if(!process.env.RS4MINI_DEVICE_ID)throw Error('Explicit RS4MINI_DEVICE_ID required');
if(process.env.RS4MINI_ALLOW_SMALL_MOTION!=='yes')throw Error('Explicit low-speed small-motion authorization required');
fs.mkdirSync(new URL('../captures/',import.meta.url),{recursive:true});

const sleep=ms=>new Promise(r=>setTimeout(r,ms)),root=fileURLToPath(new URL('../captures',import.meta.url)),file=root+'/full-motion-'+Date.now()+'.jsonl';
const id=process.env.RS4MINI_DEVICE_ID.replaceAll('-','').toLowerCase(),g=new RS4Mini({deviceId:id});let base,guardTrip;
const opt={toleranceDeg:.5,timeoutMs:10000,telemetryTimeoutMs:2500,minSpeed:.015,maxSpeed:.04,gain:.015};
function save(type,data){fs.appendFileSync(file,JSON.stringify({at:Date.now(),type,data})+'\n');}
const diff=(a,b)=>(a-b+540)%360-180;
g.onTelemetry=s=>{save('telemetry',s);if(base&&s.jointAngles&&['yaw','pitch','roll'].some(k=>Math.abs(diff(s.jointAngles[k],base[k]))>5)){guardTrip=true;void g.stop().catch(e=>save('guardError',e.message));}};
g.onReconnect=x=>save('reconnect',x);g.onError=e=>save('error',{code:e.code,message:e.message});
async function test(name,fn){if(guardTrip)throw Error('Displacement guard tripped');try{const r=await fn();save(name,{ok:true,result:r});console.log('PASS',name);return r;}catch(e){process.exitCode=1;save(name,{ok:false,code:e.code,message:e.message});console.log('FAIL',name,e.code,e.message);if(guardTrip||!g.connected)throw e;return null;}}
async function current(){return g.getJointAngles({fresh:true,timeoutMs:3000});}
async function back(){await g.moveTo({...opt,pan:base.yaw,tilt:base.pitch,roll:base.roll});await sleep(1200);return current();}
async function expectedCode(p,code){const r=await p.then(()=>({success:true}),e=>({code:e.code,message:e.message}));if(r.code!==code)throw Error(JSON.stringify(r)+' expected '+code);return r;}
try{
 await g.connect({timeoutMs:15000,directConnectTimeoutMs:8000});base=await current();save('base',base);
 await test('getAttitude.fresh',()=>g.getAttitude({fresh:true,timeoutMs:3000}));
 await test('getOrientation.explicit-wxyz',()=>g.getOrientation({componentOrder:'wxyz',fresh:true}));
 await test('getOrientation.explicit-xyzw-conjugate',()=>g.getOrientation({componentOrder:'xyzw',conjugate:true}));
 await test('setVelocity-and-stop',async()=>{await g.setVelocity({pan:.025});await sleep(350);await g.stop();await sleep(1200);const r=await current();await back();return r;});
 await test('setVelocityDeg-and-stop',async()=>{await g.setVelocityDeg({pan:.8});await sleep(350);await g.stop();await sleep(1200);const r=await current();await back();return r;});
 await test('moveFor.complete',async()=>{await g.moveFor({pan:.025,durationMs:400});await sleep(1200);const r=await current();await back();return r;});
 await test('moveFor.running-cancel',async()=>{const p=expectedCode(g.moveFor({pan:.025,durationMs:1500}),'RS4MINI_MOVE_CANCELLED');await sleep(350);await g.stop();const r=await p;await sleep(1300);const before=await current();await g.moveFor({pan:-.025,durationMs:300});await sleep(1200);const after=await current();await back();return {r,before,after};});
 await test('moveTo.running-cancel',async()=>{let requested=false;const p=expectedCode(g.moveTo({...opt,pan:base.yaw+3}),'RS4MINI_MOVE_CANCELLED');for(let n=0;n<40;n++){if(Math.abs(g.velocity.pan)>0){requested=true;break;}await sleep(50);}if(!requested){await g.stop();await p;throw Error('No nonzero velocity observed before cancellation');}await sleep(350);await g.stop();const result=await p;await sleep(1500);const stopped=await current();await back();return{result,stopped,nonzeroVelocityObserved:true};});
 await test('moveTo.total-timeout',async()=>{const r=await expectedCode(g.moveTo({...opt,pan:base.yaw+3,timeoutMs:50}),'RS4MINI_MOVE_TIMEOUT');await back();return r;});
 await test('moveTo.telemetry-timeout',async()=>{await current();const r=await expectedCode(g.moveTo({...opt,pan:base.yaw+3,telemetryTimeoutMs:20}),'RS4MINI_TELEMETRY_TIMEOUT');await back();return r;});
 await test('moveTo.two-axes-small',async()=>{const arrived=await g.moveTo({...opt,pan:base.yaw+2,tilt:base.pitch+1.5});await sleep(1800);const settled=await current();await back();return{arrived,settled};});
 await test('captureHome-moveHome-pan',async()=>{await back();await g.captureHome({fresh:true});await g.moveTo({...opt,pan:base.yaw+2});const r=await g.moveHome({...opt,axes:['pan']});await sleep(1500);return{r,settled:await current()};});
 await test('runTrajectory.complete',async()=>{const r=await g.runTrajectory([{timeMs:0,pan:.02},{timeMs:400,pan:0}],{interpolation:'linear'});await sleep(1200);await back();return r;});
 await test('runTrajectory.cancel',async()=>{const p=expectedCode(g.runTrajectory([{timeMs:0,pan:.02},{timeMs:1500,pan:.02}]),'RS4MINI_MOVE_CANCELLED');await sleep(350);await g.stop();const r=await p;await back();return r;});
 await test('moveThrough.complete',async()=>{const r=await g.moveThrough([{pan:base.yaw+1.5,holdMs:200},{pan:base.yaw,holdMs:200}],opt);await sleep(1200);return{r,settled:await current()};});
 await test('moveThrough.hold-cancel',async()=>{const here=await current(),p=expectedCode(g.moveThrough([{pan:here.yaw,holdMs:2500},{pan:here.yaw+2}],opt),'RS4MINI_MOVE_CANCELLED');await sleep(1400);await g.stop();const r=await p;await sleep(1500);const stopped=await current();await back();return{r,stopped};});
 await test('moveTo.roll-lower-speed-settling',async()=>{const before=await current(),target=before.roll+2,arrived=await g.moveTo({...opt,roll:target,minSpeed:.01,maxSpeed:.025,gain:.012});await sleep(2000);const settled=await current();const error=settled.roll-target;await g.moveTo({...opt,roll:before.roll,minSpeed:.01,maxSpeed:.025,gain:.012});await sleep(2000);const returned=await current();if(Math.abs(error)>.5)throw Error('settled roll error='+error);return{before,target,arrived,settled,error,returned};});
 await test('disconnect-reconnect',async()=>{let closeError;try{await g.disconnect();}catch(e){closeError=e.message;}await g.connect({timeoutMs:15000,directConnectTimeoutMs:8000});return{closeError,velocity:g.velocity,joints:await current()};});
 await test('autoReconnect-link-drop',async()=>{g.enableAutoReconnect({maxAttempts:3,initialDelayMs:250,maxDelayMs:1000,timeoutMs:12000,directConnectTimeoutMs:8000});await g.peripheral.disconnectAsync();for(let i=0;i<300;i++){await sleep(100);if(g.connected&&g.reconnectState.state==='restored')break;}if(!g.connected)throw Error('Auto reconnect did not restore');const result={state:g.reconnectState,velocity:g.velocity,joints:await current()};await g.disableAutoReconnect();return result;});
 save('decoder',{invalidFrames:g.decoder.invalidFrames,discardedBytes:g.decoder.discardedBytes});
}catch(e){save('sessionError',{code:e.code,message:e.message});console.log('SESSION_ERROR',e.message);process.exitCode=1;}
finally{try{await g.close();save('close',{ok:true});}catch(e){process.exitCode=1;save('close',{ok:false,message:e.message,connected:g.connected,closed:g.closed});console.log('CLOSE_ERROR',e.message);}console.log('LOG',file);}
