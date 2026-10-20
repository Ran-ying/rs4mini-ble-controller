import test from 'node:test';
import assert from 'node:assert/strict';
import { connected,until } from './fakes.js';
import { frame,crc16 } from '../src/protocol.js';
import { balanceFields } from '../src/app-balance.js';
const sent=(p,id)=>p.frames().filter(f=>f.commandId===id);
function reply(p,r,body,id=r.commandId) {
  const packet=frame(r.sequence,4,id,Buffer.from(body),0x80);packet[4]=4;packet[5]=2;
  packet.writeUInt16LE(crc16(packet.subarray(0,-2)),packet.length-2);p.rx.emit('data',packet,true);
}
test('balance fields keep zero invalid and separate testing/error from axis outcomes',()=>{
  const empty=balanceFields(0);assert.equal(empty.state,'DEFAULT');assert.equal(empty.axisFieldsValid,false);assert.equal(empty.axisResults.roll.result,null);
  const finished=balanceFields(0x9b);assert.equal(finished.state,'FINISH');assert.deepEqual(Object.values(finished.axisResults).map(r=>r.result),['PASS','MARGINAL','FAIL']);
  assert.equal(balanceFields(64).state,'TESTING');assert.equal(balanceFields(255).state,'ERROR');assert.equal(balanceFields(255).axisResults.yaw.result,'FAIL');
});
test('balance fields retain every raw byte and independently preserve invalid axes',()=>{
  for (let value=0;value<256;value++)assert.equal(balanceFields(value).rawValue,value);
  const partial=balanceFields(0x90);assert.equal(partial.axisResults.roll.result,'PASS');assert.equal(partial.axisResults.pitch.result,null);assert.equal(partial.axisFieldsValid,false);
  assert.throws(()=>balanceFields(256));assert.throws(()=>balanceFields(true));
});
