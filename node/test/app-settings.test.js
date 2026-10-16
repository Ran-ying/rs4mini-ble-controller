import test from 'node:test';
import assert from 'node:assert/strict';
import { connected, until } from './fakes.js';
import { frame, crc16 } from '../src/protocol.js';
const commands = (p, id) => p.frames().filter(f => f.commandId === id);
function reply(p, sent, payload) {
  const packet = frame(sent.sequence, 4, sent.commandId, Buffer.from(payload), 0x80);
  packet[4] = 4; packet[5] = 2;
  packet.writeUInt16LE(crc16(packet.subarray(0, -2)), packet.length - 2);
  p.rx.emit('data', packet, true);
}
test('custom follow transaction reads fresh high-index flags and preserves other axes', async t => {
  const { gimbal, peripheral: p } = await connected(t);
  gimbal.appCommands.useProfile('ronin-2.2.2');
  const options = { enabled: true, pitch: false }, write = gimbal.appCommands.setCustomFollowSettings(options);
  options.yaw = false; options.enabled = false;
  await until(() => commands(p, 0x10).length);
  const read = commands(p, 0x10).at(-1); assert.equal(read.payload.toString('hex'), '84');
  await assert.rejects(gimbal.setVelocity({ pan: .1 }), { code: 'RS4MINI_BUSY' });
  reply(p, read, [0,132,9,14]);
  await until(() => commands(p, 0x0f).length);
  const set = commands(p, 0x0f).at(-1);
  assert.equal(set.payload.toString('hex'), '84010d');
  assert.notEqual(set.sequence, read.sequence);
  reply(p, set, [0]);
  const result = await write;
  assert.equal(result.previousRawValue, 14); assert.equal(result.requestedRawValue, 13);
  assert.deepEqual(result.requestedSettings, { enabled: true, pitch: false });
  assert.equal(result.physicalCompletionVerified, false);
});
test('motor enable has inverted bit0 and preserves unknown bits in index35', async t => {
  const { gimbal, peripheral: p } = await connected(t); gimbal.appCommands.useProfile('ronin-2.2.2');
  const write = gimbal.appCommands.setMotorSettings({ enabled: true, forbidSelfie: true, roll360: false });
  await until(() => commands(p, 0x10).length); reply(p, commands(p, 0x10).at(-1), [0,35,1,207]);
  await until(() => commands(p, 0x0f).length);
  assert.equal(commands(p, 0x0f).at(-1).payload.toString('hex'), '23019e');
  reply(p, commands(p, 0x0f).at(-1), [0]); assert.equal((await write).requestedRawValue, 158);
  const read = gimbal.appCommands.getMotorSettings(); await until(() => commands(p, 0x10).length === 2);
  reply(p, commands(p, 0x10).at(-1), [0,35,1,158]); const result = await read;
  assert.deepEqual(result.settings, { enabled: true, forbidSelfie: true, forbidVertical: false, roll360: false });
  assert.equal(result.unknownBits, 142);
});
test('read rejection, truncation and unsupported custom flags never lead to a setting write', async t => {
  const { gimbal, peripheral: p } = await connected(t); gimbal.appCommands.useProfile('ronin-2.2.2');
  for (const [payload, code] of [[[7], 'RS4MINI_DEVICE_ERROR'], [[0,132,1], 'RS4MINI_PROTOCOL_ERROR'], [[0,132,1,128], 'RS4MINI_UNSUPPORTED_VALUE']]) {
    const count = commands(p, 0x10).length;
    const failure = assert.rejects(gimbal.appCommands.setCustomFollowSettings({ yaw: true }), { code });
    await until(() => commands(p, 0x10).length > count); reply(p, commands(p, 0x10).at(-1), payload); await failure;
  }
  assert.equal(commands(p, 0x0f).length, 0); assert.equal(gimbal.experimental.pending.size, 0);
});
test('stop during settings read prevents write and ignores a late read response', async t => {
  const { gimbal, peripheral: p } = await connected(t); gimbal.appCommands.useProfile('ronin-2.2.2');
  const rejected = assert.rejects(gimbal.appCommands.setMotorSettings({ enabled: false }), { code: 'RS4MINI_OPERATION_CANCELLED' });
  await until(() => commands(p, 0x10).length); const old = commands(p, 0x10).at(-1);
  await gimbal.stop(); await rejected; reply(p, old, [0,35,1,0]);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(commands(p, 0x0f).length, 0); assert.equal(gimbal.experimental.pending.size, 0);
});
test('settings transaction uses one deadline across read and ACK and never retries', async t => {
  const { gimbal, peripheral: p } = await connected(t); gimbal.appCommands.useProfile('ronin-2.2.2');
  const rejected = assert.rejects(gimbal.appCommands.setCustomFollowSettings({ roll: true, timeoutMs: 100 }), { code: 'RS4MINI_RESPONSE_TIMEOUT' });
  await until(() => commands(p, 0x10).length);
  await new Promise(resolve => setTimeout(resolve, 30)); reply(p, commands(p, 0x10).at(-1), [0,132,1,0]);
  await until(() => commands(p, 0x0f).length); await rejected;
  assert.equal(commands(p, 0x10).length, 1); assert.equal(commands(p, 0x0f).length, 1);
  assert.equal(gimbal.activeOperation, null); assert.equal(gimbal.experimental.pending.size, 0);
});
test('invalid setting fields are rejected before any frame and unknown read flags remain visible', async t => {
  const { gimbal, peripheral: p } = await connected(t); gimbal.appCommands.useProfile('ronin-2.2.2');
  for (const options of [{}, { yaw: 1 }, { enabled: null }, { preset: 'PF' }, { roll: true, timeoutMs: true }])
    await assert.rejects(gimbal.appCommands.setCustomFollowSettings(options));
  assert.equal(p.frames().length, 0);
  const reading = gimbal.appCommands.getCustomFollowSettings(); await until(() => commands(p, 0x10).length);
  reply(p, commands(p, 0x10).at(-1), [0,132,1,137]); const result = await reading;
  assert.equal(result.rawValue, 137); assert.equal(result.unknownBits, 128);
  assert.deepEqual(result.settings, { enabled: true, pitch: false, roll: false, yaw: true });
});
test('settings ACK receives the remaining deadline, rather than a new full timeout', async () => {
  const { AppCommands } = await import('../src/app-commands.js');
  const performanceDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'performance'); let clock = 1000; const timeouts = [];
  const message = (id, payload) => ({ sender: 4, receiver: 2, commandSet: 4, commandId: id, flags: 128, payload: Buffer.from(payload), raw: Buffer.alloc(0) });
  const owner = {
    motionEpoch: 1, _stop: async () => {},
    _run: async (_kind, body) => body({ controller: new AbortController() }),
    experimental: { _queryPayloadCommand: async (_kind, command, _payload, timeout) => {
      timeouts.push(timeout);
      if (command[1] === 0x10) { clock += 75; return message(0x10, [0,132,1,0]); }
      return message(0x0f, [0]);
    } },
  };
  const app = new AppCommands(owner); app._profile = 'ronin-2.2.2';
  try { Object.defineProperty(globalThis, 'performance', { value: { now: () => clock }, configurable: true }); await app.setCustomFollowSettings({ yaw: true, timeoutMs: 100 }); }
  finally { Object.defineProperty(globalThis, 'performance', performanceDescriptor); }
  assert.deepEqual(timeouts, [100, 25]);
});
