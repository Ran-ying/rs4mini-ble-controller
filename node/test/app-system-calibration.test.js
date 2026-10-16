import test from 'node:test';
import assert from 'node:assert/strict';
import { connected,until } from './fakes.js';
import { frame,crc16 } from '../src/protocol.js';
import { systemCalibrationFields } from '../src/app-system-calibration.js';
const sent=(p,id)=>p.frames().filter(f=>f.commandId===id);
function reply(p,r,body,id=r.commandId) {
  const packet=frame(r.sequence,4,id,Buffer.from(body),0x80);packet[4]=4;packet[5]=2;
  packet.writeUInt16LE(crc16(packet.subarray(0,-2)),packet.length-2);p.rx.emit('data',packet,true);
}
test('system calibration maps source enum beyond input range without sharing auto-tune states',()=>{
  assert.deepEqual([0,1,2,3].map(v=>systemCalibrationFields(v).state),['DEFAULT','START','FAIL','SUCCESS']);
  assert.deepEqual(systemCalibrationFields(3),{rawValue:3,state:'SUCCESS'});
});
test('unknown system calibration values stay raw rather than default or array index errors',()=>{
  for (let value=4;value<256;value++)assert.deepEqual(systemCalibrationFields(value),{rawValue:value,state:null});
  assert.throws(()=>systemCalibrationFields(-1));assert.throws(()=>systemCalibrationFields(true));
});
test('system calibration reads36 and cannot be satisfied by auto-tune6E reply',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const read=gimbal.appCommands.getAutoCalibrationStatus();await until(()=>sent(p,0x10).length);const r=sent(p,0x10).at(-1);
  assert.equal(r.payload.toString('hex'),'24');let done=false;read.then(()=>{done=true;});reply(p,r,[0,0,2,2,100],0x6e);
  await new Promise(resolve=>setImmediate(resolve));assert.equal(done,false);
  reply(p,r,[0,36,9,3]);const result=await read;assert.equal(result.systemCalibration.state,'SUCCESS');assert.equal(result.parameters[0].headerByte,9);assert.equal(result.physicalCompletionVerified,false);
});
test('system calibration start is fixed named write and releases ownership after ACK only',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const start=gimbal.appCommands.sendAutoCalibrationRequest();await until(()=>sent(p,0x0f).length);const r=sent(p,0x0f).at(-1);
  assert.equal(r.payload.toString('hex'),'240101');assert.equal(r.flags,0x40);assert.equal(sent(p,0x6a).length,0);assert.equal(sent(p,0x08).length,0);
  await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});reply(p,r,[0]);const result=await start;
  assert.equal(result.requestedValue,1);assert.equal(result.physicalCompletionVerified,false);assert.equal(gimbal.activeOperation,null);
});
test('system calibration refuses implicit stop, malformed context and negative ACK',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  await assert.rejects(gimbal.appCommands.sendAutoCalibrationRequest({start:false}));await assert.rejects(gimbal.appCommands.sendAutoCalibrationRequest({timeoutMs:0}));assert.equal(p.frames().length,0);
  const bad=assert.rejects(gimbal.appCommands.getAutoCalibrationStatus(),{code:'RS4MINI_PROTOCOL_ERROR'});await until(()=>sent(p,0x10).length);reply(p,sent(p,0x10).at(-1),[0,37,1,3]);await bad;
  const nack=assert.rejects(gimbal.appCommands.sendAutoCalibrationRequest(),{code:'RS4MINI_DEVICE_ERROR'});await until(()=>sent(p,0x0f).length);reply(p,sent(p,0x0f).at(-1),[7]);await nack;
});
test('system calibration host cancellation and deadline do not invent firmware abort or replay',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const cancel=assert.rejects(gimbal.appCommands.sendAutoCalibrationRequest(),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p,0x0f).length);await gimbal.stop();await cancel;
  await assert.rejects(gimbal.appCommands.sendAutoCalibrationRequest({timeoutMs:5}),{code:'RS4MINI_RESPONSE_TIMEOUT'});
  assert.equal(sent(p,0x0f).length,2);assert.ok(sent(p,0x0f).every(r=>r.payload.toString('hex')==='240101'));assert.equal(gimbal.experimental.pending.size,0);
});
