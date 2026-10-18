import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {connected,until,gate} from './fakes.js';import {frame,crc16} from '../src/protocol.js';import {handheldStickControlPayload,handheldStickControlReply} from '../src/app-handheld-stick.js';
const sent=p=>p.frames().filter(f=>f.commandId===88);
function reply(p,s,payload,flags=128,sender=4){const b=frame(s.sequence,4,s.commandId,Buffer.from(payload),flags);b[4]=sender;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
const message=(payload,flags=128)=>({sender:4,receiver:2,commandSet:4,commandId:88,flags,payload:Buffer.from(payload),raw:Buffer.alloc(0)});
test('stick control shared contracts keep ACK tail opaque and require boolean',()=>{
 const vectors=JSON.parse(fs.readFileSync(new URL('./fixtures/handheld-stick-control.json',import.meta.url)));assert.equal(vectors.length,3);
 for(const v of vectors){const r=handheldStickControlReply(message(Buffer.from(v.payloadHex,'hex')),v.enabled);assert.deepEqual([...handheldStickControlPayload(v.enabled)],[Number(v.enabled)]);for(const [k,value] of Object.entries(v.expected))assert.deepEqual(r[k],value);for(const k of ['deviceVerified','physicalCompletionVerified','readbackVerified','persistenceVerified','notificationAssociationVerified'])assert.equal(r[k],false);}
 for(const value of [undefined,null,0,1,'true',{},[]])assert.throws(()=>handheldStickControlPayload(value));
 for(let enc=1;enc<=7;enc++)for(const status of [0,7])assert.throws(()=>handheldStickControlReply(message([status],128|enc),true),{code:'RS4MINI_PROTOCOL_ERROR'});
 assert.throws(()=>handheldStickControlReply(message([7]),true),{code:'RS4MINI_DEVICE_ERROR'});assert.throws(()=>handheldStickControlReply(message([]),true),{code:'RS4MINI_PROTOCOL_ERROR'});
});
test('stick request profile and arguments reject before frames',async t=>{
 const {gimbal,peripheral:p}=await connected(t);await assert.rejects(gimbal.appCommands.sendHandheldStickControlRequest({enabled:true}));gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const options of [{},{enabled:1},{enabled:'false'},{enabled:null},{enabled:false,timeoutMs:0},{enabled:true,timeoutMs:true},{enabled:true,persist:true}])await assert.rejects(gimbal.appCommands.sendHandheldStickControlRequest(options));assert.equal(p.frames().length,0);
});
test('stick request snapshots boolean, owns until strict ACK and does not update push cache',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');reply(p,{sequence:1,commandId:87},[0,0,0,0,0,0],0);const cache=gimbal.appCommands.handheldStickStatus;
 const options={enabled:true},task=gimbal.appCommands.sendHandheldStickControlRequest(options);options.enabled=false;await until(()=>sent(p).length);const request=sent(p)[0];assert.equal(request.flags,64);assert.equal(request.payload.toString('hex'),'01');assert.deepEqual(p.frames().slice(0,3).map(f=>f.commandId),[1,1,1]);await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});assert.throws(()=>gimbal.appCommands.useProfile('ronin-2.2.2'),{code:'RS4MINI_BUSY'});
 for(const [s,flags,sender] of [[{...request,sequence:request.sequence+1},128,4],[request,0,4],[request,128,5],[{...request,commandId:87},128,4]])reply(p,s,[0],flags,sender);
 assert.equal(gimbal.activeOperation,'sendHandheldStickControlRequest');reply(p,request,[0,255,1,2]);const r=await task;assert.equal(r.requestedEnabled,true);assert.equal(r.bodyHex,'ff0102');assert.deepEqual(gimbal.appCommands.handheldStickStatus,cache);assert.equal(gimbal.appCommands.handheldStickStatus.sourceStickControlEnabled,false);assert.equal(gimbal.latestTelemetry,null);assert.equal(gimbal.experimental.pending.size,0);assert.equal(sent(p).length,1);
});
test('real57 notification while pending cannot satisfy58 and ACK cannot overwrite57',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const task=gimbal.appCommands.sendHandheldStickControlRequest({enabled:false});await until(()=>sent(p).length);const request=sent(p)[0];reply(p,{...request,commandId:87},[0,0,0,0,2,0],0);const cache=gimbal.appCommands.handheldStickStatus;assert.equal(cache.sourceStickControlEnabled,true);assert.equal(gimbal.activeOperation,'sendHandheldStickControlRequest');reply(p,request,[0]);assert.equal((await task).requestedEnabled,false);assert.deepEqual(gimbal.appCommands.handheldStickStatus,cache);assert.equal(p.frames().filter(f=>f.commandId!==1&&f.commandId!==88).length,0);
});
test('stick NACK malformed and encrypted ACK release without optimistic state',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const [payload,flags,code] of [[[7],128,'RS4MINI_DEVICE_ERROR'],[[],128,'RS4MINI_PROTOCOL_ERROR'],[[0],131,'RS4MINI_PROTOCOL_ERROR']]){const count=sent(p).length;const failed=assert.rejects(gimbal.appCommands.sendHandheldStickControlRequest({enabled:false}),{code});await until(()=>sent(p).length>count);reply(p,sent(p).at(-1),payload,flags);await failed;assert.equal(gimbal.activeOperation,null);assert.equal(gimbal.appCommands.handheldStickStatus,null);assert.equal(gimbal.experimental.pending.size,0);}
});
test('stick cancellation during neutral preamble sends no58',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const blocked=gate(),started=gate(),original=p.tx.writeAsync.bind(p.tx);let first=true;p.tx.writeAsync=async(...args)=>{if(first){first=false;started.resolve();await blocked.promise;}return original(...args);};const failed=assert.rejects(gimbal.appCommands.sendHandheldStickControlRequest({enabled:true}),{code:'RS4MINI_OPERATION_CANCELLED'});await started.promise;const stopped=gimbal.stop();blocked.resolve();await stopped;await failed;assert.equal(sent(p).length,0);
});
test('stick cancellation after send ignores late ACK and never replays',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const failed=assert.rejects(gimbal.appCommands.sendHandheldStickControlRequest({enabled:true}),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p).length);const request=sent(p)[0];await gimbal.stop();await failed;reply(p,request,[0]);await gimbal.disconnect();await gimbal.connect();assert.equal(sent(p).length,1);assert.equal(gimbal.appCommands.handheldStickStatus,null);assert.equal(gimbal.activeOperation,null);
});
test('stick response timeout has no retry or rollback',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const failed=assert.rejects(gimbal.appCommands.sendHandheldStickControlRequest({enabled:false,timeoutMs:25}),{code:'RS4MINI_RESPONSE_TIMEOUT'});await until(()=>sent(p).length);await failed;assert.equal(sent(p).length,1);assert.equal(gimbal.experimental.pending.size,0);assert.equal(gimbal.activeOperation,null);
});
