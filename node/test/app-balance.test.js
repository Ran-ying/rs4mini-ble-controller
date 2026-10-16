import test from 'node:test';
import assert from 'node:assert/strict';
import { connected,until } from './fakes.js';
import { frame,crc16 } from '../src/protocol.js';
import { balanceFields } from '../src/app-balance.js';
const sent=(p,id)=>p.frames().filter(f=>f.commandId===id);
function reply(p,r,body,id=r.commandId) {
  const packet=frame(r.sequence,4,id,Buffer.from(body),0x80);packet[4]=4;packet[5]=2;
  packet.writeUInt16LE(crc16(packet.subarray(0,-2)),packet.length-2);p.rx.emit('data',packet,true);
}
test('balance fields keep zero invalid and separate testing/error from axis outcomes',()=>{
  const empty=balanceFields(0);assert.equal(empty.state,'DEFAULT');assert.equal(empty.axisFieldsValid,false);assert.equal(empty.axisResults.roll.result,null);
  const finished=balanceFields(0x9b);assert.equal(finished.state,'FINISH');assert.deepEqual(Object.values(finished.axisResults).map(r=>r.result),['PASS','MARGINAL','FAIL']);
  assert.equal(balanceFields(64).state,'TESTING');assert.equal(balanceFields(255).state,'ERROR');assert.equal(balanceFields(255).axisResults.yaw.result,'FAIL');
});
test('balance fields retain every raw byte and independently preserve invalid axes',()=>{
  for (let value=0;value<256;value++)assert.equal(balanceFields(value).rawValue,value);
  const partial=balanceFields(0x90);assert.equal(partial.axisResults.roll.result,'PASS');assert.equal(partial.axisResults.pitch.result,null);assert.equal(partial.axisFieldsValid,false);
  assert.throws(()=>balanceFields(256));assert.throws(()=>balanceFields(true));
});
test('balance status reads named index37 and rejects wrong command correlation',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const read=gimbal.appCommands.getBalanceTestStatus();await until(()=>sent(p,0x10).length);const r=sent(p,0x10).at(-1);
  assert.equal(r.payload.toString('hex'),'25');let done=false;read.then(()=>{done=true;});reply(p,r,[0],0x0f);await new Promise(resolve=>setImmediate(resolve));assert.equal(done,false);
  reply(p,r,[0,37,9,0x9b]);const result=await read;assert.equal(result.balance.state,'FINISH');assert.equal(result.parameters[0].headerByte,9);assert.equal(result.physicalCompletionVerified,false);
});
test('balance start is fixed64 in common namespace and owns only through ACK',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const start=gimbal.appCommands.sendBalanceTestRequest();await until(()=>sent(p,0x0f).length);const r=sent(p,0x0f).at(-1);
  assert.equal(r.payload.toString('hex'),'250140');assert.equal(r.flags,0x40);assert.equal(sent(p,0x40).length,0);
  await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});reply(p,r,[0]);const result=await start;
  assert.equal(result.requestedValue,64);assert.equal(result.physicalCompletionVerified,false);assert.equal(gimbal.activeOperation,null);
});
test('balance rejects arbitrary actions before frames and malformed status/nonzero ACK',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  await assert.rejects(gimbal.appCommands.sendBalanceTestRequest({value:0}));await assert.rejects(gimbal.appCommands.sendBalanceTestRequest({timeoutMs:0}));assert.equal(p.frames().length,0);
  const bad=assert.rejects(gimbal.appCommands.getBalanceTestStatus(),{code:'RS4MINI_PROTOCOL_ERROR'});await until(()=>sent(p,0x10).length);reply(p,sent(p,0x10).at(-1),[0,37,1]);await bad;
  const nack=assert.rejects(gimbal.appCommands.sendBalanceTestRequest(),{code:'RS4MINI_DEVICE_ERROR'});await until(()=>sent(p,0x0f).length);reply(p,sent(p,0x0f).at(-1),[7]);await nack;
});
test('balance stop/timeout clear pending without sending an invented abort or replay',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const cancel=assert.rejects(gimbal.appCommands.sendBalanceTestRequest(),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p,0x0f).length);await gimbal.stop();await cancel;
  await assert.rejects(gimbal.appCommands.sendBalanceTestRequest({timeoutMs:5}),{code:'RS4MINI_RESPONSE_TIMEOUT'});
  assert.equal(sent(p,0x0f).length,2);assert.ok(sent(p,0x0f).every(r=>r.payload.toString('hex')==='250140'));assert.equal(gimbal.experimental.pending.size,0);
});
