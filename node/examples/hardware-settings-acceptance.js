import {fileURLToPath} from 'node:url';
import {RS4Mini} from '../src/index.js';import fs from 'node:fs';
// Explicit real-device runner: never imported by default tests or CI.
if(process.argv.includes('--help')){console.log('Requires RS4MINI_DEVICE_ID and explicit session authorization. See docs/HARDWARE_FULL_ACCEPTANCE.md.');process.exit(0);}
if(!process.env.RS4MINI_DEVICE_ID)throw Error('Explicit RS4MINI_DEVICE_ID required');
if(process.env.RS4MINI_ALLOW_SETTINGS!=='yes')throw Error('Explicit approval for exact same-value writes and sensitivity restore required');
fs.mkdirSync(new URL('../captures/',import.meta.url),{recursive:true});

const dir=fileURLToPath(new URL('../captures',import.meta.url)),file=dir+'/full-settings-'+Date.now()+'.jsonl',id=process.env.RS4MINI_DEVICE_ID.replaceAll('-','').toLowerCase();
const g=new RS4Mini({deviceId:id}),a=g.appCommands,t={timeoutMs:3000},backup={};
function save(type,data){fs.appendFileSync(file,JSON.stringify({at:new Date().toISOString(),type,data})+'\n');}
async function test(name,fn){try{let r=await fn();save(name,{ok:true,result:r});console.log('PASS',name);return r;}catch(e){process.exitCode=1;save(name,{ok:false,code:e.code,message:e.message});console.log('FAIL',name,e.code,e.message);return null;}}
function equal(a,b){if(a!==b)throw Error('Readback mismatch: '+a+' != '+b);}
async function echo(name,read,write,key=x=>x.rawValue){const before=await read();backup[name]=before;save('backup.'+name,before);const ack=await write(before);const after=await read();equal(JSON.stringify(key(after)),JSON.stringify(key(before)));return {ack,after};}
g.onAppStatus=x=>save('status',x);g.onMessage=x=>save('raw',x);
try{
 await g.connect({timeoutMs:15000,directConnectTimeoutMs:8000});a.useProfile('ronin-2.2.2');
 await test('setFollowSensitivity.echo',()=>echo('sensitivity',()=>a.getFollowSensitivity(t),b=>a.setFollowSensitivity({...t,mode:b.mode})));
 await test('setFollowSensitivity.change-restore',async()=>{const b=await a.getFollowSensitivity(t);save('backup.sensitivity-change',b);let changed;try{await a.setFollowSensitivity({...t,mode:1-b.mode});changed=await a.getFollowSensitivity(t);equal(changed.rawValue,1-b.rawValue);}finally{await a.setFollowSensitivity({...t,mode:b.mode});equal((await a.getFollowSensitivity(t)).rawValue,b.rawValue);}return{changed,restored:true};});
 await test('setCustomFollowSettings.echo',()=>echo('customFollow',()=>a.getCustomFollowSettings(t),b=>a.setCustomFollowSettings({...t,...b.settings})));
 await test('setMotorSettings.echo',()=>echo('motorSettings',()=>a.getMotorSettings(t),b=>a.setMotorSettings({...t,...b.settings})));
 await test('sendSmoothTrackAxesRequest.echo',()=>echo('smoothTrack',()=>a.getSmoothTrackAxes(t),b=>a.sendSmoothTrackAxesRequest({...t,axes:Object.fromEntries(b.values.map(v=>[v.axis,!!v.rawValue]))}),b=>b.values.map(v=>v.rawValue)));
 await test('sendAxisModeRequest.echo',()=>echo('axisMode',()=>a.getAxisMode(t),b=>a.sendAxisModeRequest({...t,sourceMode:b.sourceMode})));
 await test('sendUserProfileRequest.echo',()=>echo('userProfile',()=>a.getUserProfile(t),b=>a.sendUserProfileRequest({...t,sourceProfileValue:b.rawValue})));
 await test('sendWorkModeRequest.echo',()=>echo('workMode',()=>a.getWorkMode(t),b=>a.sendWorkModeRequest({...t,sourceMode:b.sourceMode})));
 for(const[domain,parameters]of [['Follow',['speed','acceleration','deadZone']],['Rc',['speed','deadZone','smoothing']]])for(const parameter of parameters){await test('set'+domain+'Settings.'+parameter,()=>echo(domain+parameter,()=>a['get'+domain+'Settings']({...t,parameter}),b=>a['set'+domain+'Settings']({...t,parameter,...b.settings})));}
 for(const domain of ['Follow','Rc']){const b=await a['get'+domain+'Tuning'](t);save('backup.'+domain+'Tuning',b);backup[domain+'Tuning']=b;for(const row of b.values){await test('set'+domain+'Tuning.'+row.axis+'.'+row.parameter,async()=>{const opt={...t,axis:row.axis,parameter:row.parameter},ack=await a['set'+domain+'Tuning']({...opt,value:row.rawValue}),after=await a['get'+domain+'Tuning'](opt);equal(after.values[0].rawValue,row.rawValue);return{ack,after};});}}
 for(const parameter of ['stiffness','strength','gyroFiltering','preControl'])for(const axis of ['pitch','roll','yaw'])await test('setMotorTuning.'+axis+'.'+parameter,()=>echo('motor.'+axis+'.'+parameter,()=>a.getMotorTuning({...t,axis,parameter}),b=>a.setMotorTuning({...t,axis,parameter,value:b.values[0].rawValue}),b=>b.values[0].rawValue));
 await test('standalone.backup-only',async()=>{const b=await a.getStandaloneTuning(t);save('backup.standalone',b);return{inputSourceRaw:b.inputSourceRaw,values:b.values};});
 save('backup-complete',Object.keys(backup));
}catch(e){save('session-error',{code:e.code,message:e.message});console.log('SESSION',e.code,e.message);process.exitCode=1;}
finally{try{await g.close();save('closed',{ok:true});}catch(e){process.exitCode=1;save('closed',{ok:false,message:e.message,connected:g.connected,closed:g.closed});console.log('CLOSE_ERROR',e.message,'connected',g.connected);}console.log('LOG',file);}
