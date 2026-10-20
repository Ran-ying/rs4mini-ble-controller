import test from 'node:test';
import assert from 'node:assert/strict';
import { connected,until } from './fakes.js';
import { frame,crc16 } from '../src/protocol.js';
import { systemCalibrationFields } from '../src/app-system-calibration.js';
const sent=(p,id)=>p.frames().filter(f=>f.commandId===id);
function reply(p,r,body,id=r.commandId) {
  const packet=frame(r.sequence,4,id,Buffer.from(body),0x80);packet[4]=4;packet[5]=2;
  packet.writeUInt16LE(crc16(packet.subarray(0,-2)),packet.length-2);p.rx.emit('data',packet,true);
}
test('system calibration maps source enum beyond input range without sharing auto-tune states',()=>{
  assert.deepEqual([0,1,2,3].map(v=>systemCalibrationFields(v).state),['DEFAULT','START','FAIL','SUCCESS']);
  assert.deepEqual(systemCalibrationFields(3),{rawValue:3,state:'SUCCESS'});
});
test('unknown system calibration values stay raw rather than default or array index errors',()=>{
  for (let value=4;value<256;value++)assert.deepEqual(systemCalibrationFields(value),{rawValue:value,state:null});
  assert.throws(()=>systemCalibrationFields(-1));assert.throws(()=>systemCalibrationFields(true));
});
