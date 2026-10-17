import test from 'node:test';import assert from 'node:assert/strict';
import {connected,until,gate} from './fakes.js';import {frame,crc16} from '../src/protocol.js';import {handleWriteSpec} from '../src/app-handle.js';
const sent=p=>p.frames().filter(f=>f.commandId===0x35);
function reply(p,r,body,id=0x35){const b=frame(r.sequence,4,id,Buffer.from(body),0x80);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('handle setting writes one source field and fresh FF defaults each time',()=>{
 for(const [setting,value,hex] of [['dualChannelMode',0,'00ffffffffffffff'],['tiltDirection',1,'ff01ffffffffffff'],['panDirection',1,'ffff01ffffffffff']])assert.equal(handleWriteSpec({setting,value}).payload.toString('hex'),hex);
 const a=handleWriteSpec({setting:'panDirection',value:0});a.payload.fill(0);assert.equal(handleWriteSpec({setting:'dualChannelMode',value:1}).payload.toString('hex'),'01ffffffffffffff');
});
test('handle snapshots input, holds ownership until ACK and makes no physical or persistence claim',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const opts={setting:'panDirection',value:1};const task=gimbal.appCommands.sendHandleSettingRequest(opts);opts.setting='dualChannelMode';opts.value=0;await until(()=>sent(p).length);assert.equal(sent(p)[0].payload.toString('hex'),'ffff01ffffffffff');assert.equal(sent(p)[0].flags,0x40);await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});reply(p,sent(p)[0],[0,99]);const r=await task;assert.equal(r.setting,'panDirection');assert.equal(r.requestedValue,1);assert.equal(r.bodyHex,'63');for(const key of ['deviceVerified','physicalCompletionVerified','unspecifiedByteSemanticsVerified','readbackVerified','persistenceVerified'])assert.equal(r[key],false);assert.equal(gimbal.appCommands.userParameterStatus,null);assert.equal(gimbal.activeOperation,null);
});
test('handle rejects source absence, unknown or excluded fields and noninteger values before frames',async t=>{
 const {gimbal,peripheral:p}=await connected(t);await assert.rejects(gimbal.appCommands.sendHandleSettingRequest({setting:'panDirection',value:1}));gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const patch of [{setting:'profile'},{setting:'zoom2Speed'},{setting:'rollDirection'},{setting:0},{setting:{toString:()=> 'panDirection'}},{value:true},{value:255},{value:-1},{value:.5},{value:NaN},{value:Infinity},{value:undefined},{index:2},{timeoutMs:0}])await assert.rejects(gimbal.appCommands.sendHandleSettingRequest({setting:'panDirection',value:1,...patch}));assert.equal(p.frames().length,0);
});
test('handle NACK is an error without cache fallback, readback, retries or rollback',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const failed=assert.rejects(gimbal.appCommands.sendHandleSettingRequest({setting:'tiltDirection',value:0}),{code:'RS4MINI_DEVICE_ERROR'});await until(()=>sent(p).length);reply(p,sent(p)[0],[0],0x36);assert.equal(gimbal.experimental.pending.size,1);reply(p,sent(p)[0],[7]);await failed;assert.equal(sent(p).length,1);assert.ok(p.frames().every(f=>[1,0x35].includes(f.commandId)));assert.equal(gimbal.experimental.pending.size,0);
});
test('handle cancellation during stop preamble never writes settings',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const blocked=gate(),started=gate(),original=p.tx.writeAsync.bind(p.tx);let first=true;p.tx.writeAsync=async(...args)=>{if(first){first=false;started.resolve();await blocked.promise;}return original(...args);};const failed=assert.rejects(gimbal.appCommands.sendHandleSettingRequest({setting:'panDirection',value:1}),{code:'RS4MINI_OPERATION_CANCELLED'});await started.promise;const stopping=gimbal.stop();blocked.resolve();await stopping;await failed;assert.equal(sent(p).length,0);assert.equal(gimbal.experimental.pending.size,0);
});
test('handle postwrite cancellation and timeout never repeat or reverse settings',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const opts={setting:'dualChannelMode',value:1};const failed=assert.rejects(gimbal.appCommands.sendHandleSettingRequest(opts),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p).length);await gimbal.stop();await failed;await assert.rejects(gimbal.appCommands.sendHandleSettingRequest({...opts,timeoutMs:10}),{code:'RS4MINI_RESPONSE_TIMEOUT'});assert.equal(sent(p).length,2);assert.ok(sent(p).every(f=>f.payload.toString('hex')==='01ffffffffffffff'));assert.ok(p.frames().every(f=>[1,0x35].includes(f.commandId)));assert.equal(gimbal.activeOperation,null);assert.equal(gimbal.experimental.pending.size,0);
});
