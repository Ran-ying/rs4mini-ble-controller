import test from 'node:test';import assert from 'node:assert/strict';
import {connected,until,gate} from './fakes.js';import {frame,crc16} from '../src/protocol.js';
import {programStatusRequestSpec,programStatusRequestReply} from '../src/app-program-request.js';
function incoming(p,request,body=Buffer.from([0]),patch={}){const b=frame(patch.sequence??request.sequence,4,patch.commandId??107,body,patch.flags??128);b[4]=patch.sender??4;b[5]=patch.receiver??2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
async function sent(p,count=1){await until(()=>p.frames().filter(f=>f.commandId===107).length===count);return p.frames().filter(f=>f.commandId===107).at(-1);}
test('fixed single-push bodies use program wire values rather than ordinals',()=>{
 for(const [program,hex,tag] of [['track','00020162',98],['timelapse','00020137',55],['panorama','00020163',99]]){const spec=programStatusRequestSpec(program);assert.equal(Buffer.from(spec.payload).toString('hex'),hex);assert.equal(spec.requestedProgramCommandId,tag);}
 for(const value of [undefined,null,98,'delay','__proto__','TRACK',{}])assert.throws(()=>programStatusRequestSpec(value));
});
test('request reply retains opaque ACK body and does not assert fresh state',()=>{
 const m={sender:4,receiver:2,commandSet:4,commandId:107,flags:128,payload:Buffer.from('0001620401020304','hex'),raw:Buffer.from([1])};const r=programStatusRequestReply(m,'track');assert.equal(r.bodyHex,'01620401020304');assert.equal(r.requestType,'RequestSinglePush');assert.equal(r.freshStatusVerified,false);assert.equal(r.programCorrelationVerified,false);
 for(const flags of [129,-128,384])assert.throws(()=>programStatusRequestReply({...m,flags},'track'),{code:'RS4MINI_PROTOCOL_ERROR'});
});
test('source and input validation reject before writes',async t=>{
 const {gimbal,peripheral:p}=await connected(t);await assert.rejects(gimbal.appCommands.sendProgramStatusRequest({program:'track'}));gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const options of [{program:'delay'},{program:98},{program:'track',requestType:0},{program:'track',timeoutMs:0}])await assert.rejects(gimbal.appCommands.sendProgramStatusRequest(options));assert.equal(p.frames().length,0);
});
test('all three named requests await only ACK and preserve passive snapshot',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');let count=0;
 for(const program of ['track','timelapse','panorama']){const q=gimbal.appCommands.sendProgramStatusRequest({program});const request=await sent(p,++count);assert.equal(request.flags,64);assert.equal(request.payload.toString('hex'),{track:'00020162',timelapse:'00020137',panorama:'00020163'}[program]);
  incoming(p,request,Buffer.from('00620402030405','hex'),{flags:0});assert.equal(gimbal.experimental.pending.size,1);const before=gimbal.appCommands.programStatus;
  incoming(p,request);const result=await q;assert.equal(result.requestedProgram,program);assert.equal(result.acknowledged,true);assert.equal(result.bodyHex,'');assert.deepEqual(gimbal.appCommands.programStatus,before);assert.equal(result.freshStatusVerified,false);}
 assert.equal(p.frames().length,3);
});
test('simultaneous requests match sequence not latest requested program',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const input={program:'track'};const a=gimbal.appCommands.sendProgramStatusRequest(input);input.program='panorama';const b=gimbal.appCommands.sendProgramStatusRequest({program:'timelapse'});await sent(p,2);const frames=p.frames();incoming(p,frames[0],Buffer.from([0]),{sender:36});assert.equal(gimbal.experimental.pending.size,2);incoming(p,frames[1]);assert.equal((await b).requestedProgram,'timelapse');incoming(p,frames[0]);assert.equal((await a).requestedProgram,'track');
});
test('NACK missing status and encrypted ACK never fall back to cached notification',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');let count=0;
 for(const [body,flags,code] of [[Buffer.from([7]),128,'RS4MINI_DEVICE_ERROR'],[Buffer.alloc(0),128,'RS4MINI_PROTOCOL_ERROR'],[Buffer.from([0]),129,'RS4MINI_PROTOCOL_ERROR']]){const q=gimbal.appCommands.sendProgramStatusRequest({program:'track'});const rejected=assert.rejects(q,{code});const r=await sent(p,++count);incoming(p,r,Buffer.from('00620401020304','hex'),{flags:0});incoming(p,r,body,{flags});await rejected;assert.equal(gimbal.experimental.pending.size,0);}
 assert.equal(p.frames().length,3);
});
test('timeout late ACK and disconnect never replay a single-push request',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const q=gimbal.appCommands.sendProgramStatusRequest({program:'track',timeoutMs:30});const rejected=assert.rejects(q,{code:'RS4MINI_RESPONSE_TIMEOUT'});const r=await sent(p);await rejected;incoming(p,r);assert.equal(gimbal.experimental.pending.size,0);const next=gimbal.appCommands.sendProgramStatusRequest({program:'panorama'});const disconnected=assert.rejects(next,{code:'RS4MINI_DISCONNECTED'});await sent(p,2);await gimbal.disconnect();await disconnected;assert.equal(p.frames().filter(f=>f.commandId===107).length,2);assert.equal(gimbal.appCommands.programStatus,null);
});
test('expired request queued behind a write cannot transmit later',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const blocked=gate();gimbal.writeChain=blocked.promise;const q=gimbal.appCommands.sendProgramStatusRequest({program:'track',timeoutMs:15});await assert.rejects(q,{code:'RS4MINI_RESPONSE_TIMEOUT'});blocked.resolve();await assert.rejects(gimbal.writeChain,{code:'RS4MINI_OPERATION_CANCELLED'});assert.equal(p.frames().length,0);assert.equal(gimbal.experimental.pending.size,0);
});
