import test from 'node:test';import assert from 'node:assert/strict';
import {connected,until,gate} from './fakes.js';import {frame,crc16} from '../src/protocol.js';import {axisModeWrite,axisModeReply} from '../src/app-axis-mode.js';
const sent=(p,id)=>p.frames().filter(f=>f.commandId===id);
function reply(p,r,body,id=r.commandId){const b=frame(r.sequence,4,id,Buffer.from(body),0x80);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
const message=body=>({sender:4,receiver:2,commandSet:4,commandId:16,flags:128,payload:Buffer.from(body),raw:Buffer.alloc(0)});
test('axis source enums use parameter34 and shifted values rather than motor bit64',()=>{
 for(const [sourceMode,value] of [['ThreeAxis',0],['TwoAxis',8],['Roll360',16],['ThreeDRoll360',24]])assert.equal(axisModeWrite({sourceMode}).payload.toString('hex'),Buffer.from([34,1,value]).toString('hex'));
});
test('axis read preserves unrelated bits and rejects wrong context, short or failed replies',()=>{
 for(const raw of [0,8,16,24,255]){const r=axisModeReply(message([0,34,9,raw]));assert.equal(r.rawValue,raw);assert.equal(r.sourceModeValue,(raw>>3)&3);assert.equal(r.unknownBits,raw&231);assert.equal(r.modelLayoutVerified,false);}
 assert.equal(axisModeReply(message([0,34,9,255])).sourceMode,'ThreeDRoll360');
 for(const body of [[0,35,9,24],[0,34,9],[7]])assert.throws(()=>axisModeReply(message(body)));
});
test('axis getter reads only34 without enabling presets and retains header byte',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const task=gimbal.appCommands.getAxisMode();await until(()=>sent(p,16).length);const r=sent(p,16)[0];assert.equal(r.payload.toString('hex'),'22');reply(p,r,[0,34,9,255]);const result=await task;assert.equal(result.sourceMode,'ThreeDRoll360');assert.equal(result.unknownBits,231);assert.equal(result.parameters[0].headerByte,9);assert.ok(p.frames().every(f=>f.commandId===16));
});
test('axis setter snapshots intent and owns until ACK without composing full track mode',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const opts={sourceMode:'ThreeDRoll360'};const task=gimbal.appCommands.sendAxisModeRequest(opts);opts.sourceMode='ThreeAxis';await until(()=>sent(p,15).length);assert.equal(sent(p,15)[0].payload.toString('hex'),'220118');await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});reply(p,sent(p,15)[0],[0]);const r=await task;assert.equal(r.requestedSourceMode,'ThreeDRoll360');assert.equal(r.requestedRawValue,24);for(const k of ['deviceVerified','physicalCompletionVerified','activePresetVerified','otherBitsPreservationVerified','persistenceVerified'])assert.equal(r[k],false);assert.equal(gimbal.appCommands.userParameterStatus,null);assert.ok(p.frames().every(f=>[1,15].includes(f.commandId)));assert.equal(sent(p,15).length,1);
});
test('axis rejects missing profile, PF/PTF labels, raw values and extra options before writes',async t=>{
 const {gimbal,peripheral:p}=await connected(t);await assert.rejects(gimbal.appCommands.sendAxisModeRequest({sourceMode:'ThreeAxis'}));gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const opts of [{},{sourceMode:'PF'},{sourceMode:'FPV'},{sourceMode:24},{sourceMode:true},{sourceMode:{toString:()=> 'ThreeAxis'}},{sourceMode:'ThreeAxis',index:34},{sourceMode:'ThreeAxis',value:64},{sourceMode:'ThreeAxis',timeoutMs:0}])await assert.rejects(gimbal.appCommands.sendAxisModeRequest(opts));assert.equal(p.frames().length,0);
});
test('axis wrong ACK and NACK never trigger a second parameter write or save',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const failed=assert.rejects(gimbal.appCommands.sendAxisModeRequest({sourceMode:'TwoAxis'}),{code:'RS4MINI_DEVICE_ERROR'});await until(()=>sent(p,15).length);reply(p,sent(p,15)[0],[0],16);assert.equal(gimbal.experimental.pending.size,1);reply(p,sent(p,15)[0],[7]);await failed;assert.equal(sent(p,15).length,1);assert.ok(p.frames().every(f=>[1,15].includes(f.commandId)));
});
test('axis cancellation before request sends nothing; ACK cancellation and timeout do not replay',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const blocked=gate(),started=gate(),original=p.tx.writeAsync.bind(p.tx);let first=true;p.tx.writeAsync=async(...args)=>{if(first){first=false;started.resolve();await blocked.promise;}return original(...args);};
 const opts={sourceMode:'ThreeAxis'};const failed=assert.rejects(gimbal.appCommands.sendAxisModeRequest(opts),{code:'RS4MINI_OPERATION_CANCELLED'});await started.promise;const stopping=gimbal.stop();blocked.resolve();await stopping;await failed;assert.equal(sent(p,15).length,0);
 const cancelled=assert.rejects(gimbal.appCommands.sendAxisModeRequest(opts),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p,15).length);await gimbal.stop();await cancelled;await assert.rejects(gimbal.appCommands.sendAxisModeRequest({...opts,timeoutMs:10}),{code:'RS4MINI_RESPONSE_TIMEOUT'});assert.equal(sent(p,15).length,2);assert.ok(sent(p,15).every(f=>f.payload.toString('hex')==='220100'));assert.equal(gimbal.activeOperation,null);assert.equal(gimbal.experimental.pending.size,0);
});
test('axis link loss and reconnect do not repeat setting',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const failed=assert.rejects(gimbal.appCommands.sendAxisModeRequest({sourceMode:'Roll360'}),{code:'RS4MINI_DISCONNECTED'});await until(()=>sent(p,15).length);await p.disconnectAsync();await failed;await gimbal.connect();assert.equal(sent(p,15).length,1);assert.equal(gimbal.experimental.pending.size,0);
});
