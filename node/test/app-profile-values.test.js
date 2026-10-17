import test from 'node:test';import assert from 'node:assert/strict';
import {connected,until,gate} from './fakes.js';import {frame,crc16} from '../src/protocol.js';import {profileValueWrite,profileValueReply} from '../src/app-profile-values.js';
const sent=(p,id)=>p.frames().filter(f=>f.commandId===id);
function reply(p,r,body,id=r.commandId){const b=frame(r.sequence,4,id,Buffer.from(body),0x80);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
const message=body=>({sender:4,receiver:2,commandSet:4,commandId:16,flags:128,payload:Buffer.from(body),raw:Buffer.alloc(0)});
const calls=g=>[{kind:'userProfile',index:0,options:{sourceProfileValue:2},write:o=>g.appCommands.sendUserProfileRequest(o),read:()=>g.appCommands.getUserProfile()},{kind:'workMode',index:62,options:{sourceMode:'Center'},write:o=>g.appCommands.sendWorkModeRequest(o),read:()=>g.appCommands.getWorkMode()}];
test('profile0 and work62 have distinct source values and no inferred movement names',()=>{
 for(let v=0;v<=5;v++)assert.equal(profileValueWrite('userProfile',v).payload.toString('hex'),Buffer.from([0,1,v]).toString('hex'));
 for(const [mode,v] of [['Free',0],['Flower',1],['Fpv',2],['Center',3]])assert.equal(profileValueWrite('workMode',mode).payload.toString('hex'),Buffer.from([62,1,v]).toString('hex'));
 const p=profileValueReply(message([0,0,9,5]),'userProfile');assert.equal(p.sourceUiName,null);assert.equal(p.withinSourceRange,true);const w=profileValueReply(message([0,62,9,128]),'workMode');assert.equal(w.sourceMode,null);assert.equal(w.withinSourceRange,true);
});
test('profile value replies preserve unknown255 and reject wrong context, short or failed responses',()=>{
 for(const [kind,index] of [['userProfile',0],['workMode',62]]){const r=profileValueReply(message([0,index,9,255]),kind);assert.equal(r.rawValue,255);assert.equal(r.withinSourceRange,false);assert.equal(r.activePresetVerified,false);for(const body of [[0,index===0?62:0,9,2],[0,index,9],[7]])assert.throws(()=>profileValueReply(message(body),kind));}
});
test('named getters query a single source parameter including zero index',async t=>{
 const {gimbal:g,peripheral:p}=await connected(t);g.appCommands.useProfile('ronin-2.2.2');let count=0;for(const c of calls(g)){const task=c.read();count++;await until(()=>sent(p,16).length===count);const request=sent(p,16).at(-1);assert.deepEqual([...request.payload],[c.index]);reply(p,request,[0,c.index,9,2]);const r=await task;assert.equal(r.parameter,c.kind);assert.equal(r.rawValue,2);assert.equal(r.parameters[0].headerByte,9);assert.equal(r.activePresetVerified,false);}assert.ok(p.frames().every(f=>f.commandId===16));
});
test('named setters snapshot options, own until ACK and never switch other domains',async t=>{
 const {gimbal:g,peripheral:p}=await connected(t);g.appCommands.useProfile('ronin-2.2.2');for(const [i,c] of calls(g).entries()){const opts={...c.options};const task=c.write(opts);Object.assign(opts,{sourceProfileValue:5,sourceMode:'Free'});await until(()=>sent(p,15).length===i+1);const request=sent(p,15).at(-1);assert.equal(request.payload[0],c.index);await assert.rejects(g.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});reply(p,request,[0]);const r=await task;assert.equal(r.parameter,c.kind);assert.equal(r.requestedRawValue,c.kind==='userProfile'?2:3);assert.equal(r.activePresetVerified,false);assert.equal(r.persistenceVerified,false);assert.equal(r.physicalCompletionVerified,false);}assert.ok(p.frames().every(f=>[1,15].includes(f.commandId)));assert.equal(g.appCommands.userParameterStatus,null);
});
test('profiles and work modes reject absent source, booleans, aliases and raw fields before writes',async t=>{
 const {gimbal:g,peripheral:p}=await connected(t);await assert.rejects(g.appCommands.sendUserProfileRequest({sourceProfileValue:2}));g.appCommands.useProfile('ronin-2.2.2');for(const v of [true,-1,6,2.5,NaN,Infinity,undefined])await assert.rejects(g.appCommands.sendUserProfileRequest({sourceProfileValue:v}));for(const v of ['PF','FPV',2,true,{},undefined])await assert.rejects(g.appCommands.sendWorkModeRequest({sourceMode:v}));await assert.rejects(g.appCommands.sendWorkModeRequest({sourceMode:'Fpv',index:62}));await assert.rejects(g.appCommands.getUserProfile({axis:'yaw'}));assert.equal(p.frames().length,0);
});
test('profile and work NACK never cause fallback, saves or another write',async t=>{
 const {gimbal:g,peripheral:p}=await connected(t);g.appCommands.useProfile('ronin-2.2.2');for(const [i,c] of calls(g).entries()){const failed=assert.rejects(c.write(c.options),{code:'RS4MINI_DEVICE_ERROR'});await until(()=>sent(p,15).length===i+1);const request=sent(p,15).at(-1);reply(p,request,[0],16);assert.equal(g.experimental.pending.size,1);reply(p,request,[7]);await failed;}assert.equal(sent(p,15).length,2);assert.ok(p.frames().every(f=>[1,15].includes(f.commandId)));
});
test('both setters cancel before write and never replay after cancellation or timeout',async t=>{
 const {gimbal:g,peripheral:p}=await connected(t);g.appCommands.useProfile('ronin-2.2.2');for(const c of calls(g)){const before=sent(p,15).length,blocked=gate(),started=gate(),original=p.tx.writeAsync.bind(p.tx);let first=true;p.tx.writeAsync=async(...args)=>{if(first){first=false;started.resolve();await blocked.promise;}return original(...args);};const failed=assert.rejects(c.write(c.options),{code:'RS4MINI_OPERATION_CANCELLED'});await started.promise;const stopping=g.stop();blocked.resolve();await stopping;await failed;assert.equal(sent(p,15).length,before);p.tx.writeAsync=original;const cancelled=assert.rejects(c.write(c.options),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p,15).length===before+1);await g.stop();await cancelled;await assert.rejects(c.write({...c.options,timeoutMs:10}),{code:'RS4MINI_RESPONSE_TIMEOUT'});assert.equal(sent(p,15).length,before+2);assert.equal(g.activeOperation,null);assert.equal(g.experimental.pending.size,0);}
});
test('disconnect and reconnect never repeat either profile or work request',async t=>{
 const {gimbal:g,peripheral:p}=await connected(t);g.appCommands.useProfile('ronin-2.2.2');for(const [i,c] of calls(g).entries()){const failed=assert.rejects(c.write(c.options),{code:'RS4MINI_DISCONNECTED'});await until(()=>sent(p,15).length===i+1);await p.disconnectAsync();await failed;await g.connect();assert.equal(sent(p,15).length,i+1);}
});
