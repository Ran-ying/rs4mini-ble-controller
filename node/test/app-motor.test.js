import test from 'node:test';
import assert from 'node:assert/strict';
import { connected, until } from './fakes.js';
import { frame,crc16 } from '../src/protocol.js';
const sent=(p,id)=>p.frames().filter(f=>f.commandId===id);
function reply(p,request,body,id=request.commandId) {
  const packet=frame(request.sequence,4,id,Buffer.from(body),0x80); packet[4]=4;packet[5]=2;
  packet.writeUInt16LE(crc16(packet.subarray(0,-2)),packet.length-2);p.rx.emit('data',packet,true);
}
test('motor query uses32 namespace, complete named order and explicit metadata widths',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const read=gimbal.appCommands.getMotorTuning(); await until(()=>sent(p,0x32).length);
  const request=sent(p,0x32).at(-1);assert.equal(request.payload.toString('hex'),'000102030405060708090a0b');
  let done=false;read.then(()=>{done=true;});reply(p,request,[0,0,1,50],0x10);
  await new Promise(resolve=>setImmediate(resolve));assert.equal(done,false);
  reply(p,request,[0,...Array.from({length:12},(_,index)=>[index,9,index===0?255:index]).flat()]);
  const result=await read;assert.equal(result.values.length,12);assert.equal(result.values[0].parameter,'stiffness');
  assert.equal(result.values[0].rawValue,255);assert.equal(result.values[0].withinSourceRange,false);
  assert.equal(result.values[0].headerByte,9);assert.equal(result.values[11].parameter,'preControl');assert.equal(result.values[11].axis,'yaw');
});
test('motor filter selection is copied before awaiting and uses source parameter names',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const options={axis:'yaw'},read=gimbal.appCommands.getMotorTuning(options);options.axis='pitch';
  await until(()=>sent(p,0x32).length);const request=sent(p,0x32).at(-1);assert.equal(request.payload.toString('hex'),'0205080b');
  reply(p,request,[0,2,1,20,5,1,30,8,1,0,11,1,100]);const result=await read;
  assert.deepEqual(result.values.map(v=>v.axis),Array(4).fill('yaw'));
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
