import test from 'node:test';
import assert from 'node:assert/strict';
import {connected} from './fakes.js';
import {frame,crc16} from '../src/protocol.js';
import {userParameterNotification} from '../src/app-user-parameters.js';
const payload=()=>{const b=Buffer.alloc(78,0xaa);b[0]=99;b[2]=2;b[9]=0x34;b[10]=0x12;b[63]=255;b[64]=255;b[73]=255;return b;};
const message=(body=payload(),flags=0)=>({sender:4,receiver:2,commandSet:4,commandId:0x24,flags,payload:body});
function incoming(p,body=payload(),flags=0){const b=frame(1,4,0x24,body,flags);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('fixed push preserves all 17 source fields, unsigned values and unknown layout bytes',()=>{
  const result=userParameterNotification(message());const get=name=>result.values.find(row=>row.sourceGetter===name);
  assert.equal(result.values.length,17);assert.equal(get('getYawSpeed').rawValue,4660);assert.equal(get('getRollAccel').rawValue,65535);assert.equal(get('getRollSmoothTrack').rawValue,255);assert.equal(result.preset.rawValue,2);assert.equal(result.preset.sourceEnum,null);assert.equal(result.bodyHex,payload().toString('hex'));assert.equal(result.modelLayoutVerified,false);assert.equal(result.activePresetVerified,false);
});
test('fixed push requires complete known layout and explicit unencrypted request context',()=>{
  for(const flags of [128,1,7,256,-256,0.5,true])assert.equal(userParameterNotification(message(payload(),flags)),null);
  for(const change of [{sender:0xe5},{receiver:4},{commandId:0x10},{commandSet:0},{payload:Buffer.alloc(73)},{flags:undefined}])assert.equal(userParameterNotification({...message(),...change}),null);
  const b=payload();b[2]=1;assert.equal(userParameterNotification(message(b)).preset.sourceEnum,'CUSTOM_2');
});
test('facade passive events require source selection, copy observers and never transmit',async t=>{
  const {gimbal,peripheral:p}=await connected(t);incoming(p);assert.equal(gimbal.appCommands.userParameterStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');
  const errors=[];gimbal.onError=e=>errors.push(e);gimbal.onAppStatus=status=>{assert.equal(status.kind,'userParameters');status.values.length=0;status.preset.rawValue=99;throw Error('observer');};
  incoming(p);const result=gimbal.appCommands.userParameterStatus;assert.equal(result.values.length,17);assert.equal(result.preset.rawValue,2);result.values[0].rawHex='changed';assert.notEqual(gimbal.appCommands.userParameterStatus.values[0].rawHex,'changed');assert.equal(errors.length,1);assert.equal(p.frames().length,0);assert.equal(gimbal.latestTelemetry,null);assert.equal(gimbal.appCommands.calibrationStatus,null);
});
test('invalid notifications retain prior report and profile changes reset passive cache',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);const before=gimbal.appCommands.userParameterStatus;
  incoming(p,Buffer.alloc(73));incoming(p,payload(),128);incoming(p,payload(),1);assert.deepEqual(gimbal.appCommands.userParameterStatus,before);
  gimbal.appCommands.useProfile('ronin-2.2.2');assert.equal(gimbal.appCommands.userParameterStatus,null);incoming(p);gimbal.experimental.useProfile('rs3');assert.equal(gimbal.appCommands.userParameterStatus,null);incoming(p);assert.equal(gimbal.appCommands.userParameterStatus,null);assert.equal(p.frames().length,0);
});
test('disconnect clears fixed report with no synthetic stop or subscription request',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);await gimbal.disconnect();assert.equal(gimbal.appCommands.userParameterStatus,null);assert.equal(p.frames().filter(f=>f.commandId===0x12).length,0);
});
