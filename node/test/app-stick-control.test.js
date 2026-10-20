import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {connected,until,gate} from './fakes.js';import {frame,crc16} from '../src/protocol.js';import {handheldStickControlPayload,handheldStickControlReply} from '../src/app-handheld-stick.js';
const sent=p=>p.frames().filter(f=>f.commandId===88);
function reply(p,s,payload,flags=128,sender=4){const b=frame(s.sequence,4,s.commandId,Buffer.from(payload),flags);b[4]=sender;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
const message=(payload,flags=128)=>({sender:4,receiver:2,commandSet:4,commandId:88,flags,payload:Buffer.from(payload),raw:Buffer.alloc(0)});
test('stick control shared contracts keep ACK tail opaque and require boolean',()=>{
 const vectors=JSON.parse(fs.readFileSync(new URL('./fixtures/handheld-stick-control.json',import.meta.url)));assert.equal(vectors.length,3);
 for(const v of vectors){const r=handheldStickControlReply(message(Buffer.from(v.payloadHex,'hex')),v.enabled);assert.deepEqual([...handheldStickControlPayload(v.enabled)],[Number(v.enabled)]);for(const [k,value] of Object.entries(v.expected))assert.deepEqual(r[k],value);for(const k of ['deviceVerified','physicalCompletionVerified','readbackVerified','persistenceVerified','notificationAssociationVerified'])assert.equal(r[k],false);}
 for(const value of [undefined,null,0,1,'true',{},[]])assert.throws(()=>handheldStickControlPayload(value));
 for(let enc=1;enc<=7;enc++)for(const status of [0,7])assert.throws(()=>handheldStickControlReply(message([status],128|enc),true),{code:'RS4MINI_PROTOCOL_ERROR'});
 assert.throws(()=>handheldStickControlReply(message([7]),true),{code:'RS4MINI_DEVICE_ERROR'});assert.throws(()=>handheldStickControlReply(message([]),true),{code:'RS4MINI_PROTOCOL_ERROR'});
});
