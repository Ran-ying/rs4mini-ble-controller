import test from 'node:test';
import assert from 'node:assert/strict';
import {connected,until} from './fakes.js';
import {frame,crc16} from '../src/protocol.js';
import {handheldStickNotification} from '../src/app-handheld-stick.js';
const body=()=>Buffer.from('0080ff7f0380aabb','hex');
const message=(payload=body(),flags=0)=>({sender:4,receiver:2,commandSet:4,commandId:0x57,flags,payload});
function incoming(p,payload=body(),flags=0,commandId=0x57,sequence=1){const b=frame(sequence,4,commandId,payload,flags);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('stick candidate preserves signed endpoints, unknown flags and trailing bytes',()=>{
 const r=handheldStickNotification(message());assert.equal(r.sourceStickX,-32768);assert.equal(r.sourceStickY,32767);assert.equal(r.rawStateWord,32771);assert.equal(r.unknownStateBits,32768);assert.equal(r.sourceTriggerPressed,true);assert.equal(r.sourceStickControlEnabled,true);assert.equal(r.bodyHex,'0080ff7f0380aabb');assert.equal(r.axisMappingVerified,false);assert.equal(r.deviceVerified,false);
});
test('stick bits are independent; short ACK encrypted and wrong endpoint messages are rejected',()=>{
 for(const [word,trigger,enabled] of [[0,false,false],[1,true,false],[2,false,true],[3,true,true],[65535,true,true]]) {const b=body();b.writeUInt16LE(word,4);const r=handheldStickNotification(message(b));assert.equal(r.sourceTriggerPressed,trigger);assert.equal(r.sourceStickControlEnabled,enabled);}
 for(const change of [{flags:128},{flags:1},{flags:true},{flags:256},{flags:-1},{sender:36},{receiver:4},{commandSet:0},{commandId:0x58},{payload:Buffer.alloc(5)},{payload:[]},{flags:undefined}])assert.equal(handheldStickNotification({...message(),...change}),null);
});
test('stick events require profile, copy snapshots and isolate observers without sends',async t=>{
 const {gimbal,peripheral:p}=await connected(t);incoming(p);assert.equal(gimbal.appCommands.handheldStickStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');const errors=[];gimbal.onError=e=>errors.push(e);gimbal.onAppStatus=s=>{s.sourceStickX=10;throw Error('observer');};incoming(p);const s=gimbal.appCommands.handheldStickStatus;assert.equal(s.sourceStickX,-32768);s.rawStateWord=0;assert.equal(gimbal.appCommands.handheldStickStatus.rawStateWord,32771);assert.equal(errors.length,1);assert.equal(p.frames().length,0);assert.equal(gimbal.latestTelemetry,null);assert.equal(gimbal.appCommands.userParameterStatus,null);assert.equal(gimbal.appCommands.calibrationStatus,null);
});
test('invalid stick frames retain cache and research-source switches clear it',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);const before=gimbal.appCommands.handheldStickStatus;incoming(p,Buffer.alloc(5));incoming(p,body(),128);incoming(p,body(),1);assert.deepEqual(gimbal.appCommands.handheldStickStatus,before);gimbal.appCommands.useProfile('ronin-2.2.2');assert.equal(gimbal.appCommands.handheldStickStatus,null);incoming(p);gimbal.experimental.useProfile('rs3');assert.equal(gimbal.appCommands.handheldStickStatus,null);incoming(p);assert.equal(gimbal.appCommands.handheldStickStatus,null);assert.equal(p.frames().length,0);
});
test('disconnect clears stick cache without a subscription or control58 request',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);await gimbal.disconnect();assert.equal(gimbal.appCommands.handheldStickStatus,null);assert.equal(p.frames().filter(f=>f.commandId===0x58||f.commandId===0x12).length,0);
});
test('passive stick report does not complete a pending parameter request',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const query=gimbal.appCommands.getWorkMode();await until(()=>p.frames().some(f=>f.commandId===16));const request=p.frames().find(f=>f.commandId===16);incoming(p);assert.equal(gimbal.experimental.pending.size,1);assert.equal(gimbal.appCommands.handheldStickStatus.sourceStickX,-32768);incoming(p,Buffer.from([0,62,1,2]),128,16,request.sequence);assert.equal((await query).sourceMode,'Fpv');
});
