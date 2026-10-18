import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {connected,until} from './fakes.js';import {frame,crc16} from '../src/protocol.js';import {componentCalibrationPayload,componentCalibrationReply} from '../src/app-component-calibration.js';
const sent=(p,id)=>p.frames().filter(f=>f.commandId===id).at(-1);
function reply(p,s,payload,flags=128){const b=frame(s.sequence,4,s.commandId,Buffer.from(payload),flags);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
const message=payload=>({sender:4,receiver:2,commandSet:4,commandId:8,flags:128,payload:Buffer.from(payload),raw:Buffer.alloc(0)});
test('component ACK shared vectors distinguish business status and incomplete responses',()=>{
 const vectors=JSON.parse(fs.readFileSync(new URL('./fixtures/component-calibration.json',import.meta.url)));assert.equal(vectors.length,7);
 for(const v of vectors){const r=componentCalibrationReply(message(Buffer.from(v.payloadHex,'hex')),128);for(const [k,value] of Object.entries(v.expected))assert.deepEqual(r[k],value,v.name+':'+k);assert.equal(r.physicalCompletionVerified,false);assert.equal(r.businessRequestAssociationVerified,false);}
 for(let v=0;v<256;v++){const r=componentCalibrationReply(message([0,v,v]),0).calibration;assert.equal(r.rawPart,v);assert.equal(r.rawStatus,v);assert.equal(r.sourcePartKnown,v<10);assert.equal(r.sourceStatusKnown,v<3);}
 assert.throws(()=>componentCalibrationReply(message([1,0,1]),0),{code:'RS4MINI_DEVICE_ERROR'});assert.throws(()=>componentCalibrationReply({...message([0,0,1]),flags:131},0),{code:'RS4MINI_PROTOCOL_ERROR'});
});
test('component request requires explicit AUTO before any frame',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const options of [{},{sourcePart:'GYRO'},{sourcePart:0},{sourcePart:'AUTO',motorEnabled:true},{sourcePart:'AUTO',timeoutMs:true}])await assert.rejects(gimbal.appCommands.sendComponentCalibrationRequest(options));assert.equal(p.frames().length,0);assert.equal(componentCalibrationPayload('AUTO').toString('hex'),'00');
});
test('component transaction owns fresh motor read through correlated ACK and never mutates caches',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');let events=0;gimbal.onAppStatus=()=>events++;const options={sourcePart:'AUTO'};const task=gimbal.appCommands.sendComponentCalibrationRequest(options);options.sourcePart='GYRO';await until(()=>sent(p,16));const read=sent(p,16);assert.equal(read.payload.toString('hex'),'23');assert.ok(p.frames().slice(0,3).every(f=>f.commandId===1));await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});assert.throws(()=>gimbal.appCommands.useProfile('ronin-2.2.2'),{code:'RS4MINI_BUSY'});
 reply(p,read,[0,35,1,128]);await until(()=>sent(p,8));const start=sent(p,8);assert.equal(start.payload.toString('hex'),'00');assert.equal(start.flags,64);assert.notEqual(start.sequence,read.sequence);reply(p,{...start,sequence:start.sequence+1},[0,0,1]);reply(p,start,[0,0,1],0);reply(p,{...start,commandId:48},[100,0],0);assert.equal(gimbal.activeOperation,'sendComponentCalibrationRequest');reply(p,start,[0,0,0]);const r=await task;assert.equal(r.calibration.sourceStatus,'FAIL');assert.equal(r.acknowledged,true);assert.equal(r.motorPreflightRawValue,128);assert.equal(gimbal.appCommands.calibrationStatus,null);assert.equal(gimbal.latestTelemetry,null);assert.equal(events,1);assert.equal(gimbal.experimental.pending.size,0);assert.equal(p.frames().filter(f=>f.commandId===15).length,0);
});
test('disabled, malformed, rejected or encrypted motor reads never send component calibration',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const [payload,flags,code] of [[[0,35,1,1],128,'RS4MINI_MOTOR_DISABLED'],[[7],128,'RS4MINI_DEVICE_ERROR'],[[0,35,1],128,'RS4MINI_PROTOCOL_ERROR'],[[0,35,1,0],131,'RS4MINI_PROTOCOL_ERROR']]){const count=p.frames().filter(f=>f.commandId===16).length;const task=gimbal.appCommands.sendComponentCalibrationRequest({sourcePart:'AUTO'}),rejected=assert.rejects(task,{code});await until(()=>p.frames().filter(f=>f.commandId===16).length>count);reply(p,sent(p,16),payload,flags);await rejected;assert.equal(sent(p,8),undefined);assert.equal(gimbal.activeOperation,null);}
});
test('component cancel before read completion ignores late replies and sends no calibration',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const rejected=assert.rejects(gimbal.appCommands.sendComponentCalibrationRequest({sourcePart:'AUTO'}),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p,16));const read=sent(p,16);await gimbal.stop();await rejected;reply(p,read,[0,35,1,0]);await new Promise(r=>setImmediate(r));assert.equal(sent(p,8),undefined);assert.equal(gimbal.experimental.pending.size,0);
});
test('cancel after calibration send does not invent firmware abort or replay',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const rejected=assert.rejects(gimbal.appCommands.sendComponentCalibrationRequest({sourcePart:'AUTO'}),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p,16));reply(p,sent(p,16),[0,35,1,0]);await until(()=>sent(p,8));const start=sent(p,8);await gimbal.stop();await rejected;reply(p,start,[0,0,1]);await gimbal.disconnect();assert.equal(p.frames().filter(f=>f.commandId===8).length,1);assert.equal(gimbal.appCommands.sensorCalibrationStatus,null);
});
test('component total deadline passes remaining read budget to ACK and prevents late sends',async()=>{
 const {AppCommands}=await import('../src/app-commands.js');const descriptor=Object.getOwnPropertyDescriptor(globalThis,'performance');let clock=1000,advance=75;const timeouts=[];
 const owner={motionEpoch:1,_stop:async()=>{},_run:async(_,fn)=>fn({controller:new AbortController()}),experimental:{_queryPayloadCommand:async(_,cmd,payload,timeout)=>{timeouts.push(timeout);if(cmd[1]===16){clock+=advance;return {...message([0,35,1,0]),commandId:16};}return message([0,0,1]);}}};const app=new AppCommands(owner);app._profile='ronin-2.2.2';
 try{Object.defineProperty(globalThis,'performance',{value:{now:()=>clock},configurable:true});await app.sendComponentCalibrationRequest({sourcePart:'AUTO',timeoutMs:100});assert.deepEqual(timeouts,[100,25]);advance=101;timeouts.length=0;await assert.rejects(app.sendComponentCalibrationRequest({sourcePart:'AUTO',timeoutMs:100}),{code:'RS4MINI_RESPONSE_TIMEOUT'});assert.equal(timeouts.length,1);}finally{Object.defineProperty(globalThis,'performance',descriptor);}
});
test('component ACK errors and incomplete bodies release transaction without promoting caches',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const [payload,flags,code] of [[[1,0,1],128,'RS4MINI_DEVICE_ERROR'],[[],128,'RS4MINI_PROTOCOL_ERROR'],[[0,0,1],131,'RS4MINI_PROTOCOL_ERROR'],[[0],128,null],[[0,5],128,null]]){
  const count=p.frames().filter(f=>f.commandId===16).length;const task=gimbal.appCommands.sendComponentCalibrationRequest({sourcePart:'AUTO'});const result=code?assert.rejects(task,{code}):task;await until(()=>p.frames().filter(f=>f.commandId===16).length>count);reply(p,sent(p,16),[0,35,1,0]);await until(()=>gimbal.experimental.pending.size===1&&[...gimbal.experimental.pending.values()].some(()=>sent(p,8)?.sequence>sent(p,16).sequence));reply(p,sent(p,8),payload,flags);const r=await result;if(!code){assert.equal(r.businessComplete,false);assert.equal(r.calibration,null);}assert.equal(gimbal.activeOperation,null);assert.equal(gimbal.experimental.pending.size,0);assert.equal(gimbal.appCommands.calibrationStatus,null);
 }
});
