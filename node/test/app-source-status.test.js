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
test('source statuses cannot resolve a pending parameter request',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const q=gimbal.appCommands.getWorkMode();await until(()=>p.frames().some(f=>f.commandId===16));const request=p.frames().find(f=>f.commandId===16);incoming(p);incoming(p,51,Buffer.from([255]));assert.equal(gimbal.experimental.pending.size,1);incoming(p,16,Buffer.from([0,62,1,2]),128,request.sequence);assert.equal((await q).sourceMode,'Fpv');
});
