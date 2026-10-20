import test from 'node:test';import assert from 'node:assert/strict';
import {connected,until,gate} from './fakes.js';import {frame,crc16} from '../src/protocol.js';import {handleWriteSpec} from '../src/app-handle.js';
const sent=p=>p.frames().filter(f=>f.commandId===0x35);
function reply(p,r,body,id=0x35){const b=frame(r.sequence,4,id,Buffer.from(body),0x80);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('handle setting writes one source field and fresh FF defaults each time',()=>{
 for(const [setting,value,hex] of [['dualChannelMode',0,'00ffffffffffffff'],['tiltDirection',1,'ff01ffffffffffff'],['panDirection',1,'ffff01ffffffffff']])assert.equal(handleWriteSpec({setting,value}).payload.toString('hex'),hex);
 const a=handleWriteSpec({setting:'panDirection',value:0});a.payload.fill(0);assert.equal(handleWriteSpec({setting:'dualChannelMode',value:1}).payload.toString('hex'),'01ffffffffffffff');
});
