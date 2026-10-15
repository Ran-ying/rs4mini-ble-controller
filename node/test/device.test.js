import test from 'node:test';
import assert from 'node:assert/strict';
import { BleDevice } from '../src/device.js';
import { RS4Mini } from '../src/controller.js';
import { Adapter, Peripheral, until } from './fakes.js';

test('standalone BLE SDK supports device operations without composed motion', async t => {
  const peripheral = new Peripheral();
  const device = new BleDevice({ adapter: new Adapter(peripheral), rateHz: 1000 });
  t.after(() => device.close());
  assert.equal(device.moveTo, undefined);
  assert.equal(device.runTrajectory, undefined);
  assert.equal(device.experimental.absolute, undefined);
  await device.connect();
  const read = device.getJointAngles({ fresh: true });
  peripheral.telemetry({ yaw: 12, pitch: 3, roll: -2 });
  assert.equal((await read).yaw, 12);
  await device.setVelocity({ pan: .1 });
  await device.stop();
  await device.recenter();
  assert.ok(peripheral.frames().some(frame => frame.commandId === 0x4c));
  assert.equal(peripheral.frames().at(-1).commandId, 1);
  assert.equal(peripheral.frames().filter(f => f.commandId === 1).length >= 4, true);
});

test('application facade routes basic access and position through one SDK write owner', async t => {
  const peripheral = new Peripheral();
  const app = new RS4Mini({ adapter: new Adapter(peripheral), rateHz: 1000 });
  t.after(() => app.close());
  assert.ok(app instanceof BleDevice);
  await app.connect();
  let writes = 0;
  const write = app._writeVelocity.bind(app);
  app._writeVelocity = (...args) => { writes++; return write(...args); };
  await app.setVelocity({ pan: .1 });
  await app.stop();
  const moving = app.moveTo({ pan: 5 });
  await until(() => app.telemetryWaiters.size === 1);
  peripheral.telemetry({ yaw: 0 });
  await until(() => writes >= 2 && app.telemetryWaiters.size === 1);
  peripheral.telemetry({ yaw: 5 });
  assert.equal((await moving).current.pan, 5);
  assert.equal(app.operation, null);
  assert.equal(app.connected, true);
});

test('degree-info uses correlated SDK query without enabling an unrelated model profile', async t => {
  const { frame, crc16 } = await import('../src/protocol.js');
  for (const Type of [BleDevice, RS4Mini]) {
    const peripheral = new Peripheral();
    const app = new Type({ adapter: new Adapter(peripheral), rateHz: 1000 });
    t.after(() => app.close());
    await app.connect();
    const waiting = app.requestDegreeInfo({ timeoutMs: 1000 });
    await until(() => peripheral.frames().length > 0);
    const sent = peripheral.frames()[0];
    assert.equal(sent.commandId, 0x1e);
    assert.equal(sent.payload.length, 0);
    const reply = frame(sent.sequence, 4, 0x1e, Buffer.from([0]), 0x80);
    reply[4] = 4; reply[5] = 2;
    reply.writeUInt16LE(crc16(reply.subarray(0, -2)), reply.length - 2);
    peripheral.rx.emit('data', reply, true);
    assert.equal((await waiting).payload.toString('hex'), '00');
    assert.equal(app.experimental.profile, null);
  }
});
