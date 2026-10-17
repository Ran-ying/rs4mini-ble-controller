import test from 'node:test';
import assert from 'node:assert/strict';
import {connected,until} from './fakes.js';
import {frame,crc16} from '../src/protocol.js';
import {standaloneSelection} from '../src/app-standalone.js';
const sent=(p,id)=>p.frames().filter(f=>f.commandId===id);
function reply(p,r,body,id=r.commandId){const b=frame(r.sequence,4,id,Buffer.from(body),0x80);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('standalone read retains actual input source and unsigned values without switching',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const read=gimbal.appCommands.getStandaloneTuning();await until(()=>sent(p,0x10).length);const r=sent(p,0x10).at(-1);
  assert.equal(r.payload.toString('hex'),'48504f514d4c4e');const data=[0,72,9,255];
  for(const row of standaloneSelection())data.push(row.index,9,255,255);
  reply(p,r,data);const result=await read;assert.equal(result.inputSourceRaw,255);assert.equal(result.values.length,6);assert.equal(result.values[0].rawValue,65535);assert.equal(result.values[0].withinSourceRange,false);assert.equal(result.activePresetVerified,false);assert.equal(sent(p,0x0f).length,0);
});
test('standalone filtered read snapshots selection and decodes little endian',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const options={axis:'roll',parameter:'smoothing'},read=gimbal.appCommands.getStandaloneTuning(options);options.axis='pitch';
  await until(()=>sent(p,0x10).length);const r=sent(p,0x10).at(-1);assert.equal(r.payload.toString('hex'),'484c');reply(p,r,[0,72,1,1,76,9,0x34,0x12]);const result=await read;assert.equal(result.inputSourceRaw,1);assert.equal(result.values[0].rawValue,4660);assert.equal(result.values[0].axis,'roll');
});
test('standalone source2 and value share exactly one ACK-owned packet',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const options={inputSource:2,axis:'pitch',parameter:'speed',value:100},write=gimbal.appCommands.setStandaloneTuning(options);options.value=5;options.inputSource=1;
  await until(()=>sent(p,0x0f).length);const r=sent(p,0x0f).at(-1);assert.equal(r.payload.toString('hex'),'48010250026400');assert.equal(sent(p,0x10).length,0);
  await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});reply(p,r,[0]);const result=await write;assert.equal(result.requestedInputSource,2);assert.equal(result.requestedValue,100);assert.equal(result.physicalCompletionVerified,false);assert.equal(result.activePresetVerified,false);assert.equal(sent(p,0x0f).length,1);
});
test('standalone rejects implicit sources, unrelated names and invalid values before frames',async t=>{
  const {gimbal,peripheral:p}=await connected(t);await assert.rejects(gimbal.appCommands.getStandaloneTuning());gimbal.appCommands.useProfile('ronin-2.2.2');
  const good={inputSource:2,axis:'yaw',parameter:'smoothing',value:30};
  for(const patch of [{inputSource:undefined},{inputSource:1},{inputSource:3},{inputSource:true},{axis:'pan'},{parameter:'acceleration'},{value:31},{value:-1},{value:true},{value:1.5},{index:72}])await assert.rejects(gimbal.appCommands.setStandaloneTuning({...good,...patch}));
  assert.equal(p.frames().length,0);
});
test('standalone rejects truncated replies and NACK, ignores wrong namespace',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const failed=assert.rejects(gimbal.appCommands.getStandaloneTuning({axis:'yaw',parameter:'speed'}),{code:'RS4MINI_PROTOCOL_ERROR'});await until(()=>sent(p,0x10).length);const r=sent(p,0x10).at(-1);reply(p,r,[0,72,1,2,81,2,1,0],0x32);assert.equal(gimbal.experimental.pending.size,1);reply(p,r,[0,72,1,2,81,2,1]);await failed;
  const nack=assert.rejects(gimbal.appCommands.setStandaloneTuning({inputSource:2,axis:'roll',parameter:'smoothing',value:0}),{code:'RS4MINI_DEVICE_ERROR'});await until(()=>sent(p,0x0f).length);reply(p,sent(p,0x0f).at(-1),[7]);await nack;assert.equal(gimbal.experimental.pending.size,0);
});
test('standalone cancel and timeout never replay or send source-only cleanup',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const options={inputSource:2,axis:'yaw',parameter:'speed',value:0};
  const cancel=assert.rejects(gimbal.appCommands.setStandaloneTuning(options),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p,0x0f).length);await gimbal.stop();await cancel;
  await assert.rejects(gimbal.appCommands.setStandaloneTuning({...options,timeoutMs:10}),{code:'RS4MINI_RESPONSE_TIMEOUT'});assert.equal(sent(p,0x0f).length,2);assert.ok(sent(p,0x0f).every(r=>r.payload.toString('hex')==='48010251020000'));assert.equal(gimbal.experimental.pending.size,0);assert.equal(gimbal.activeOperation,null);
});
