import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {connected,until,gate} from './fakes.js';
import {frame,crc16} from '../src/protocol.js';
import {programStatusSubscriptionSpec,programStatusSubscriptionReply} from '../src/app-program-request.js';
const vectors=JSON.parse(readFileSync(new URL('./fixtures/program-subscription.json',import.meta.url)));
function incoming(p,r,body=Buffer.from([0]),flags=128,patch={}) {
 const b=frame(patch.sequence??r.sequence,4,patch.commandId??107,body,flags);b[4]=patch.sender??4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);
}
async function sent(p,count=1){await until(()=>p.frames().filter(f=>f.commandId===107).length===count);return p.frames().filter(f=>f.commandId===107).at(-1);}
test('six shared subscription request vectors retain source request types and exact tags',()=>{
 assert.equal(vectors.length,6);
 for(const v of vectors){const s=programStatusSubscriptionSpec(v.program,v.enabled);assert.equal(Buffer.from(s.payload).toString('hex'),v.bodyHex);assert.equal(s.requestType,v.requestType);assert.equal(s.requestedProgramCommandId,v.programCommand);}
 for(const enabled of [undefined,null,0,1,'true',{}])assert.throws(()=>programStatusSubscriptionSpec('track',enabled));
 for(const program of [98,'__proto__','delay'])assert.throws(()=>programStatusSubscriptionSpec(program,true));
});
test('subscription result reports opaque ACK without remote state or stream claims',()=>{
 const message={sender:4,receiver:2,commandSet:4,commandId:107,flags:128,payload:Buffer.from('0001620401020304','hex'),raw:Buffer.from([1])};
 for(const enabled of [true,false]){const r=programStatusSubscriptionReply(message,'track',enabled);assert.equal(r.bodyHex,'01620401020304');assert.equal(r.requestedEnabled,enabled);assert.equal(r.freshStatusVerified,false);assert.equal(r.notificationStreamVerified,false);assert.equal(r.remoteSubscriptionStateVerified,false);}
 for(const flags of [129,-128,384])assert.throws(()=>programStatusSubscriptionReply({...message,flags},'track',true),{code:'RS4MINI_PROTOCOL_ERROR'});
});
test('profile invalid fields and timeout reject before any subscription write',async t=>{
 const {gimbal,peripheral:p}=await connected(t);await assert.rejects(gimbal.appCommands.sendProgramStatusSubscriptionRequest({program:'track',enabled:true}));gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const options of [{program:'track',enabled:1},{program:98,enabled:true},{program:'track',enabled:true,requestType:0},{program:'track',enabled:false,timeoutMs:0}])await assert.rejects(gimbal.appCommands.sendProgramStatusSubscriptionRequest(options));assert.equal(p.frames().length,0);
});
test('all six requests await only ACK and never filter passive candidates after stop',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');let count=0;
 for(const v of vectors){const q=gimbal.appCommands.sendProgramStatusSubscriptionRequest({program:v.program,enabled:v.enabled});const r=await sent(p,++count);assert.equal(r.payload.toString('hex'),v.bodyHex);assert.equal(r.flags,64);
 incoming(p,r,Buffer.from('00620401020304','hex'),0);assert.equal(gimbal.experimental.pending.size,1);const before=gimbal.appCommands.programStatus;incoming(p,r);const result=await q;assert.equal(result.requestType,v.requestType);assert.equal(result.requestedEnabled,v.enabled);assert.deepEqual(gimbal.appCommands.programStatus,before);}
 assert.equal(p.frames().length,6);assert.equal(gimbal.activeOperation,null);assert.equal(gimbal.appCommands.programStatus.records[0].rawTag,98);
});
test('start and stop capture input and match separate sequences with no local subscription state',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const input={program:'track',enabled:true};const a=gimbal.appCommands.sendProgramStatusSubscriptionRequest(input);input.enabled=false;input.program='panorama';const b=gimbal.appCommands.sendProgramStatusSubscriptionRequest({program:'track',enabled:false});await sent(p,2);const frames=p.frames();incoming(p,frames[0],Buffer.from([0]),128,{sender:36});assert.equal(gimbal.experimental.pending.size,2);incoming(p,frames[1]);assert.equal((await b).requestedEnabled,false);incoming(p,frames[0]);const result=await a;assert.equal(result.requestedEnabled,true);assert.equal(result.requestedProgram,'track');assert.equal(p.frames().length,2);
});
test('NACK and invalid ACK fail without inverse subscription or cached fallback',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');let count=0;
 for(const [body,flags,code] of [[Buffer.from([7]),128,'RS4MINI_DEVICE_ERROR'],[Buffer.alloc(0),128,'RS4MINI_PROTOCOL_ERROR'],[Buffer.from([0]),129,'RS4MINI_PROTOCOL_ERROR']]){const q=gimbal.appCommands.sendProgramStatusSubscriptionRequest({program:'track',enabled:true});const rejected=assert.rejects(q,{code});const r=await sent(p,++count);incoming(p,r,Buffer.from('00620401020304','hex'),0);incoming(p,r,body,flags);await rejected;assert.equal(gimbal.experimental.pending.size,0);}
 assert.equal(p.frames().length,3);
});
test('timeout late ACK and disconnect never issue implicit stop or replay',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const q=gimbal.appCommands.sendProgramStatusSubscriptionRequest({program:'track',enabled:true,timeoutMs:25});const rejected=assert.rejects(q,{code:'RS4MINI_RESPONSE_TIMEOUT'});const r=await sent(p);await rejected;incoming(p,r);assert.equal(gimbal.experimental.pending.size,0);const b=gimbal.appCommands.sendProgramStatusSubscriptionRequest({program:'track',enabled:false});const disconnected=assert.rejects(b,{code:'RS4MINI_DISCONNECTED'});await sent(p,2);await gimbal.disconnect();await disconnected;assert.equal(p.frames().filter(f=>f.commandId===107).length,2);
});
test('queued subscription timeout cannot send after queue releases',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const blocked=gate();gimbal.writeChain=blocked.promise;await assert.rejects(gimbal.appCommands.sendProgramStatusSubscriptionRequest({program:'track',enabled:true,timeoutMs:15}),{code:'RS4MINI_RESPONSE_TIMEOUT'});blocked.resolve();await assert.rejects(gimbal.writeChain,{code:'RS4MINI_OPERATION_CANCELLED'});assert.equal(p.frames().length,0);assert.equal(gimbal.experimental.pending.size,0);
});
