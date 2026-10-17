import test from 'node:test';
import assert from 'node:assert/strict';
import {connected,until} from './fakes.js';
import {frame,crc16} from '../src/protocol.js';
const sent=p=>p.frames().filter(f=>f.commandId===0x36);
function reply(p,r,body,id=0x36){const b=frame(r.sequence,4,id,Buffer.from(body),0x80);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('handle query is empty, correlated and preserves raw bytes and bit0 source booleans',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const read=gimbal.appCommands.getHandleSettings();await until(()=>sent(p).length);const r=sent(p).at(-1);assert.equal(r.payload.length,0);assert.equal(r.flags,0x40);
 reply(p,r,[0,7,1,0,255,3,2,3,254,99],0x35);assert.equal(gimbal.experimental.pending.size,1);reply(p,r,[0,7,1,0,255,3,2,3,254,99]);const result=await read;assert.equal(result.values.length,8);assert.equal(result.values[0].rawValue,7);assert.equal(result.values[3].rawValue,255);assert.equal(result.values[5].sourceBit0,false);assert.equal(result.values[6].sourceBit0,true);assert.equal(result.values[7].rawValue,254);assert.equal(result.bodyHex,'070100ff030203fe63');assert.equal(result.modelLayoutVerified,false);assert.equal(gimbal.appCommands.userParameterStatus,null);assert.equal(p.frames().length,1);
});
test('handle read validates profile/options before any transmission',async t=>{
 const {gimbal,peripheral:p}=await connected(t);await assert.rejects(gimbal.appCommands.getHandleSettings());gimbal.appCommands.useProfile('ronin-2.2.2');for(const options of [{index:0},{timeoutMs:0},{timeoutMs:true}])await assert.rejects(gimbal.appCommands.getHandleSettings(options));assert.equal(p.frames().length,0);
});
test('handle reply rejects short body and negative ACK without manufacturing fields',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');for(const [body,code] of [[[0,1,2,3,4,5,6,7],'RS4MINI_PROTOCOL_ERROR'],[[7],'RS4MINI_DEVICE_ERROR']]){const n=sent(p).length,failed=assert.rejects(gimbal.appCommands.getHandleSettings(),{code});await until(()=>sent(p).length>n);reply(p,sent(p).at(-1),body);await failed;}assert.equal(gimbal.experimental.pending.size,0);
});
test('handle timeout and disconnect clear pending reads without retry or write commands',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');await assert.rejects(gimbal.appCommands.getHandleSettings({timeoutMs:10}),{code:'RS4MINI_RESPONSE_TIMEOUT'});const failed=assert.rejects(gimbal.appCommands.getHandleSettings(),{code:'RS4MINI_DISCONNECTED'});await until(()=>sent(p).length===2);await gimbal.disconnect();await failed;assert.equal(gimbal.experimental.pending.size,0);assert.equal(sent(p).length,2);const cleanup=p.frames().filter(f=>f.commandId!==0x36);assert.equal(cleanup.length,3);assert.ok(cleanup.every(f=>f.commandSet===4&&f.commandId===1&&f.payload.toString('hex')==='000400040004000002'));
});
