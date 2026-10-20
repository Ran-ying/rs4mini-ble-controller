import test from 'node:test';import assert from 'node:assert/strict';
import {connected,until,gate} from './fakes.js';import {frame,crc16} from '../src/protocol.js';import {factoryResetSpec} from '../src/app-protocol.js';
const sent=p=>p.frames().filter(f=>f.commandId===0x13);
function reply(p,r,body,id=0x13){const b=frame(r.sequence,4,id,Buffer.from(body),0x80);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('factory reset HG724 source branch uses independent 010001 bodies',()=>{
 const a=factoryResetSpec({sourcePlatform:'HG724'});assert.equal(a.payload.toString('hex'),'010001');a.payload.fill(0);assert.equal(factoryResetSpec({sourcePlatform:'HG724'}).payload.toString('hex'),'010001');
});
