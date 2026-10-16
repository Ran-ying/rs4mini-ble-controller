import test from 'node:test';
import assert from 'node:assert/strict';
import {connected,until} from './fakes.js';
import {frame,crc16} from '../src/protocol.js';
import {settingsWrite,decodeSettings} from '../src/app-settings.js';
const sent=(p,id)=>p.frames().filter(f=>f.commandId===id);
function reply(p,r,body){const b=frame(r.sequence,4,r.commandId,Buffer.from(body),0x80);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('mode field update preserves other axes and opaque low bits for every byte',()=>{
  for(let raw=0;raw<256;raw++){
    const {requestedRawValue:value}=settingsWrite('followSpeed',{yaw:'custom'},raw);
    assert.equal(value&63,raw&63);assert.equal(value>>>6,0);
  }
  assert.equal(settingsWrite('followSpeed',{pitch:'high'},0x9b).requestedRawValue,0x9f);
  assert.deepEqual(decodeSettings({parameters:[{rawHex:'9b'}]},'rcSpeed').settings,{pitch:'middle',roll:'low',yaw:'middle'});
});
test('six mode groups read their named source register and expose opaque bits',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  for(const [method,parameter,index] of [['getFollowSettings','speed',65],['getFollowSettings','acceleration',71],['getFollowSettings','deadZone',66],['getRcSettings','speed',67],['getRcSettings','deadZone',68],['getRcSettings','smoothing',69]]){
    const n=sent(p,0x10).length,read=gimbal.appCommands[method]({parameter});await until(()=>sent(p,0x10).length>n);const r=sent(p,0x10).at(-1);assert.deepEqual([...r.payload],[index]);reply(p,r,[0,index,9,0x9b]);const result=await read;assert.equal(result.settings.pitch,'middle');assert.equal(result.unknownBits,3);assert.equal(result.parameters[0].headerByte,9);
  }
});
test('mode write uses fresh read and copied patch, retains ownership to ACK',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const options={parameter:'speed',yaw:'custom'},write=gimbal.appCommands.setFollowSettings(options);options.yaw='high';
  await until(()=>sent(p,0x10).length);reply(p,sent(p,0x10).at(-1),[0,65,1,255]);await until(()=>sent(p,0x0f).length);const r=sent(p,0x0f).at(-1);assert.equal(r.payload.toString('hex'),'41013f');
  await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});reply(p,r,[0]);const result=await write;assert.equal(result.previousRawValue,255);assert.equal(result.requestedRawValue,63);assert.equal(result.requestedSettings.yaw,'custom');assert.equal(result.physicalCompletionVerified,false);
});
test('mode cancellation before read reply prevents all writes and clears ownership',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const failed=assert.rejects(gimbal.appCommands.setRcSettings({parameter:'smoothing',roll:'middle'}),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p,0x10).length);const r=sent(p,0x10).at(-1);await gimbal.stop();reply(p,r,[0,69,1,0]);await failed;assert.equal(sent(p,0x0f).length,0);assert.equal(gimbal.experimental.pending.size,0);assert.equal(gimbal.activeOperation,null);
});
test('invalid modes never stop/write, malformed read blocks write and ACK deadline never replays',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  for(const o of [{parameter:{toString:()=> 'speed'},yaw:'low'},{parameter:'speed'},{parameter:'speed',yaw:1},{parameter:'PF',yaw:'low'},{parameter:'speed',pan:'low'},{parameter:'speed',yaw:'medium'}])await assert.rejects(gimbal.appCommands.setFollowSettings(o));assert.equal(p.frames().length,0);
  const bad=assert.rejects(gimbal.appCommands.setRcSettings({parameter:'deadZone',pitch:'low'}),{code:'RS4MINI_PROTOCOL_ERROR'});await until(()=>sent(p,0x10).length);reply(p,sent(p,0x10).at(-1),[0,68,1]);await bad;assert.equal(sent(p,0x0f).length,0);
  const count=sent(p,0x10).length,timeout=assert.rejects(gimbal.appCommands.setRcSettings({parameter:'speed',yaw:'low',timeoutMs:30}),{code:'RS4MINI_RESPONSE_TIMEOUT'});await until(()=>sent(p,0x10).length>count);reply(p,sent(p,0x10).at(-1),[0,67,1,0]);await timeout;assert.equal(sent(p,0x0f).length,1);assert.equal(gimbal.experimental.pending.size,0);
});
