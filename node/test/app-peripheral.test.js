import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {connected,until} from './fakes.js';import {frame,crc16} from '../src/protocol.js';import {peripheralNotification} from '../src/app-peripheral.js';
const vectors=JSON.parse(readFileSync(new URL('./fixtures/peripheral-status.json',import.meta.url)));
const message=payload=>({sender:4,receiver:2,commandSet:4,commandId:102,flags:0,payload:Buffer.from(payload,'hex')});
function incoming(p,body,patch={}){const b=frame(patch.sequence??5,4,patch.commandId??102,Buffer.from(body,'hex'),patch.flags??0);b[4]=patch.sender??4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('all six peripheral contracts preserve every source getter and collision',()=>{
 for(const v of vectors){const r=peripheralNotification(message(v.bodyHex));for(const [key,value] of Object.entries(v.expected))assert.deepEqual(r[key],value,v.name);assert.equal(r.referenceFrameVerified,false);}
 assert.equal(peripheralNotification(message(vectors[0].bodyHex)).records.flatMap(r=>r.sourceViews).length,43);
});
test('wrong envelope encrypted ACK invalid flags and malformed records are rejected',()=>{
 const m=message('0122020a00');for(const patch of [{sender:36},{receiver:4},{commandSet:0},{commandId:107},{flags:128},{flags:1},{flags:-128},{flags:256},{flags:false},{payload:null}])assert.equal(peripheralNotification({...m,...patch}),null);
 for(const body of ['','0122','01220200','012280'+'00'.repeat(128)])assert.equal(peripheralNotification(message(body)),null);
});
test('every valid signed length is decoded without silent drops or missing zeros',()=>{
 for(let n=0;n<128;n++){const p=Buffer.concat([Buffer.from([1,0,n]),Buffer.alloc(n,255)]);const r=peripheralNotification({...message(''),payload:p});assert.equal(r.records[0].sourceInt32,n===0?0:n===3?16777215:-1);}
 assert.deepEqual(peripheralNotification(message('01')).records,[]);
});
test('peripheral request-type notification does not complete a query or release ownership',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const query=gimbal.appCommands.getFollowSensitivity();await until(()=>p.frames().some(f=>f.commandId===16));const q=p.frames().find(f=>f.commandId===16),owner=gimbal.activeOperation;
 incoming(p,'0122020a00',{sequence:q.sequence,flags:64});assert.equal(gimbal.experimental.pending.size,1);assert.equal(gimbal.activeOperation,owner);assert.equal(p.frames().length,1);
 incoming(p,'00960100',{sequence:q.sequence,flags:128,commandId:16});assert.equal((await query).mode,0);
});
