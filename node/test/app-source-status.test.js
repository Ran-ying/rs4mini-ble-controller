import test from 'node:test';import assert from 'node:assert/strict';
import {connected,until} from './fakes.js';import {frame,crc16} from '../src/protocol.js';
import {sourceStatusNotification} from '../src/app-source-status.js';
const body=()=>Buffer.from('04ff3e6701aabb','hex');
const msg=(commandId=39,payload=body(),flags=0)=>({sender:4,receiver:2,commandSet:4,commandId,payload,flags});
function incoming(p,commandId=39,payload=body(),flags=0,sequence=1){const b=frame(sequence,4,commandId,payload,flags);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('abnormal source has21 direct fields plus roll-or-pitch composite excluding yaw',()=>{
 const r=sourceStatusNotification(msg()),v=r.sourceValues;assert.equal(Object.keys(v).length,22);assert.equal(v.getGimbalGravity,3);assert.equal(v.getSleepMode,1);assert.equal(v.getFanDirection,1);assert.equal(v.getVerticalDirection,1);assert.equal(v.getGimbalDirectionWhenVertical,1);assert.equal(v.isMotorProtected,true);assert.equal(v.isPanoReady,true);assert.equal(v.isYawLocked,true);assert.equal(v.isGimbalLocked,false);assert.equal(r.bodyHex,'04ff3e6701aabb');assert.equal(r.modelLayoutVerified,false);
 for(const value of [1,2,4,248]){const b=body();b[0]=value;assert.equal(sourceStatusNotification(msg(39,b)).sourceValues.isGimbalLocked,value===1||value===2);}
});
test('source battery preserves255 and tail without using other-model battery envelope',()=>{
 for(const value of [0,100,255]){const r=sourceStatusNotification(msg(51,Buffer.from([value,99])));assert.equal(r.rawCapacityValue,value);assert.equal(r.bodyHex,Buffer.from([value,99]).toString('hex'));assert.equal(r.sourceGetter,'getCapacityPercentage');}
 assert.equal(sourceStatusNotification({...msg(51,Buffer.from([50])),commandSet:13,commandId:2}),null);
});
test('both source notifications require complete unencrypted request envelopes',()=>{
 for(const command of [39,51])for(const patch of [{payload:Buffer.alloc(command===39?4:0)},{flags:128},{flags:1},{flags:true},{flags:256},{flags:-1},{sender:36},{receiver:4},{commandSet:0},{commandId:40},{payload:[]}])assert.equal(sourceStatusNotification({...msg(command),...patch}),null);
});
test('source caches are opt-in, copied and observer-isolated without sends or feedback mutation',async t=>{
 const {gimbal,peripheral:p}=await connected(t);incoming(p);assert.equal(gimbal.appCommands.abnormalStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');const errors=[];gimbal.onError=e=>errors.push(e);gimbal.onAppStatus=s=>{if(s.kind==='abnormal')s.sourceValues.getSleepMode=99;else s.rawCapacityValue=0;throw Error('observer');};incoming(p);incoming(p,51,Buffer.from([255]));const a=gimbal.appCommands.abnormalStatus;assert.equal(a.sourceValues.getSleepMode,1);a.sourceValues.isYawLocked=false;assert.equal(gimbal.appCommands.abnormalStatus.sourceValues.isYawLocked,true);assert.equal(gimbal.appCommands.batteryStatus.rawCapacityValue,255);assert.equal(errors.length,2);assert.equal(p.frames().length,0);assert.equal(gimbal.latestTelemetry,null);assert.equal(gimbal.appCommands.calibrationStatus,null);assert.equal(gimbal.appCommands.handheldStickStatus,null);
});
test('invalid reports retain independent caches and profile/disconnect clears both',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);incoming(p,51,Buffer.from([255]));const a=gimbal.appCommands.abnormalStatus,b=gimbal.appCommands.batteryStatus;incoming(p,39,Buffer.alloc(4));incoming(p,51,Buffer.alloc(0));incoming(p,39,body(),128);assert.deepEqual(gimbal.appCommands.abnormalStatus,a);assert.deepEqual(gimbal.appCommands.batteryStatus,b);gimbal.experimental.useProfile('rs3');assert.equal(gimbal.appCommands.abnormalStatus,null);assert.equal(gimbal.appCommands.batteryStatus,null);incoming(p);assert.equal(gimbal.appCommands.abnormalStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);incoming(p,51,Buffer.from([50]));await gimbal.disconnect();assert.equal(gimbal.appCommands.abnormalStatus,null);assert.equal(gimbal.appCommands.batteryStatus,null);assert.equal(p.frames().filter(f=>[18,39,51].includes(f.commandId)).length,0);
});
test('source statuses cannot resolve a pending parameter request',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const q=gimbal.appCommands.getWorkMode();await until(()=>p.frames().some(f=>f.commandId===16));const request=p.frames().find(f=>f.commandId===16);incoming(p);incoming(p,51,Buffer.from([255]));assert.equal(gimbal.experimental.pending.size,1);incoming(p,16,Buffer.from([0,62,1,2]),128,request.sequence);assert.equal((await q).sourceMode,'Fpv');
});
