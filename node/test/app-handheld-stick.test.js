import test from 'node:test';
import assert from 'node:assert/strict';
import {connected,until} from './fakes.js';
import {frame,crc16} from '../src/protocol.js';
import {handheldStickNotification} from '../src/app-handheld-stick.js';
const body=()=>Buffer.from('0080ff7f0380aabb','hex');
const message=(payload=body(),flags=0)=>({sender:4,receiver:2,commandSet:4,commandId:0x57,flags,payload});
function incoming(p,payload=body(),flags=0,commandId=0x57,sequence=1){const b=frame(sequence,4,commandId,payload,flags);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('stick candidate preserves signed endpoints, unknown flags and trailing bytes',()=>{
 const r=handheldStickNotification(message());assert.equal(r.sourceStickX,-32768);assert.equal(r.sourceStickY,32767);assert.equal(r.rawStateWord,32771);assert.equal(r.unknownStateBits,32768);assert.equal(r.sourceTriggerPressed,true);assert.equal(r.sourceStickControlEnabled,true);assert.equal(r.bodyHex,'0080ff7f0380aabb');assert.equal(r.axisMappingVerified,false);assert.equal(r.deviceVerified,false);
});
test('stick bits are independent; short ACK encrypted and wrong endpoint messages are rejected',()=>{
 for(const [word,trigger,enabled] of [[0,false,false],[1,true,false],[2,false,true],[3,true,true],[65535,true,true]]) {const b=body();b.writeUInt16LE(word,4);const r=handheldStickNotification(message(b));assert.equal(r.sourceTriggerPressed,trigger);assert.equal(r.sourceStickControlEnabled,enabled);}
 for(const change of [{flags:128},{flags:1},{flags:true},{flags:256},{flags:-1},{sender:36},{receiver:4},{commandSet:0},{commandId:0x58},{payload:Buffer.alloc(5)},{payload:[]},{flags:undefined}])assert.equal(handheldStickNotification({...message(),...change}),null);
});
