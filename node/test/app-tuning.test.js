import test from 'node:test';
import assert from 'node:assert/strict';
import {connected,until} from './fakes.js';
import {frame,crc16} from '../src/protocol.js';
import {tuningSelection} from '../src/app-tuning.js';
const sent=(p,id)=>p.frames().filter(f=>f.commandId===id);
function reply(p,r,body,id=r.commandId){const b=frame(r.sequence,4,id,Buffer.from(body),0x80);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('follow numeric read uses named two-byte context, little-endian values and filter snapshot',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const options={axis:'pitch',parameter:'speed'},read=gimbal.appCommands.getFollowTuning(options);options.axis='yaw';
  await until(()=>sent(p,0x10).length);const r=sent(p,0x10).at(-1);assert.equal(r.payload.toString('hex'),'03');
  reply(p,r,[0,3,9,0x34,0x12]);const result=await read;assert.equal(result.values[0].rawValue,4660);assert.equal(result.values[0].withinSourceRange,false);assert.equal(result.values[0].axis,'pitch');assert.equal(result.values[0].headerByte,9);assert.equal(result.activePresetVerified,false);
});
test('RC default query retains mixed widths and unsigned out-of-range feedback',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const read=gimbal.appCommands.getRcTuning();await until(()=>sent(p,0x10).length);const r=sent(p,0x10).at(-1),rows=tuningSelection('rc');
  assert.equal(r.payload.toString('hex'),'2a2b291b281a092708');
  const data=[0];for(const [i,row] of rows.entries()){const value=i===0?65535:i===3?255:30;data.push(row.index,9,...Array.from({length:row.size},(_,b)=>(value>>>(8*b))&255));}
  reply(p,r,data);const result=await read;assert.equal(result.values.length,9);assert.equal(result.values[0].rawValue,65535);assert.equal(result.values[3].rawValue,255);assert.equal(result.values[3].withinSourceRange,false);assert.equal(result.values[8].withinSourceRange,true);
});
test('numeric setters encode widths, copy values and hold ownership through ACK only',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  for(const [method,options,hex] of [['setFollowTuning',{axis:'pitch',parameter:'speed',value:100},'03026400'],['setRcTuning',{axis:'yaw',parameter:'deadZone',value:100},'1a0164'],['setRcTuning',{axis:'pitch',parameter:'smoothing',value:30},'09021e00']]){
    const n=sent(p,0x0f).length,value=options.value,write=gimbal.appCommands[method](options);options.value=1;await until(()=>sent(p,0x0f).length>n);const r=sent(p,0x0f).at(-1);assert.equal(r.payload.toString('hex'),hex);
    await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});reply(p,r,[0]);const result=await write;assert.equal(result.requestedValue,value);assert.equal(result.physicalCompletionVerified,false);assert.equal(result.activePresetVerified,false);
  }
  assert.equal(sent(p,0x31).length,0);assert.equal(sent(p,0x10).length,0);assert.ok(sent(p,0x0f).every(r=>r.payload[0]!==72));
});
test('numeric validation rejects source bounds, booleans, arbitrary indexes and create aliases before frames',async t=>{
  const {gimbal,peripheral:p}=await connected(t);await assert.rejects(gimbal.appCommands.getFollowTuning());gimbal.appCommands.useProfile('ronin-2.2.2');
  for(const o of [{axis:'pitch',parameter:'speed',value:0},{axis:'pitch',parameter:'speed',value:101},{axis:'pan',parameter:'speed',value:100},{axis:'pitch',parameter:'speed',value:true},{axis:'pitch',parameter:'speed',value:1.5},{axis:'pitch',parameter:'speed',value:1,index:72}])await assert.rejects(gimbal.appCommands.setFollowTuning(o));
  await assert.rejects(gimbal.appCommands.setRcTuning({axis:'pitch',parameter:'smoothing',value:31}));await assert.rejects(gimbal.appCommands.getRcTuning({parameter:'gimbal_create_max_speed_pitch'}));assert.equal(p.frames().length,0);
});
test('numeric read rejects truncation and wrong namespace, setter rejects NACK',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const failed=assert.rejects(gimbal.appCommands.getFollowTuning({axis:'roll',parameter:'deadZone'}),{code:'RS4MINI_PROTOCOL_ERROR'});await until(()=>sent(p,0x10).length);const r=sent(p,0x10).at(-1);reply(p,r,[0,13,1,1,0],0x32);assert.equal(gimbal.experimental.pending.size,1);reply(p,r,[0,13,1,1]);await failed;
  const nack=assert.rejects(gimbal.appCommands.setRcTuning({axis:'yaw',parameter:'speed',value:0}),{code:'RS4MINI_DEVICE_ERROR'});await until(()=>sent(p,0x0f).length);reply(p,sent(p,0x0f).at(-1),[7]);await nack;assert.equal(gimbal.experimental.pending.size,0);
});
test('numeric cancellation/ACK deadline clear pending without replay or preset writes',async t=>{
  const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');
  const cancel=assert.rejects(gimbal.appCommands.setRcTuning({axis:'yaw',parameter:'speed',value:0}),{code:'RS4MINI_OPERATION_CANCELLED'});await until(()=>sent(p,0x0f).length);await gimbal.stop();await cancel;
  await assert.rejects(gimbal.appCommands.setFollowTuning({axis:'pitch',parameter:'deadZone',value:0,timeoutMs:10}),{code:'RS4MINI_RESPONSE_TIMEOUT'});
  assert.equal(sent(p,0x0f).length,2);assert.equal(gimbal.experimental.pending.size,0);assert.equal(gimbal.activeOperation,null);assert.ok(sent(p,0x0f).every(r=>![65,66,67,68,69,71,72].includes(r.payload[0])));
});
