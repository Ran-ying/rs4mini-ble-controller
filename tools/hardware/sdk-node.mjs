// Explicit real-device test. Never imported by default tests or CI.
import { BleDevice } from '../../node/src/device-node.js';
if(process.argv.includes('--help')){console.log('RS4MINI_SDK_TEST=yes RS4MINI_DEVICE_ID=<local ID> node tools/hardware/sdk-node.mjs');process.exit(0);}
if(process.env.RS4MINI_SDK_TEST!=='yes'||!process.env.RS4MINI_DEVICE_ID)throw Error('Explicit SDK test opt-in and local device ID required');
const g=new BleDevice({deviceId:process.env.RS4MINI_DEVICE_ID.replaceAll('-','').toLowerCase()}),a=g.appCommands,rows=[];
async function check(name,fn){const start=Date.now();try{const v=await fn();rows.push({name,ok:true,elapsedMs:Date.now()-start,value:v});return v;}catch(e){rows.push({name,ok:false,elapsedMs:Date.now()-start,code:e.code??'ERROR'});return null;}}
const summary=r=>r&&Object.fromEntries(['readMode','atomic','rawValue','mode','sourceMode','sourceProfile','sourceWorkMode','inputSource','values','settings'].filter(k=>r[k]!==undefined).map(k=>[k,r[k]]));
try{
 await g.connect({timeoutMs:15000,directConnectTimeoutMs:8000});rows.push({name:'connect',ok:g.connected});
 rows.push({name:'deviceLayerOnly',ok:typeof g.moveTo==='undefined'});
 await check('attitude',()=>g.getAttitude({fresh:true,timeoutMs:3000}));await check('joints',()=>g.getJointAngles({fresh:true,timeoutMs:3000}));
 a.useProfile('ronin-2.2.2');
 for(const name of ['getFollowSensitivity','getMotorSettings','getCustomFollowSettings','getAxisMode','getUserProfile','getWorkMode','getSmoothTrackAxes','getFollowTuning','getRcTuning','getStandaloneTuning'])await check(name,async()=>summary(await a[name]({timeoutMs:3000})));
 if(process.env.RS4MINI_SDK_WRITEBACK==='yes'){
  const mode=rows.find(r=>r.name==='getFollowSensitivity')?.value?.rawValue;
  await check('sensitivity.sameValueWrite',async()=>{if(![0,1].includes(mode))throw Error('No valid baseline');const r=await a.setFollowSensitivity({mode,timeoutMs:3000});return{statusCode:r.statusCode,acknowledged:r.acknowledged,requestedMode:mode};});
  await check('sensitivity.sameValueReadback',async()=>{const r=await a.getFollowSensitivity({timeoutMs:3000});if(r.rawValue!==mode)throw Error('Readback mismatch');return{rawValue:r.rawValue};});
 }
 for(const [name,fn] of [['follow.speed',()=>a.getFollowSettings({parameter:'speed',timeoutMs:3000})],['rc.speed',()=>a.getRcSettings({parameter:'speed',timeoutMs:3000})],['motor.single',()=>a.getMotorTuning({axis:'pitch',parameter:'stiffness',timeoutMs:3000})],['motor.bulk',()=>a.getMotorTuning({timeoutMs:3000})],['motor.axis',()=>a.getMotorTuning({axis:'yaw',timeoutMs:3000})],['motor.parameter',()=>a.getMotorTuning({parameter:'stiffness',timeoutMs:3000})]])await check(name,async()=>{const r=await fn(),expected={'motor.single':1,'motor.bulk':12,'motor.axis':4,'motor.parameter':3}[name];if(expected&&(r.values.length!==expected||(expected>1&&r.replies?.length!==expected)))throw Error('Motor result incomplete');return summary(r);});
 await check('degreeInfo',async()=>{const r=await g.requestDegreeInfo({timeoutMs:3000});return{payloadHex:Buffer.from(r.payload??r.message?.payload??[]).toString('hex')};});
 await check('stop',()=>g.stop());rows.push({name:'decoder',ok:g.decoder.invalidFrames===0&&g.decoder.discardedBytes===0,value:{invalidFrames:g.decoder.invalidFrames,discardedBytes:g.decoder.discardedBytes}});
}catch(e){rows.push({name:'session',ok:false,code:e.code??'ERROR'});}
finally{await check('close',async()=>{await g.close();return{connected:g.connected,closed:g.closed};});}
console.log(JSON.stringify({port:'node',entry:'BleDevice',rows},null,2));if(rows.some(r=>!r.ok))process.exitCode=1;
