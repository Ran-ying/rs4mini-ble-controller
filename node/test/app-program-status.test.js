import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {connected,until} from './fakes.js';import {frame,crc16} from '../src/protocol.js';import {programStatusNotification} from '../src/app-program-status.js';
const vectors=JSON.parse(readFileSync(new URL('./fixtures/program-status.json',import.meta.url),'utf8'));
const body=()=>Buffer.from('00620401020304','hex');
const msg=(commandId=107,payload=body(),flags=0)=>({sender:4,receiver:2,commandSet:4,commandId,payload,flags});
function incoming(p,command=107,payload=body(),flags=0,sequence=1){const b=frame(sequence,4,command,payload,flags);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('program source vectors preserve unsigned counters, mask differences, duplicate and unknown records',()=>{
 for(const v of vectors){const r=programStatusNotification(msg(v.commandId,Buffer.from(v.bodyHex,'hex')));assert.ok(r,v.name);for(const[k,value]of Object.entries(v.expected))assert.deepEqual(r[k],value,v.name+': '+k);assert.equal(r.bodyHex,v.bodyHex);assert.equal(r.kind,'program');for(const k of ['deviceVerified','modelLayoutVerified','programCorrelationVerified','physicalCompletionVerified'])assert.equal(r[k],false);}
});
test('program candidates reject ACK encrypted wrong endpoints and non-byte inputs',()=>{
 for(const patch of [{flags:128},{flags:1},{flags:true},{flags:256},{sender:36},{receiver:4},{commandSet:0},{commandId:98},{payload:[]}])assert.equal(programStatusNotification({...msg(),...patch}),null);
 assert.ok(programStatusNotification(msg(107,body(),64))); // ACK requested still never sends one.
});
test('malformed records and source negative lengths never produce partial candidates',()=>{
 for(const hex of ['','00','0062','006204010203','006203010203','006280','00fe00620401'])assert.equal(programStatusNotification(msg(107,Buffer.from(hex,'hex'))),null,hex);
 assert.equal(programStatusNotification(msg(56,Buffer.alloc(3))),null);assert.equal(programStatusNotification(msg(100,Buffer.alloc(4))),null);
});
test('program cache and observer are independent snapshots gated by explicit source',async t=>{
 const{gimbal,peripheral:p}=await connected(t);incoming(p);assert.equal(gimbal.appCommands.programStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');const errors=[];gimbal.onError=e=>errors.push(e);gimbal.onAppStatus=s=>{s.records[0].sourceValues.status=99;throw Error('program observer');};incoming(p);
 const r=gimbal.appCommands.programStatus;r.records[0].sourceValues.status=77;assert.equal(gimbal.appCommands.programStatus.records[0].sourceValues.status,1);assert.equal(errors.length,1);assert.equal(p.frames().length,0);assert.equal(gimbal.latestTelemetry,null);assert.equal('batteryStatus' in gimbal.appCommands,false);
});
test('one frame never retains records from older program frames',async t=>{
 const{gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);incoming(p,100,Buffer.from('feffff0080','hex'));assert.equal(gimbal.appCommands.programStatus.records.length,0);assert.equal(gimbal.appCommands.programStatus.sourceValues.currentPictures,65535);
 incoming(p,107,Buffer.from('00fe00','hex'));assert.equal(gimbal.appCommands.programStatus.records.length,1);assert.equal(gimbal.appCommands.programStatus.records[0].sourceValues,null);
});
test('invalid candidate keeps cache and profile switch plus disconnect clear it',async t=>{
 const{gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);const before=gimbal.appCommands.programStatus;incoming(p,107,Buffer.from('006203010203','hex'));incoming(p,107,body(),128);assert.deepEqual(gimbal.appCommands.programStatus,before);
 gimbal.experimental.useProfile('rs3');assert.equal(gimbal.appCommands.programStatus,null);incoming(p);assert.equal(gimbal.appCommands.programStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);await gimbal.disconnect();assert.equal(gimbal.appCommands.programStatus,null);
});
test('program notifications cannot complete pending query or send ACK or subscription',async t=>{
 const{gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const q=gimbal.appCommands.getWorkMode();await until(()=>p.frames().some(f=>f.commandId===16));const request=p.frames().find(f=>f.commandId===16),writes=p.frames().length;
 incoming(p,107,body(),64,request.sequence);incoming(p,56,Buffer.from('0b010264','hex'),64);incoming(p,100,Buffer.from('0101000200','hex'),64);assert.equal(gimbal.experimental.pending.size,1);assert.equal(p.frames().length,writes);assert.equal(gimbal.activeOperation,null);
 incoming(p,16,Buffer.from([0,62,1,2]),128,request.sequence);assert.equal((await q).sourceMode,'Fpv');
});
