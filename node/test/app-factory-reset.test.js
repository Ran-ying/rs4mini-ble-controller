import test from 'node:test';import assert from 'node:assert/strict';
import {connected,until,gate} from './fakes.js';import {frame,crc16} from '../src/protocol.js';import {factoryResetSpec} from '../src/app-protocol.js';
const sent=p=>p.frames().filter(f=>f.commandId===0x13);
function reply(p,r,body,id=0x13){const b=frame(r.sequence,4,id,Buffer.from(body),0x80);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('factory reset HG724 source branch uses independent 010001 bodies',()=>{
 const a=factoryResetSpec({sourcePlatform:'HG724'});assert.equal(a.payload.toString('hex'),'010001');a.payload.fill(0);assert.equal(factoryResetSpec({sourcePlatform:'HG724'}).payload.toString('hex'),'010001');
});
test('reset snapshots source branch, owns until ACK and reports no reset scope or persistence',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const opts={sourcePlatform:'HG724'};const task=gimbal.appCommands.sendFactorySettingsResetRequest(opts);opts.sourcePlatform='HG702';await until(()=>sent(p).length);assert.equal(sent(p)[0].payload.toString('hex'),'010001');assert.equal(sent(p)[0].flags,0x40);await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});reply(p,sent(p)[0],[0,99]);const r=await task;assert.equal(r.requestedSourcePlatform,'HG724');assert.equal(r.bodyHex,'63');for(const k of ['deviceVerified','physicalCompletionVerified','targetResetScopeVerified','persistenceVerified'])assert.equal(r[k],false);assert.equal(gimbal.activeOperation,null);
});
test('reset rejects missing source branch, other platform, enum ordinal and raw fields before writes',async t=>{
 const {gimbal,peripheral:p}=await connected(t);await assert.rejects(gimbal.appCommands.sendFactorySettingsResetRequest({sourcePlatform:'HG724'}));gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const opts of [{},{sourcePlatform:'HG702'},{sourcePlatform:103},{sourcePlatform:true},{sourcePlatform:{toString:()=> 'HG724'}},{sourcePlatform:'HG724',payload:[1,0,1]},{sourcePlatform:'HG724',timeoutMs:0}])await assert.rejects(gimbal.appCommands.sendFactorySettingsResetRequest(opts));assert.equal(p.frames().length,0);
});
test('reset ignores wrong ACK and NACK fails without save, readback, retry or fallback',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const failed=assert.rejects(gimbal.appCommands.sendFactorySettingsResetRequest({sourcePlatform:'HG724'}),{code:'RS4MINI_DEVICE_ERROR'});await until(()=>sent(p).length);reply(p,sent(p)[0],[0],0x11);assert.equal(gimbal.experimental.pending.size,1);reply(p,sent(p)[0],[7]);await failed;assert.equal(sent(p).length,1);assert.ok(p.frames().every(f=>[1,0x13].includes(f.commandId)));assert.equal(gimbal.experimental.pending.size,0);
});
test('reset preamble cancellation sends no reset command',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const blocked=gate(),started=gate(),original=p.tx.writeAsync.bind(p.tx);let first=true;p.tx.writeAsync=async(...args)=>{if(first){first=false;started.resolve();await blocked.promise;}return original(...args);};const failed=assert.rejects(gimbal.appCommands.sendFactorySettingsResetRequest({sourcePlatform:'HG724'}),{code:'RS4MINI_OPERATION_CANCELLED'});await started.promise;const stopping=gimbal.stop();blocked.resolve();await stopping;await failed;assert.equal(sent(p).length,0);
});
test('reset ACK cancellation and deadline never replay or undo',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const opts={sourcePlatform:'HG724'};const failed=assert.rejects(gimbal.appCommands.sendFactorySettingsResetRequest(opts),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p).length);await gimbal.stop();await failed;await assert.rejects(gimbal.appCommands.sendFactorySettingsResetRequest({...opts,timeoutMs:10}),{code:'RS4MINI_RESPONSE_TIMEOUT'});assert.equal(sent(p).length,2);assert.ok(p.frames().every(f=>[1,0x13].includes(f.commandId)));assert.equal(gimbal.activeOperation,null);assert.equal(gimbal.experimental.pending.size,0);
});
test('reset link loss rejects waiting and reconnect never repeats the request',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const failed=assert.rejects(gimbal.appCommands.sendFactorySettingsResetRequest({sourcePlatform:'HG724'}),{code:'RS4MINI_DISCONNECTED'});await until(()=>sent(p).length);await p.disconnectAsync();await failed;await gimbal.connect();assert.equal(sent(p).length,1);assert.equal(gimbal.experimental.pending.size,0);assert.equal(gimbal.activeOperation,null);
});
