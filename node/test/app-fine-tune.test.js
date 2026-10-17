import test from 'node:test';import assert from 'node:assert/strict';
import {connected,until,gate} from './fakes.js';import {frame,crc16} from '../src/protocol.js';import {fineTuneSpec} from '../src/app-fine-tune.js';
const sent=p=>p.frames().filter(f=>f.commandId===7);
function reply(p,r,body,id=7){const b=frame(r.sequence,4,id,Buffer.from(body),0x80);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('fine source vectors use float32, truncate and wire axis values rather than ordinals',()=>{
 for(const [axis,delta,hex,steps] of [['pitch',-1.29,'f402',-12],['roll',1.29,'0c00',12],['roll',1.999999999,'1400',20],['pitch',-.09,'0002',0],['roll',-2,'ec00',-20]]){const r=fineTuneSpec({axis,adjustmentDegrees:delta});assert.equal(r.payload.toString('hex'),hex);assert.equal(r.encodedTenths,steps);}
});
test('fine request snapshots intent and owns until ACK, not physical completion',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const options={axis:'pitch',adjustmentDegrees:-1.29};const task=gimbal.appCommands.sendFineTuneRequest(options);options.axis='roll';options.adjustmentDegrees=2;await until(()=>sent(p).length);assert.equal(sent(p)[0].payload.toString('hex'),'f402');assert.equal(sent(p)[0].flags,0x40);await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});reply(p,sent(p)[0],[0]);const r=await task;assert.equal(r.axis,'pitch');assert.equal(r.requestedAdjustmentDegrees,-1.29);assert.equal(r.encodedTenths,-12);assert.equal(r.nominalAdjustmentDegrees,-1.2);assert.equal(r.physicalCompletionVerified,false);assert.equal(r.stabilizationStateVerified,false);assert.equal(gimbal.activeOperation,null);
});
test('fine rejects absent source, unknown fields/axes and bad deltas before any write',async t=>{
 const {gimbal,peripheral:p}=await connected(t);await assert.rejects(gimbal.appCommands.sendFineTuneRequest({axis:'roll',adjustmentDegrees:1}));gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const patch of [{axis:'yaw'},{axis:0},{axis:{toString:()=> 'roll'}},{adjustmentDegrees:true},{adjustmentDegrees:2.1},{adjustmentDegrees:NaN},{adjustmentDegrees:Infinity},{adjustmentDegrees:undefined},{index:0},{timeoutMs:0}])await assert.rejects(gimbal.appCommands.sendFineTuneRequest({axis:'roll',adjustmentDegrees:1,...patch}));assert.equal(p.frames().length,0);
});
test('fine ignores unrelated ACK and reports device failure without retry',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const failed=assert.rejects(gimbal.appCommands.sendFineTuneRequest({axis:'roll',adjustmentDegrees:.1}),{code:'RS4MINI_DEVICE_ERROR'});await until(()=>sent(p).length);reply(p,sent(p)[0],[0],0x0f);assert.equal(gimbal.experimental.pending.size,1);reply(p,sent(p)[0],[7]);await failed;assert.equal(sent(p).length,1);assert.equal(gimbal.experimental.pending.size,0);
});
test('fine preamble cancellation never submits a fine command',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const blocked=gate(),started=gate(),original=p.tx.writeAsync.bind(p.tx);let first=true;p.tx.writeAsync=async(...args)=>{if(first){first=false;started.resolve();await blocked.promise;}return original(...args);};
 const failed=assert.rejects(gimbal.appCommands.sendFineTuneRequest({axis:'pitch',adjustmentDegrees:.1}),{code:'RS4MINI_OPERATION_CANCELLED'});await started.promise;const stopping=gimbal.stop();blocked.resolve();await stopping;await failed;assert.equal(sent(p).length,0);assert.equal(gimbal.experimental.pending.size,0);
});
test('fine ACK cancellation and deadline never replay or send a rollback',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const opts={axis:'roll',adjustmentDegrees:.1};const failed=assert.rejects(gimbal.appCommands.sendFineTuneRequest(opts),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p).length);await gimbal.stop();await failed;await assert.rejects(gimbal.appCommands.sendFineTuneRequest({...opts,timeoutMs:10}),{code:'RS4MINI_RESPONSE_TIMEOUT'});assert.equal(sent(p).length,2);assert.ok(sent(p).every(f=>f.payload.toString('hex')==='0100'));assert.ok(p.frames().every(f=>[1,7].includes(f.commandId)));assert.equal(gimbal.activeOperation,null);assert.equal(gimbal.experimental.pending.size,0);
});
