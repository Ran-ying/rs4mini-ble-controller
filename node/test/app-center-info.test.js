import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {connected,until,gate} from './fakes.js';import {frame,crc16} from '../src/protocol.js';
import {centerInfoSpec,centerInfoReply} from '../src/app-center-info.js';
const vectors=JSON.parse(readFileSync(new URL('./fixtures/center-info.json',import.meta.url)));
const payload=Buffer.from(vectors[0].payloadHex,'hex');
function msg(p=payload,patch={}){return {sender:229,receiver:2,commandSet:0,commandId:50,flags:128,payload:p,raw:Buffer.from([1]),...patch};}
function incoming(p,r,body=payload,patch={}){const b=frame(patch.sequence??r.sequence,patch.commandSet??0,patch.commandId??50,body,patch.flags??128);b[4]=patch.sender??229;b[5]=patch.receiver??2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
async function request(p,count=1){await until(()=>p.frames().filter(f=>f.commandSet===0&&f.commandId===50).length===count);return p.frames().filter(f=>f.commandSet===0&&f.commandId===50).at(-1);}
test('CENTER GET shared contracts preserve source version, signed SN and incomplete errors',()=>{
 for(const v of vectors){const fn=()=>centerInfoReply(msg(Buffer.from(v.payloadHex,'hex')),v.sourceVersion);if(v.error)assert.throws(fn,{code:v.error});else {const r=fn();assert.equal(r.sourceSerialNumber,v.sourceSerialNumber);assert.equal(r.serialNumberRawHex,v.serialNumberRawHex);assert.equal(r.dateRaw.year,2026);assert.equal(r.unknownActiveBits,130);assert.equal(r.activationValidityVerified,false);assert.equal(r.actualSessionVersionVerified,false);}}
 for(const [v,b] of Object.entries({Ver1_0:1,Ver1_1:17,Ver1_3:17,Ver13:1}))assert.deepEqual(Array.from(centerInfoSpec(v).payload),[b]);
 for(const v of [undefined,null,1,true,'OTHER','Ver14',{}])assert.throws(()=>centerInfoSpec(v),TypeError);
});
test('CENTER response strictly validates envelope and every flags byte',()=>{
 for(let flags=0;flags<256;flags++){if((flags&128)&&!(flags&7))assert.equal(centerInfoReply(msg(payload,{flags}),'Ver1_1').acknowledged,true);else assert.throws(()=>centerInfoReply(msg(payload,{flags}),'Ver1_1'),{code:'RS4MINI_PROTOCOL_ERROR'});}
 for(const patch of [{sender:4},{sender:5},{receiver:4},{commandSet:4},{commandId:1},{flags:true},{flags:256},{flags:-1},{payload:[]}])assert.throws(()=>centerInfoReply(msg(payload,patch),'Ver1_1'),{code:'RS4MINI_PROTOCOL_ERROR'});
 const p=Buffer.from(payload),r=centerInfoReply(msg(p),'Ver1_1');p.fill(0);assert.equal(r.message.payload.toString('hex'),payload.toString('hex'));assert.equal(r.trailingBodyHex,'dead');
});
test('CENTER public API validates profile/version/options before any writes',async t=>{
 const {gimbal,peripheral:p}=await connected(t);await assert.rejects(gimbal.appCommands.getCenterActivationInfo({sourceVersion:'Ver1_1'}));gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const options of [{},{sourceVersion:'OTHER'},{sourceVersion:'Ver1_1',timeoutMs:0},{sourceVersion:'Ver1_1',receiver:229}])await assert.rejects(gimbal.appCommands.getCenterActivationInfo(options));assert.equal(p.frames().length,0);
 await assert.rejects(gimbal.experimental._queryPayloadCommand('bad',[4,50],Buffer.from([17]),30,{receiver:229}));assert.equal(p.frames().length,0);
});
test('CENTER uses E5/COMMON request and rejects wrong endpoint, command, sequence and nonACK',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const options={sourceVersion:'Ver1_1'};const q=gimbal.appCommands.getCenterActivationInfo(options);options.sourceVersion='Ver1_0';const r=await request(p);assert.equal(r.receiver,229);assert.equal(r.flags,64);assert.deepEqual(Array.from(r.payload),[17]);
 for(const patch of [{sender:4},{sender:5},{receiver:4},{sequence:r.sequence+1},{commandSet:4},{commandId:1},{flags:0}]){incoming(p,r,payload,patch);assert.equal(gimbal.experimental.pending.size,1);}
 incoming(p,r);const result=await q;assert.equal(result.sourceVersion,'Ver1_1');assert.equal(result.sourceSerialNumber,'A45-1');assert.equal(p.frames().length,1);assert.equal(gimbal.latestTelemetry,null);assert.equal(gimbal.appCommands.calibrationStatus,null);
});
test('CENTER and gimbal queries sharing id32 resolve only their own target and set',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const q=gimbal.appCommands.getCenterActivationInfo({sourceVersion:'Ver1_1'}),other=gimbal.appCommands.getMotorTuning({axis:'pitch',parameter:'stiffness'});const a=await request(p);await until(()=>p.frames().some(f=>f.commandSet===4&&f.commandId===50));const b=p.frames().find(f=>f.commandSet===4&&f.commandId===50);
 incoming(p,a);assert.equal((await q).sourceSerialNumber,'A45-1');assert.equal(gimbal.experimental.pending.size,1);incoming(p,b,Buffer.from([0,0,1,10]),{commandSet:4,commandId:50,sender:4});assert.equal((await other).values[0].rawValue,10);
});
test('CENTER bad/short/encrypted ACK fails without a previous SN success fallback',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');let n=0;let q=gimbal.appCommands.getCenterActivationInfo({sourceVersion:'Ver1_1'});incoming(p,await request(p,++n));await q;
 for(const [b,flags,code] of [[Buffer.from([0]),128,'RS4MINI_PROTOCOL_ERROR'],[Buffer.from([7]),128,'RS4MINI_DEVICE_ERROR'],[payload,129,'RS4MINI_PROTOCOL_ERROR']]){q=gimbal.appCommands.getCenterActivationInfo({sourceVersion:'Ver1_1'});const bad=assert.rejects(q,{code});incoming(p,await request(p,++n),b,{flags});await bad;assert.equal(gimbal.experimental.pending.size,0);}
 assert.equal(p.frames().length,4);
});
test('CENTER timeout, late response, busy profile change and disconnect never replay',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');let q=gimbal.appCommands.getCenterActivationInfo({sourceVersion:'Ver1_1',timeoutMs:30});const timeout=assert.rejects(q,{code:'RS4MINI_RESPONSE_TIMEOUT'});const r=await request(p);assert.throws(()=>gimbal.appCommands.useProfile('ronin-2.2.2'),{code:'RS4MINI_BUSY'});await timeout;incoming(p,r);assert.equal(gimbal.experimental.pending.size,0);
 q=gimbal.appCommands.getCenterActivationInfo({sourceVersion:'Ver1_1'});const loss=assert.rejects(q,{code:'RS4MINI_DISCONNECTED'});await request(p,2);await gimbal.disconnect();await loss;assert.equal(p.frames().filter(f=>f.commandSet===0).length,2);
});
test('CENTER query timing out while queued cannot send later',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const wait=gate();gimbal.writeChain=wait.promise;await assert.rejects(gimbal.appCommands.getCenterActivationInfo({sourceVersion:'Ver1_1',timeoutMs:20}),{code:'RS4MINI_RESPONSE_TIMEOUT'});wait.resolve();await assert.rejects(gimbal.writeChain,{code:'RS4MINI_OPERATION_CANCELLED'});assert.equal(p.frames().length,0);
});
