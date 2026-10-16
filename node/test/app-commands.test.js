import test from 'node:test';
import assert from 'node:assert/strict';
import { connected, until } from './fakes.js';
import { frame, crc16 } from '../src/protocol.js';
function reply(peripheral, sent, payload, mutate = () => {}) {
  const data = frame(sent.sequence, 4, sent.commandId, Buffer.from(payload), 0x80);
  data[4] = 4; data[5] = 2; mutate(data);
  data.writeUInt16LE(crc16(data.subarray(0, -2)), data.length - 2);
  peripheral.rx.emit('data', data, true);
}
const sentApp = (p, id) => p.frames().filter(f => f.commandId === id).at(-1);

test('App source profile is explicit and mutually exclusive with legacy profiles', async t => {
  const { gimbal, peripheral } = await connected(t);
  await assert.rejects(gimbal.appCommands.getFollowSensitivity(), /explicit/);
  assert.equal(peripheral.frames().length, 0);
  gimbal.experimental.useProfile('rs3');
  gimbal.appCommands.useProfile('ronin-2.2.2');
  assert.equal(gimbal.experimental.profile, null);
  gimbal.experimental.useProfile('rs3mini');
  assert.equal(gimbal.appCommands.profile, null);
  await assert.rejects(gimbal.appCommands.setFollowSensitivity({ mode: 1 }), /explicit/);
});
test('parameter request preserves unsigned high indexes, duplicate order and context snapshot', async t => {
  const { gimbal, peripheral } = await connected(t);
  gimbal.appCommands.useProfile('ronin-2.2.2');
  const parameters = [{ index: 150, size: 1 }, { index: 150, size: 8 }];
  const read = gimbal.appCommands.readParameters({ parameters }); parameters[0].index = 1;
  await until(() => sentApp(peripheral, 0x10));
  const sent = sentApp(peripheral, 0x10);
  assert.equal(sent.payload.toString('hex'), '9696');
  assert.throws(() => gimbal.experimental.useProfile('rs3'), { code: 'RS4MINI_BUSY' });
  reply(peripheral, sent, [0, 150, 9, 1, 150, 8, ...Array(8).fill(255)]);
  const result = await read;
  assert.deepEqual(result.parameters, [{ index: 150, size: 1, headerByte: 9, rawHex: '01' }, { index: 150, size: 8, headerByte: 8, rawHex: 'ffffffffffffffff' }]);
  assert.equal(result.message.payload.toString('hex'), '009609019608ffffffffffffffff');
  assert.equal(result.deviceVerified, false);
  assert.equal(gimbal.experimental.pending.size, 0);
});
test('setter owns the operation and waits for correlated status acknowledgement', async t => {
  const { gimbal, peripheral } = await connected(t);
  gimbal.appCommands.useProfile('ronin-2.2.2');
  const options = { mode: 1 }; const write = gimbal.appCommands.setFollowSensitivity(options); options.mode = 0;
  await until(() => sentApp(peripheral, 0x0f));
  const sent = sentApp(peripheral, 0x0f);
  assert.equal(sent.payload.toString('hex'), '960101');
  assert.equal(sent.flags, 0x40);
  await assert.rejects(gimbal.setVelocity({ pan: .1 }), { code: 'RS4MINI_BUSY' });
  let complete = false; write.then(() => { complete = true; });
  reply(peripheral, sent, [0], data => { data[6] ^= 1; });
  reply(peripheral, sent, [0], data => { data[4] = 0x24; });
  await new Promise(resolve => setImmediate(resolve)); assert.equal(complete, false);
  reply(peripheral, sent, [0]);
  const result = await write;
  assert.equal(result.requestedMode, 1); assert.equal(result.acknowledged, true); assert.equal(result.physicalCompletionVerified, false);
  assert.equal(gimbal.activeOperation, null);
});
test('device rejection and malformed replies cannot become successful parameter transactions', async t => {
  const { gimbal, peripheral } = await connected(t);
  gimbal.appCommands.useProfile('ronin-2.2.2');
  const write = gimbal.appCommands.setFollowSensitivity({ mode: 0 });
  const rejected = assert.rejects(write, error => error.code === 'RS4MINI_DEVICE_ERROR' && error.statusCode === 7 && typeof error.message === 'string');
  await until(() => sentApp(peripheral, 0x0f)); reply(peripheral, sentApp(peripheral, 0x0f), [7]); await rejected;
  const read = gimbal.appCommands.getFollowSensitivity();
  const malformed = assert.rejects(read, { code: 'RS4MINI_PROTOCOL_ERROR' });
  await until(() => sentApp(peripheral, 0x10)); reply(peripheral, sentApp(peripheral, 0x10), [0, 150, 1]); await malformed;
  assert.equal(gimbal.experimental.pending.size, 0);
});
test('setter cancellation and timeout remove correlation and never replay a write', async t => {
  const { gimbal, peripheral } = await connected(t);
  gimbal.appCommands.useProfile('ronin-2.2.2');
  const write = gimbal.appCommands.setFollowSensitivity({ mode: 1, timeoutMs: 1000 });
  const cancelled = assert.rejects(write, { code: 'RS4MINI_OPERATION_CANCELLED' });
  await until(() => sentApp(peripheral, 0x0f)); await gimbal.stop(); await cancelled;
  assert.equal(gimbal.experimental.pending.size, 0); assert.equal(gimbal.activeOperation, null);
  await assert.rejects(gimbal.appCommands.setFollowSensitivity({ mode: 0, timeoutMs: 5 }), { code: 'RS4MINI_RESPONSE_TIMEOUT' });
  assert.equal(peripheral.frames().filter(f => f.commandId === 0x0f).length, 2);
  assert.equal(gimbal.experimental.pending.size, 0);
});
test('invalid arguments do not start movement cleanup or submit frames', async t => {
  const { gimbal, peripheral } = await connected(t);
  gimbal.appCommands.useProfile('ronin-2.2.2');
  for (const options of [{ mode: 2 }, { mode: true }, { mode: 1, timeoutMs: -1 }, { mode: 1, raw: [] }])
    await assert.rejects(gimbal.appCommands.setFollowSensitivity(options));
  for (const parameters of [[], [{ index: 150, size: 3 }], [{ index: 256, size: 1 }], [{ index: 150, size: 1, name: 'inferred' }]])
    await assert.rejects(gimbal.appCommands.readParameters({ parameters }));
  assert.equal(peripheral.frames().length, 0);
});
test('read disconnect rejects pending request and late previous-session replies do not complete a new request', async t => {
  const { gimbal, peripheral } = await connected(t);
  gimbal.appCommands.useProfile('ronin-2.2.2');
  const read = gimbal.appCommands.getFollowSensitivity();
  const disconnected = assert.rejects(read, { code: 'RS4MINI_DISCONNECTED' });
  await until(() => sentApp(peripheral, 0x10)); const old = sentApp(peripheral, 0x10);
  peripheral.emit('disconnect'); await disconnected;
  await until(() => gimbal.cleanupTasks.size === 0);
  await gimbal.connect();
  const next = gimbal.appCommands.getFollowSensitivity();
  await until(() => peripheral.frames().filter(f => f.commandId === 0x10).length === 2);
  reply(peripheral, old, [0, 150, 1, 1]);
  reply(peripheral, sentApp(peripheral, 0x10), [0, 150, 1, 255]);
  assert.equal((await next).mode, null);
});
