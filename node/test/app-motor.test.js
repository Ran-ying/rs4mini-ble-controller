import test from 'node:test';
import assert from 'node:assert/strict';
import { connected, until } from './fakes.js';
import { frame,crc16 } from '../src/protocol.js';
const sent=(p,id)=>p.frames().filter(f=>f.commandId===id);
function reply(p,request,body,id=request.commandId) {
  const packet=frame(request.sequence,4,id,Buffer.from(body),0x80); packet[4]=4;packet[5]=2;
  packet.writeUInt16LE(crc16(packet.subarray(0,-2)),packet.length-2);p.rx.emit('data',packet,true);
}
test('motor full read sends twelve individual queries and retains real replies',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
 const read=gimbal.appCommands.getMotorTuning();let done=false;read.then(()=>done=true);
 for(let index=0;index<12;index++){
  await until(()=>sent(p,0x32).length===index+1);const request=sent(p,0x32).at(-1);
  assert.deepEqual([...request.payload],[index]);assert.equal(done,false);
  if(index===0){reply(p,request,[0,0,1,50],0x10);await new Promise(r=>setImmediate(r));assert.equal(sent(p,0x32).length,1);}
  reply(p,request,[0,index,9,index===0?255:index]);
 }
 const r=await read;assert.equal(r.values.length,12);assert.equal(r.replies.length,12);assert.equal(r.readMode,'sequential');assert.equal(r.atomic,false);assert.equal(r.message,undefined);
 assert.equal(r.values[0].rawValue,255);assert.equal(r.values[0].withinSourceRange,false);assert.equal(r.values[11].parameter,'preControl');assert.equal(r.values[11].axis,'yaw');
 assert.equal(new Set(r.replies.map(x=>x.message.sequence)).size,12);
});
test('motor selection snapshot keeps order with one request in flight',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
 const options={axis:'yaw'},read=gimbal.appCommands.getMotorTuning(options);options.axis='pitch';
 for(const [i,index] of [2,5,8,11].entries()){await until(()=>sent(p,0x32).length===i+1);const request=sent(p,0x32).at(-1);assert.deepEqual([...request.payload],[index]);reply(p,request,[0,index,1,20]);}
 const result=await read;assert.deepEqual(result.values.map(v=>v.axis),Array(4).fill('yaw'));assert.equal(result.replies.length,4);
});
test('motor batch cancellation cannot issue remaining requests or return partial values',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
 const fail=assert.rejects(gimbal.appCommands.getMotorTuning(),{code:'RS4MINI_OPERATION_CANCELLED'});
 await until(()=>sent(p,0x32).length===1);reply(p,sent(p,0x32)[0],[0,0,1,10]);await until(()=>sent(p,0x32).length===2);
 await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});await gimbal.stop();await fail;
 assert.equal(sent(p,0x32).length,2);assert.equal(gimbal.experimental.pending.size,0);assert.equal(gimbal.activeOperation,null);
});
test('motor batch rejects an intermediate NACK with no third request',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
 const fail=assert.rejects(gimbal.appCommands.getMotorTuning(),{code:'RS4MINI_DEVICE_ERROR'});
 await until(()=>sent(p,0x32).length===1);reply(p,sent(p,0x32)[0],[0,0,1,10]);await until(()=>sent(p,0x32).length===2);reply(p,sent(p,0x32)[1],[7]);await fail;assert.equal(sent(p,0x32).length,2);
});
test('motor batch carries a decreasing total timeout across responses',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const budgets=[];
 const original=gimbal.experimental._queryPayloadCommand.bind(gimbal.experimental);gimbal.experimental._queryPayloadCommand=(name,cmd,body,timeout,options)=>{budgets.push(timeout);return original(name,cmd,body,timeout,options);};
 const fail=assert.rejects(gimbal.appCommands.getMotorTuning({timeoutMs:80}),{code:'RS4MINI_RESPONSE_TIMEOUT'});
 await until(()=>sent(p,0x32).length===1);await new Promise(r=>setTimeout(r,15));reply(p,sent(p,0x32)[0],[0,0,1,10]);await fail;
 assert.equal(sent(p,0x32).length,2);assert.ok(budgets[1]<budgets[0]-10);assert.equal(gimbal.experimental.pending.size,0);
});
test('named motor setter sends31 with correct value snapshot and waits for ACK',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const options={axis:'roll',parameter:'stiffness',value:50},write=gimbal.appCommands.setMotorTuning(options);options.value=80;
  await until(()=>sent(p,0x31).length);const request=sent(p,0x31).at(-1);
  assert.equal(request.payload.toString('hex'),'010132');assert.equal(request.flags,0x40);
  await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});
  reply(p,request,[0]);const result=await write;assert.equal(result.requestedValue,50);assert.equal(result.axis,'roll');assert.equal(result.physicalCompletionVerified,false);
  assert.equal(sent(p,0x0f).length,0);
});
test('motor invalid names/values cannot bypass source bounds or open raw indexes',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  for (const options of [{axis:'pitch',parameter:'stiffness',value:4},{axis:'roll',parameter:'strength',value:0},{axis:'yaw',parameter:'gyroFiltering',value:101},{axis:'pan',parameter:'stiffness',value:50},{axis:'pitch',parameter:'preControl',value:true},{axis:'pitch',parameter:'stiffness',value:50,index:0}]) await assert.rejects(gimbal.appCommands.setMotorTuning(options));
  await assert.rejects(gimbal.appCommands.getMotorTuning({index:0}));assert.equal(p.frames().length,0);
});
test('motor read rejects truncated records and device NACK before mapping names',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  for (const [body,code] of [[[0,0,1],'RS4MINI_PROTOCOL_ERROR'],[[7],'RS4MINI_DEVICE_ERROR']]) {
    const count=sent(p,0x32).length,failed=assert.rejects(gimbal.appCommands.getMotorTuning({axis:'pitch',parameter:'stiffness'}),{code});
    await until(()=>sent(p,0x32).length>count);reply(p,sent(p,0x32).at(-1),body);await failed;
  }
  assert.equal(gimbal.experimental.pending.size,0);
});
test('motor cancellation/timeout clear pending ACK and never replay a tuning write',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const failed=assert.rejects(gimbal.appCommands.setMotorTuning({axis:'yaw',parameter:'gyroFiltering',value:0}),{code:'RS4MINI_OPERATION_CANCELLED'});
  await until(()=>sent(p,0x31).length);await gimbal.stop();await failed;
  await assert.rejects(gimbal.appCommands.setMotorTuning({axis:'pitch',parameter:'preControl',value:100,timeoutMs:5}),{code:'RS4MINI_RESPONSE_TIMEOUT'});
  assert.equal(sent(p,0x31).length,2);assert.equal(gimbal.experimental.pending.size,0);assert.equal(gimbal.activeOperation,null);
});
