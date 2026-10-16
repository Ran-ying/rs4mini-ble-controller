import test from 'node:test';
import assert from 'node:assert/strict';
import { connected, gate, until } from './fakes.js';
import { frame, crc16 } from '../src/protocol.js';
import { DumlStreamDecoder } from '../src/telemetry.js';
import { calibrationRecords } from '../src/app-calibration.js';
function incoming(p, sequence, flags, payload, mutate = () => {}) {
  const packet = frame(sequence, 4, 0x6e, Buffer.from(payload), flags);
  packet[4] = 4; packet[5] = 2; mutate(packet);
  packet.writeUInt16LE(crc16(packet.subarray(0,-2)), packet.length-2); p.rx.emit('data',packet,true);
}
const queries = p => p.frames().filter(f => f.commandId === 0x6e);
const requests = p => p.frames().filter(f => f.commandId === 0x6a);
test('auto-tune source request has no ACK and never claims firmware completion', async t => {
  const { gimbal, peripheral: p } = await connected(t);
  await assert.rejects(gimbal.appCommands.sendAutoTuneRequest({start:true}), /explicit/);
  gimbal.appCommands.useProfile('ronin-2.2.2');
  for (const start of [true,false]) {
    const result = await gimbal.appCommands.sendAutoTuneRequest({start});
    assert.equal(requests(p).at(-1).payload.toString('hex'), start ? '000101' : '000100');
    assert.equal(requests(p).at(-1).flags, 0);
    assert.equal(result.sent,true); assert.equal(result.acknowledged,false); assert.equal(result.acknowledgementRequested,false);
    assert.equal(result.physicalCompletionVerified,false); assert.equal(gimbal.experimental.pending.size,0);
  }
  const before = p.frames().length;
  for (const options of [{start:1},{start:null},{start:true,timeoutMs:1000},{}]) await assert.rejects(gimbal.appCommands.sendAutoTuneRequest(options));
  assert.equal(p.frames().length,before);
});
test('no-ACK request owns in-flight write; stop cancels host work without replay', async t => {
  const { gimbal, peripheral: p } = await connected(t);
  gimbal.appCommands.useProfile('ronin-2.2.2');
  const blocked=gate(), started=gate(), original=p.tx.writeAsync.bind(p.tx);
  p.tx.writeAsync=async (chunk,mode) => {
    if (new DumlStreamDecoder().push(chunk)[0]?.commandId===0x6a) { started.resolve(); await blocked.promise; }
    return original(chunk,mode);
  };
  const rejected=assert.rejects(gimbal.appCommands.sendAutoTuneRequest({start:true}),{code:'RS4MINI_OPERATION_CANCELLED'});
  await started.promise; await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});
  const stopping=gimbal.stop(); blocked.resolve(); await stopping; await rejected;
  assert.equal(requests(p).length,1); assert.equal(gimbal.experimental.pending.size,0); assert.equal(gimbal.activeOperation,null);
});
test('calibration query separates status code from records and checks correlation', async t => {
  const { gimbal, peripheral:p }=await connected(t); gimbal.appCommands.useProfile('ronin-2.2.2');
  const read=gimbal.appCommands.queryCalibrationStatus(); await until(()=>queries(p).length);
  const request=queries(p).at(-1); assert.equal(request.flags,0x40); assert.equal(request.payload.length,0);
  let done=false; read.then(()=>{done=true;});
  incoming(p,request.sequence+1,0x80,[0,0,2,1,40]);
  incoming(p,request.sequence,0x80,[0,0,2,1,40],data=>{data[4]=0x24;});
  await new Promise(resolve=>setImmediate(resolve)); assert.equal(done,false);
  incoming(p,request.sequence,0x80,[0,0,2,1,40]); const result=await read;
  assert.equal(result.calibration.state,'Processing'); assert.equal(result.calibration.percent,40);
  assert.equal(gimbal.appCommands.calibrationStatus,null); // Query ACK does not populate an unsequenced notification cache.
});
test('passive records keep unknown fields, clone state, and isolate observer failure', async t => {
  const { gimbal, peripheral:p }=await connected(t); gimbal.appCommands.useProfile('ronin-2.2.2');
  const errors=[]; gimbal.onError=error=>errors.push(error);
  gimbal.onAppStatus=status=>{status.records[0].rawHex='changed'; throw new Error('observer');};
  incoming(p,1,0,[1,0,0,3,2,100,99,7,1,44]);
  const first=gimbal.appCommands.calibrationStatus; assert.equal(first.state,'Complete'); assert.equal(first.percent,100);
  assert.equal(first.records[1].rawHex,'026463'); assert.equal(first.records[2].rawHex,'2c'); assert.equal(errors.length,1);
  first.records.length=0; assert.equal(gimbal.appCommands.calibrationStatus.records.length,3);
  incoming(p,2,0,[0,2,77,255]);
  assert.equal(gimbal.appCommands.calibrationStatus.state,null); assert.equal(gimbal.appCommands.calibrationStatus.rawPercent,255);
  assert.equal(gimbal.appCommands.calibrationStatus.percent,null);
});
test('malformed, wrong-endpoint, ACK and unknown-only packets do not reset passive status', async t => {
  const { gimbal, peripheral:p }=await connected(t); gimbal.appCommands.useProfile('ronin-2.2.2');
  incoming(p,1,0,[0,2,1,20]);
  for (const body of [[0,128,...Array(128).fill(1)],[],[0],[0,1,2],[0,2,1],[1,0],[2,2,2,0],[0,2,2,100,4]]) incoming(p,2,0,body);
  incoming(p,3,0x80,[0,0,2,2,100]); incoming(p,4,0,[0,2,2,100],data=>{data[5]=4;});
  assert.equal(gimbal.appCommands.calibrationStatus.percent,20);
  gimbal.experimental.useProfile('rs3'); assert.equal(gimbal.appCommands.calibrationStatus,null);
  incoming(p,5,0,[0,2,1,50]); assert.equal(gimbal.appCommands.calibrationStatus,null);
  gimbal.appCommands.useProfile('ronin-2.2.2'); incoming(p,6,0,[0,2,1,60]);
  p.emit('disconnect'); assert.equal(gimbal.appCommands.calibrationStatus,null);
});
test('query ACK-only success is empty, malformed/NACK/timeouts reject without synthetic completion', async t => {
  const { gimbal, peripheral:p }=await connected(t); gimbal.appCommands.useProfile('ronin-2.2.2');
  for (const [payload,code] of [[[0],null],[[0,0,1,2],'RS4MINI_PROTOCOL_ERROR'],[[7],'RS4MINI_DEVICE_ERROR']]) {
    const count=queries(p).length, read=gimbal.appCommands.queryCalibrationStatus();
    const checked=code ? assert.rejects(read,{code}) : read;
    await until(()=>queries(p).length>count); incoming(p,queries(p).at(-1).sequence,0x80,payload);
    const result=await checked; if(!code) { assert.equal(result.calibration.rawState,null); assert.equal(result.calibration.percent,null); }
  }
  await assert.rejects(gimbal.appCommands.queryCalibrationStatus({timeoutMs:5}),{code:'RS4MINI_RESPONSE_TIMEOUT'});
  assert.equal(gimbal.experimental.pending.size,0);
});
test('record decoder uses last complete status and never invents a default for unknown-only body',()=>{
  const result=calibrationRecords(Buffer.from([0,2,1,10,0,2,3,20]));
  assert.equal(result.state,'Failure'); assert.equal(result.percent,20); assert.equal(result.records.length,2);
  assert.equal(calibrationRecords(Buffer.from([1,0])).rawState,null);
  assert.equal(calibrationRecords(Buffer.from([0,2,255,0])).state,'UnKnown');
});
