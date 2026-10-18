import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {connected,until} from './fakes.js';
import {frame,crc16} from '../src/protocol.js';
import {externalDeviceNotification} from '../src/app-external-device.js';
const vectors=JSON.parse(readFileSync(new URL('./fixtures/external-device.json',import.meta.url)));
const body=()=>Buffer.from(vectors[0].bodyHex,'hex');
const message=(payload=body(),flags=0)=>({sender:4,receiver:2,commandSet:4,commandId:105,flags,payload});
function incoming(p,payload=body(),flags=0,commandId=105,sequence=1){const b=frame(sequence,4,commandId,payload,flags);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('seven shared external records preserve axis order, signed endpoints and unknowns',()=>{
 assert.equal(vectors.length,7);for(const v of vectors){const r=externalDeviceNotification(message(Buffer.from(v.bodyHex,'hex')));assert.deepEqual(r.records,v.records);assert.equal(r.bodyHex,v.bodyHex);for(const [k,value] of Object.entries(r))if(k.endsWith('Verified'))assert.equal(value,false);}
 const s=externalDeviceNotification(message()).records[0].speedControl;assert.deepEqual([s.sourcePitchSpeed,s.sourceRollSpeed,s.sourceYawSpeed],[-32768,32767,0]);
});
test('Other source7 differs from unknown raw255 and records never invent missing speeds',()=>{
 const a=externalDeviceNotification(message(Buffer.from(vectors[2].bodyHex,'hex'))).records[0].speedControl,b=externalDeviceNotification(message(Buffer.from(vectors[3].bodyHex,'hex'))).records[0].speedControl;assert.equal(a.sourceControlType,'Other');assert.equal(a.sourceControlTypeKnown,true);assert.equal(b.sourceControlType,'Other');assert.equal(b.sourceControlTypeKnown,false);assert.equal(b.rawControlType,255);
 assert.equal(externalDeviceNotification(message(Buffer.from('ff00','hex'))).records[0].speedControl,undefined);
});
test('entire malformed TLV bodies, source negative lengths and wrong envelopes reject',()=>{
 for(const payload of [Buffer.alloc(0),Buffer.from([2]),Buffer.from([2,6,...Array(6).fill(0)]),Buffer.from([2,7,...Array(6).fill(0)]),Buffer.from([9,128,...Array(128).fill(0)]),Buffer.concat([body(),Buffer.from([9])]),[]])assert.equal(externalDeviceNotification(message(payload)),null);
 for(const patch of [{flags:128},{flags:1},{flags:256},{flags:-1},{flags:true},{flags:undefined},{sender:36},{receiver:4},{commandSet:0},{commandId:102}])assert.equal(externalDeviceNotification({...message(),...patch}),null);
 const max=Buffer.from([9,127,...Array(127).fill(1)]);assert.equal(externalDeviceNotification(message(max)).records[0].length,127);
});
test('explicit profile, nested snapshots and observer failure isolation never cause writes',async t=>{
 const {gimbal,peripheral:p}=await connected(t);incoming(p);assert.equal(gimbal.appCommands.externalDeviceStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');const errors=[];gimbal.onError=e=>errors.push(e);gimbal.onAppStatus=s=>{s.records[0].speedControl.sourcePitchSpeed=100;throw Error('external observer');};incoming(p);
 const status=gimbal.appCommands.externalDeviceStatus;assert.equal(status.records[0].speedControl.sourcePitchSpeed,-32768);status.records[0].speedControl.sourceYawSpeed=42;status.records.push({});assert.equal(gimbal.appCommands.externalDeviceStatus.records.length,1);assert.equal(gimbal.appCommands.externalDeviceStatus.records[0].speedControl.sourceYawSpeed,0);assert.equal(errors.length,1);assert.equal(p.frames().length,0);assert.equal(gimbal.latestTelemetry,null);assert.equal(gimbal.appCommands.peripheralStatus,null);
});
test('bad packets retain cache; unknown-only frame replaces old fields; source and disconnect clear',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);const before=gimbal.appCommands.externalDeviceStatus;incoming(p,Buffer.concat([body(),Buffer.from([9])]));incoming(p,body(),128);incoming(p,body(),1);assert.deepEqual(gimbal.appCommands.externalDeviceStatus,before);
 incoming(p,Buffer.from('ff00','hex'));assert.equal(gimbal.appCommands.externalDeviceStatus.records[0].speedControl,undefined);gimbal.appCommands.useProfile('ronin-2.2.2');assert.equal(gimbal.appCommands.externalDeviceStatus,null);incoming(p);gimbal.experimental.useProfile('rs3');assert.equal(gimbal.appCommands.externalDeviceStatus,null);incoming(p);assert.equal(gimbal.appCommands.externalDeviceStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);await gimbal.disconnect();assert.equal(gimbal.appCommands.externalDeviceStatus,null);assert.equal(p.frames().filter(f=>f.commandId===105||f.commandId===18).length,0);
});
test('passive candidate cannot complete pending query or change operation owner',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const query=gimbal.appCommands.getWorkMode();await until(()=>p.frames().some(f=>f.commandId===16));const request=p.frames().find(f=>f.commandId===16);incoming(p);assert.equal(gimbal.experimental.pending.size,1);incoming(p,Buffer.from([0,62,1,2]),128,16,request.sequence);assert.equal((await query).sourceMode,'Fpv');
 const moving=gimbal.moveTo({pan:5});const rejected=assert.rejects(moving,{code:'RS4MINI_MOVE_CANCELLED'});const owner=gimbal.activeOperation;incoming(p);assert.equal(gimbal.activeOperation,owner);assert.equal(gimbal.latestTelemetry,null);await gimbal.stop();await rejected;
});
