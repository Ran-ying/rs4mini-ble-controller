import test from 'node:test';
import assert from 'node:assert/strict';
import { connected, until } from './fakes.js';
import { frame, crc16 } from '../src/protocol.js';
import { parseDumlFrame } from '../src/telemetry.js';
import { rs3AbsoluteFrame, rs3RateFrame, researchSleepFrame, decodeResearchStatus } from '../src/experimental-protocol.js';

function incoming(sequence, set, id, payload = [], { flags = 0x80, sender = 4, receiver = 2 } = {}) {
  const packet = frame(sequence, set, id, Buffer.from(payload), flags);
  packet[4] = sender; packet[5] = receiver; packet.writeUInt16LE(crc16(packet.subarray(0, -2)), packet.length - 2);
  return packet;
}
test('RS research frames preserve source axis order, omitted-axis mask and model differences', () => {
  assert.equal(parseDumlFrame(rs3AbsoluteFrame(1, { pan: 45, parameterByte: 20 })).payload.toString('hex'), 'c201000000000d14');
  assert.equal(parseDumlFrame(rs3AbsoluteFrame(1, { tilt: -3, parameterByte: 20 })).payload.toString('hex'), '00000000e2ff0714');
  assert.equal(parseDumlFrame(rs3RateFrame(1, { pan: 2 })).payload.toString('hex'), '14000000000080');
  assert.equal(parseDumlFrame(rs3RateFrame(1, {}, true)).payload.toString('hex'), '00000000000000');
  assert.equal(parseDumlFrame(researchSleepFrame(1, 'rs3', true)).payload.toString('hex'), '230101');
  assert.equal(parseDumlFrame(researchSleepFrame(1, 'rs3mini', true)).payload.toString('hex'), '230111');
  assert.throws(() => rs3AbsoluteFrame(1, { pan: 1 }), /parameterByte/);
  assert.throws(() => rs3AbsoluteFrame(1, { pan: 181, parameterByte: 20 }), /pan/);
  assert.throws(() => rs3RateFrame(1, { pan: Infinity }), /pan/);
});
test('experimental controls require explicit profile and reject options before writing', async t => {
  const { gimbal, peripheral } = await connected(t);
  await assert.rejects(gimbal.experimental.absolute({ pan: 0, parameterByte: 20 }), /explicit/);
  assert.throws(() => gimbal.experimental.useProfile('rs4mini'), /explicit/);
  gimbal.experimental.useProfile('rs3mini');
  await assert.rejects(gimbal.experimental.absolute({ pan: 0, parameterByte: 20 }), /only/);
  await assert.rejects(gimbal.experimental.setSleep({ asleep: true, camera: 1 }), /invalid/);
  await assert.rejects(gimbal.experimental.query({ kind: 'calibrate' }), /query kind/);
  assert.equal(peripheral.frames().length, 0);
});
test('queries match sequence, endpoint, command and response bit without taking motion ownership', async t => {
  const { gimbal, peripheral } = await connected(t); gimbal.experimental.useProfile('rs3');
  const query = gimbal.experimental.query({ kind: 'type', timeoutMs: 100 });
  await until(() => peripheral.frames().length === 1);
  const sent = peripheral.frames()[0], seq = sent.sequence;
  for (const packet of [incoming(seq + 1, 4, 0x1c), incoming(seq, 4, 2), incoming(seq, 4, 0x1c, [], { sender: 5 }), incoming(seq, 4, 0x1c, [], { flags: 0 })])
    peripheral.rx.emit('data', packet, true);
  assert.equal(gimbal.experimental.pending.size, 1);
  gimbal.sequence = seq;
  await gimbal.setVelocity({ pan: .05 });
  assert.notEqual(peripheral.frames()[1].sequence, seq);
  peripheral.rx.emit('data', incoming(seq, 4, 0x1c, [0, 42]), true);
  assert.equal((await query).payload[1], 42); assert.equal(gimbal.experimental.pending.size, 0);
  await gimbal.stop();
});
test('query timeout and disconnection dispose pending response state', async t => {
  const { gimbal, peripheral } = await connected(t); gimbal.experimental.useProfile('rs3');
  await assert.rejects(gimbal.experimental.query({ kind: 'position', timeoutMs: 10 }), { code: 'RS4MINI_RESPONSE_TIMEOUT' });
  assert.equal(gimbal.experimental.pending.size, 0);
  const query = gimbal.experimental.query({ kind: 'version' });
  const rejected = assert.rejects(query, { code: 'RS4MINI_DISCONNECTED' });
  await peripheral.disconnectAsync(); await rejected; assert.equal(gimbal.experimental.pending.size, 0);
});
test('absolute experiment owns its observation interval, cancels and stops', async t => {
  const { gimbal, peripheral } = await connected(t); gimbal.experimental.useProfile('rs3');
  const operation = gimbal.experimental.absolute({ pan: 2, parameterByte: 20, observeMs: 10000 });
  const rejected = assert.rejects(operation, { code: 'RS4MINI_MOVE_CANCELLED' });
  await until(() => peripheral.frames().some(item => item.commandId === 0x14));
  await assert.rejects(gimbal.moveFor({ durationMs: 0 }), { code: 'RS4MINI_BUSY' });
  await gimbal.stop(); await rejected;
  assert.equal(peripheral.frames().at(-1).commandId, 1);
});
test('native rate experiments always release takeover before normal neutrals', async t => {
  const { gimbal, peripheral } = await connected(t); gimbal.experimental.useProfile('rs3');
  const operation = gimbal.experimental.rateFor({ pan: 2, durationMs: 10000 });
  const rejected = assert.rejects(operation, { code: 'RS4MINI_MOVE_CANCELLED' });
  await until(() => peripheral.frames().length > 0); await gimbal.stop(); await rejected;
  const frames = peripheral.frames();
  assert.equal(frames[0].commandId, 0x0c); assert.equal(frames[0].payload[6], 0x80);
  assert.equal(frames.at(-4).commandId, 0x0c); assert.equal(frames.at(-4).payload.toString('hex'), '00000000000000');
  assert(frames.slice(-3).every(item => item.commandId === 1));
});
test('sleep experiment sends neutrals before sleep and makes no false completion claim', async t => {
  const { gimbal, peripheral } = await connected(t); gimbal.experimental.useProfile('rs3mini');
  const result = await gimbal.experimental.setSleep({ asleep: true });
  assert.equal(peripheral.frames().length, 4);
  assert.equal(peripheral.frames().at(-1).commandId, 0x0f);
  assert.equal(result.physicalCompletionVerified, false);
});
test('status decoders require known endpoints and preserve profile uncertainty', async t => {
  const { gimbal, peripheral } = await connected(t); gimbal.experimental.useProfile('rs3mini');
  const payload = Buffer.alloc(21); payload.writeInt32LE(-123, 1); payload[20] = 67;
  const battery = incoming(1, 0x0d, 2, payload, { sender: 0xe5 });
  const message = parseDumlFrame(battery);
  assert.equal(decodeResearchStatus(message, 'rs3mini').batteryPercent, 67);
  assert.equal(decodeResearchStatus(message, 'rs3').batteryPercent, null);
  assert.equal(decodeResearchStatus({ ...message, sender: 4 }, 'rs3mini'), null);
  peripheral.rx.emit('data', battery, true);
  const status = gimbal.experimental.status; status['battery-status'].batteryPercent = 0;
  assert.equal(gimbal.experimental.status['battery-status'].batteryPercent, 67);
  assert.equal(gimbal.experimental.status['battery-status'].deviceVerified, false);
  peripheral.rx.emit('data', incoming(1, 4, 0x27, [0, 0, 0, 0, 1]), true);
  assert.equal(gimbal.experimental.status.sleep.asleep, true);
  const malformed = parseDumlFrame(incoming(1, 4, 0x66, [1, 0x22, 2, 0], { sender: 0xe5 }));
  assert.equal(decodeResearchStatus(malformed, 'rs3mini'), null);
  await gimbal.disconnect(); assert.deepEqual(gimbal.experimental.status, {});
});
