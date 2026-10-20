import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {connected,until,gate} from './fakes.js';
import {frame,crc16} from '../src/protocol.js';
import {programStatusSubscriptionSpec,programStatusSubscriptionReply} from '../src/app-program-request.js';
const vectors=JSON.parse(readFileSync(new URL('./fixtures/program-subscription.json',import.meta.url)));
function incoming(p,r,body=Buffer.from([0]),flags=128,patch={}) {
 const b=frame(patch.sequence??r.sequence,4,patch.commandId??107,body,flags);b[4]=patch.sender??4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);
}
async function sent(p,count=1){await until(()=>p.frames().filter(f=>f.commandId===107).length===count);return p.frames().filter(f=>f.commandId===107).at(-1);}
test('six shared subscription request vectors retain source request types and exact tags',()=>{
 assert.equal(vectors.length,6);
 for(const v of vectors){const s=programStatusSubscriptionSpec(v.program,v.enabled);assert.equal(Buffer.from(s.payload).toString('hex'),v.bodyHex);assert.equal(s.requestType,v.requestType);assert.equal(s.requestedProgramCommandId,v.programCommand);}
 for(const enabled of [undefined,null,0,1,'true',{}])assert.throws(()=>programStatusSubscriptionSpec('track',enabled));
 for(const program of [98,'__proto__','delay'])assert.throws(()=>programStatusSubscriptionSpec(program,true));
});
test('subscription result reports opaque ACK without remote state or stream claims',()=>{
 const message={sender:4,receiver:2,commandSet:4,commandId:107,flags:128,payload:Buffer.from('0001620401020304','hex'),raw:Buffer.from([1])};
 for(const enabled of [true,false]){const r=programStatusSubscriptionReply(message,'track',enabled);assert.equal(r.bodyHex,'01620401020304');assert.equal(r.requestedEnabled,enabled);assert.equal(r.freshStatusVerified,false);assert.equal(r.notificationStreamVerified,false);assert.equal(r.remoteSubscriptionStateVerified,false);}
 for(const flags of [129,-128,384])assert.throws(()=>programStatusSubscriptionReply({...message,flags},'track',true),{code:'RS4MINI_PROTOCOL_ERROR'});
});
