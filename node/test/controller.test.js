import assert from 'node:assert/strict';
import test from 'node:test';
import { setTimeout as sleep } from 'node:timers/promises';
import { connected, setup, until, gate } from './fakes.js';

test('scan normalizes name spaces, cached direct connect skips scan, stale cache falls back', async t => {
  const { gimbal, adapter, peripheral } = await connected(t);
  assert.equal(gimbal.connected, true); assert.equal(adapter.scans, 1);
  await gimbal.disconnect();
  await gimbal.connect(); assert.equal(adapter.scans, 1);
  await gimbal.disconnect();
  adapter.connectAsync = async () => { throw new Error('stale id'); };
  await gimbal.connect(); assert.equal(adapter.scans, 2); assert.equal(gimbal.deviceId, peripheral.id);
});
test('invalid options and conflicting operations cannot cancel the owner', async t => {
  const { gimbal } = await connected(t);
  await assert.rejects(gimbal.connect({ timeuotMs: 1 }), /unknown option/);
  await assert.rejects(gimbal.setVelocity({ tile: 1 }), /unknown option/);
  await assert.rejects(gimbal.moveTo({ pan: NaN }), /finite/);
  const motion = gimbal.moveTo({ pan: 20 }); const rejected = assert.rejects(motion, { code: 'RS4MINI_MOVE_CANCELLED' });
  await assert.rejects(gimbal.moveFor({ pan: 0.1, durationMs: 0 }), { code: 'RS4MINI_BUSY' });
  await assert.rejects(gimbal.recenter(), { code: 'RS4MINI_BUSY' });
  await assert.rejects(gimbal.setVelocity({ pan: 0.1 }), { code: 'RS4MINI_BUSY' });
  assert.equal(gimbal.moveToActive, true);
  await gimbal.stop(); await rejected; assert.equal(gimbal.moveToActive, false);
});
test('stop produces three complete neutral frames with 20-byte GATT chunks', async t => {
  const { gimbal, peripheral } = await connected(t);
  await gimbal.stop();
  assert.deepEqual(peripheral.tx.writes.map(([data]) => data.length), [20, 2, 20, 2, 20, 2]);
  assert.equal(peripheral.frames().length, 3);
  for (const item of peripheral.frames()) assert.equal(item.payload.readInt16LE(4), 1024);
});
test('cached readings are copied; fresh joints skip attitude-only frames', async t => {
  const { gimbal, peripheral } = await connected(t);
  peripheral.telemetry({ yaw: 12.34 }); const cached = await gimbal.getJointAngles();
  cached.yaw = 99; cached.raw.yaw = 99;
  assert.equal((await gimbal.getJointAngles()).yaw, 12.34);
  const next = gimbal.getJointAngles({ fresh: true });
  peripheral.telemetry({ short: true }); assert.equal(gimbal.telemetryWaiters.size, 1);
  peripheral.telemetry({ yaw: 24 }); assert.equal((await next).yaw, 24);
});
test('sync/async callbacks and error callbacks cannot break telemetry processing', async t => {
  const { gimbal, peripheral } = await connected(t);
  const errors = [];
  gimbal.onError = error => { errors.push(error); throw new Error('observer error'); };
  gimbal.onNotification = () => { throw new Error('raw callback'); };
  gimbal.onMessage = async () => { throw new Error('async message callback'); };
  gimbal.onTelemetry = sample => { sample.jointAngles.yaw = 999; };
  const reading = gimbal.getJointAngles({ fresh: true });
  peripheral.telemetry({ yaw: 2 }); assert.equal((await reading).yaw, 2);
  await until(() => errors.length === 2); assert.equal(gimbal.latestTelemetry.jointAngles.yaw, 2);
});
test('moveTo zeros each axis in tolerance and preserves Tilt sign', async t => {
  const { gimbal, peripheral } = await connected(t);
  const motion = gimbal.moveTo({ pan: 5, tilt: 5, roll: -4 });
  peripheral.telemetry({ yaw: 4.5 });
  await until(() => peripheral.frames().length >= 1);
  const payload = peripheral.frames()[0].payload;
  assert.equal(payload.readInt16LE(4), 1024); // pan within 1 degree
  assert(payload.readInt16LE(0) < 1024); assert(payload.readInt16LE(2) < 1024);
  await until(() => gimbal.telemetryWaiters.size > 0);
  peripheral.telemetry({ yaw: 4.8, pitch: 4.5, roll: -3.5 });
  const result = await motion;
  assert.deepEqual(result.current, { pan: 4.8, tilt: 4.5, roll: -3.5 });
  assert.equal(gimbal.activeOperation, null);
});
test('Pan crosses the wrap using the shortest error', async t => {
  const { gimbal, peripheral } = await connected(t);
  const motion = gimbal.moveTo({ pan: -179, toleranceDeg: 0.5 });
  peripheral.telemetry({ yaw: 179 }); await until(() => peripheral.frames().length > 0);
  assert(peripheral.frames()[0].payload.readInt16LE(4) > 1024);
  await until(() => gimbal.telemetryWaiters.size > 0); peripheral.telemetry({ yaw: -179 });
  await motion;
});
test('total move timeout has one error code even inside a telemetry wait', async t => {
  const { gimbal } = await connected(t);
  await assert.rejects(gimbal.moveTo({ pan: 5, timeoutMs: 20, telemetryTimeoutMs: 500 }), error => {
    assert.equal(error.code, 'RS4MINI_MOVE_TIMEOUT'); assert.deepEqual(error.target, { pan: 5 }); assert.equal(error.current, null); return true;
  });
  assert.equal(gimbal.telemetryWaiters.size, 0); assert.equal(gimbal.moveToActive, false);
});
test('a shorter telemetry timeout stays distinguishable from total timeout', async t => {
  const { gimbal } = await connected(t);
  await assert.rejects(gimbal.moveTo({ pan: 5, timeoutMs: 500, telemetryTimeoutMs: 20 }), { code: 'RS4MINI_TELEMETRY_TIMEOUT' });
});
test('moveFor sleep is cancelled immediately; old duration cannot stop a new command', async t => {
  const { gimbal, peripheral } = await connected(t);
  const motion = gimbal.moveFor({ pan: 0.1, durationMs: 80 });
  const rejected = assert.rejects(motion, { code: 'RS4MINI_MOVE_CANCELLED' });
  await until(() => peripheral.frames().length >= 1);
  await gimbal.stop(); await rejected;
  await gimbal.setVelocity({ tilt: 0.1 }); await sleep(100);
  assert.equal(gimbal.velocity.tilt, 0.1); await gimbal.stop();
});
test('stop during an in-flight first chunk completes the frame then only sends neutrals', async t => {
  const { gimbal, peripheral } = await connected(t);
  const block = gate(), original = peripheral.tx.writeAsync.bind(peripheral.tx);
  let entered = false;
  peripheral.tx.writeAsync = async (...args) => { if (!entered) { entered = true; await block.promise; } return original(...args); };
  const motion = gimbal.setVelocity({ pan: 0.2 });
  const rejected = assert.rejects(motion, { code: 'RS4MINI_OPERATION_CANCELLED' });
  await until(() => entered);
  const stop = gimbal.stop();
  await assert.rejects(gimbal.setVelocity({ tilt: 0.2 }), { code: 'RS4MINI_BUSY' });
  block.resolve(); await stop; await rejected;
  const frames = peripheral.frames(); assert.equal(frames.length, 4);
  assert(frames[0].payload.readInt16LE(4) > 1024);
  for (const item of frames.slice(1)) assert.equal(item.payload.readInt16LE(4), 1024);
  assert.equal(gimbal.streamPromise, null);
});
test('moveTo owns final stop cleanup until the last neutral write finishes', async t => {
  const { gimbal, peripheral } = await connected(t);
  const block = gate(), original = peripheral.tx.writeAsync.bind(peripheral.tx);
  let entered = false;
  peripheral.tx.writeAsync = async (...args) => { if (!entered) { entered = true; await block.promise; } return original(...args); };
  const motion = gimbal.moveTo({ pan: 0 }); peripheral.telemetry();
  await until(() => entered); assert.equal(gimbal.moveToActive, true);
  await assert.rejects(gimbal.moveTo({ pan: 1 }), { code: 'RS4MINI_BUSY' });
  block.resolve(); await motion; assert.equal(gimbal.moveToActive, false);
});
test('write failures disconnect instead of continuing a partly written DUML stream', async t => {
  const { gimbal, peripheral } = await connected(t, { ioTimeoutMs: 20 });
  let disconnects = 0; gimbal.onDisconnect = () => disconnects++;
  peripheral.tx.writeAsync = () => new Promise(() => {});
  await assert.rejects(gimbal.setVelocity({ pan: 0.1 }), { code: 'RS4MINI_IO_TIMEOUT' });
  assert.equal(gimbal.connected, false); await until(() => peripheral.disconnectCount > 0);
  assert.equal(peripheral.rx.listenerCount('data'), 0);
  assert.equal(disconnects, 1, 'write failure must notify observers exactly once');
});
test('disconnect removes listeners, rejects readers, and reconnect has exactly one listener', async t => {
  const { gimbal, peripheral } = await connected(t);
  const reader = gimbal.getAttitude({ fresh: true }); const rejected = assert.rejects(reader, { code: 'RS4MINI_DISCONNECTED' });
  await gimbal.disconnect(); await rejected;
  assert.equal(peripheral.rx.listenerCount('data'), 0); assert.equal(peripheral.listenerCount('disconnect'), 0);
  await gimbal.connect(); assert.equal(peripheral.rx.listenerCount('data'), 1); assert.equal(peripheral.listenerCount('disconnect'), 1);
  peripheral.telemetry({ yaw: 5 }); assert.equal((await gimbal.getJointAngles()).yaw, 5);
});
test('unexpected disconnection cancels motion and never restarts on reconnect', async t => {
  const { gimbal, peripheral } = await connected(t);
  const motion = gimbal.moveFor({ pan: 0.1, durationMs: 10000 });
  const rejected = assert.rejects(motion, { code: 'RS4MINI_MOVE_CANCELLED' });
  await until(() => gimbal.streamPromise); await peripheral.disconnectAsync(); await rejected;
  assert.deepEqual(gimbal.velocity, { pan: 0, tilt: 0, roll: 0 });
  await gimbal.connect(); const writes = peripheral.tx.writes.length; await sleep(5);
  assert.equal(peripheral.tx.writes.length, writes);
});

for (const stage of ['power', 'scanStart', 'scan', 'scanStop', 'peripheral', 'discovery', 'subscribe']) {
  test(`connection deadline bounds ${stage} and cleans listeners`, async () => {
    const { gimbal, peripheral, adapter } = setup({ ioTimeoutMs: 20 });
    const never = () => new Promise(() => {});
    if (stage === 'power') adapter.waitForPoweredOnAsync = never;
    if (stage === 'scanStart') adapter.startScanningAsync = never;
    if (stage === 'scan') adapter.startScanningAsync = async () => {};
    if (stage === 'scanStop') adapter.stopScanningAsync = never;
    if (stage === 'peripheral') peripheral.connectAsync = never;
    if (stage === 'discovery') peripheral.discoverSomeServicesAndCharacteristicsAsync = never;
    if (stage === 'subscribe') peripheral.rx.subscribeAsync = never;
    const started = performance.now();
    await assert.rejects(gimbal.connect({ timeoutMs: 25 }), { code: 'RS4MINI_CONNECT_TIMEOUT' });
    assert(performance.now() - started < 1000); assert.equal(gimbal.connected, false);
    assert.equal(adapter.listenerCount('discover'), 0); assert.equal(peripheral.rx.listenerCount('data'), 0);
    assert.equal(peripheral.listenerCount('disconnect'), 0);
    await gimbal.close().catch(() => {}); assert.equal(adapter.stopped, true);
  });
}
for (const stage of ['power', 'scan', 'direct', 'discovery', 'subscribe']) {
  test(`close cancels pending ${stage}; late completion cannot resurrect the controller`, async () => {
    const { gimbal, adapter, peripheral } = setup({ ioTimeoutMs: 30 });
    const block = gate(); let entered = false;
    const blocked = async () => { entered = true; return block.promise; };
    if (stage === 'power') adapter.waitForPoweredOnAsync = blocked;
    if (stage === 'scan') adapter.startScanningAsync = blocked;
    if (stage === 'direct') adapter.connectAsync = blocked;
    if (stage === 'discovery') peripheral.discoverSomeServicesAndCharacteristicsAsync = blocked;
    if (stage === 'subscribe') peripheral.rx.subscribeAsync = blocked;
    const connecting = gimbal.connect({ timeoutMs: 10000, ...(stage === 'direct' ? { deviceId: peripheral.id } : {}) });
    const rejected = assert.rejects(connecting, { code: 'RS4MINI_CONNECT_CANCELLED' });
    await until(() => entered); await gimbal.close(); await rejected;
    if (stage === 'direct') { peripheral.state = 'connected'; block.resolve(peripheral); await until(() => peripheral.disconnectCount > 0); }
    else block.resolve({ characteristics: [peripheral.rx, peripheral.tx] });
    await sleep(2);
    assert.equal(gimbal.connected, false); assert.equal(adapter.stopped, true);
    assert.equal(adapter.listenerCount('discover'), 0); assert.equal(peripheral.rx.listenerCount('data'), 0);
    await assert.rejects(gimbal.connect(), /closed/);
  });
}
test('failed discovery and missing characteristics clean up the peripheral', async () => {
  const { gimbal, peripheral } = setup();
  peripheral.discoverSomeServicesAndCharacteristicsAsync = async () => ({ characteristics: [] });
  await assert.rejects(gimbal.connect(), /FFF4\/FFF5/);
  await until(() => peripheral.disconnectCount > 0); await gimbal.close();
});

test('position takeover stops an existing manual stream before waiting for feedback', async t => {
  const { gimbal, peripheral } = await connected(t);
  await gimbal.setVelocity({ pan: 0.2 });
  const motion = gimbal.moveTo({ pan: 3 });
  const cancelled = assert.rejects(motion, { code: 'RS4MINI_MOVE_CANCELLED' });
  await until(() => gimbal.telemetryWaiters.size > 0);
  assert.deepEqual(gimbal.velocity, { pan: 0, tilt: 0, roll: 0 }); assert.equal(gimbal.streamPromise, null);
  for (const item of peripheral.frames().slice(-3)) assert.equal(item.payload.readInt16LE(4), 1024);
  await gimbal.stop(); await cancelled;
});
test('recenter is serialized after neutrals and a stop during its preamble cancels it', async t => {
  const { gimbal, peripheral } = await connected(t);
  await gimbal.recenter();
  assert.deepEqual(peripheral.frames().map(item => item.commandId), [1, 1, 1, 0x4c, 1, 1, 1]);
  peripheral.tx.writes.length = 0;
  const block = gate(), original = peripheral.tx.writeAsync.bind(peripheral.tx); let entered = false;
  peripheral.tx.writeAsync = async (...args) => { if (!entered) { entered = true; await block.promise; } return original(...args); };
  const motion = gimbal.recenter(); const cancelled = assert.rejects(motion, { code: 'RS4MINI_OPERATION_CANCELLED' });
  await until(() => entered); const stop = gimbal.stop(); block.resolve(); await stop; await cancelled;
  assert(peripheral.frames().every(item => item.commandId === 1));
});
test('state snapshots cannot modify feedback or sustained velocity', async t => {
  const { gimbal, peripheral } = await connected(t);
  peripheral.telemetry({ yaw: 2 }); gimbal.latestTelemetry.jointAngles.yaw = 999;
  assert.equal((await gimbal.getJointAngles()).yaw, 2);
  await gimbal.setVelocity({ pan: 0.1 }); gimbal.velocity.pan = 1;
  assert.equal(gimbal.velocity.pan, 0.1);
});
test('stream write errors reach onError even when invalidation also cancels the stream', async t => {
  const { gimbal, peripheral } = await connected(t);
  const errors = []; gimbal.onError = error => errors.push(error);
  await gimbal.setVelocity({ pan: 0.1 });
  peripheral.tx.writeAsync = async () => { throw new Error('transport failed'); };
  await until(() => errors.length > 0); assert.match(errors[0].message, /transport failed/);
  assert.equal(gimbal.connected, false);
});
test('timeout error remains primary if final stop itself fails', async t => {
  const { gimbal, peripheral } = await connected(t);
  peripheral.tx.writeAsync = async () => { throw new Error('stop failed'); };
  await assert.rejects(gimbal.moveTo({ pan: 3, timeoutMs: 15 }), error => {
    assert.equal(error.code, 'RS4MINI_MOVE_TIMEOUT'); assert.match(error.cleanupError.message, /stop failed/); return true;
  });
});
test('late cached result cannot disconnect a fallback connection using the same peripheral', async t => {
  const { gimbal, peripheral, adapter } = setup(); t.after(() => gimbal.close());
  const direct = gate(); adapter.connectAsync = () => direct.promise;
  await gimbal.connect({ deviceId: peripheral.id, timeoutMs: 200, directConnectTimeoutMs: 10 });
  direct.resolve(peripheral); await sleep(2);
  assert.equal(gimbal.connected, true); assert.equal(peripheral.disconnectCount, 0);
});
test('close during scan connection disposes a late peripheral connection', async () => {
  const { gimbal, peripheral } = setup(); const block = gate(); let entered = false;
  peripheral.connectAsync = async () => { entered = true; await block.promise; peripheral.state = 'connected'; };
  const pending = gimbal.connect(); const rejected = assert.rejects(pending, { code: 'RS4MINI_CONNECT_CANCELLED' });
  await until(() => entered); await gimbal.close(); await rejected;
  block.resolve(); await until(() => peripheral.state === 'disconnected' && peripheral.disconnectCount >= 2);
  assert.equal(gimbal.connected, false);
});

test('cancelling a powered-off EventEmitter adapter removes its power listener immediately', async () => {
  const { gimbal, adapter } = setup(); adapter.state = 'poweredOff';
  adapter.waitForPoweredOnAsync = () => { throw new Error('Must use owned event listener'); };
  const pending = gimbal.connect(); const rejected = assert.rejects(pending, { code: 'RS4MINI_CONNECT_CANCELLED' });
  await until(() => adapter.listenerCount('stateChange') === 1);
  await gimbal.close(); await rejected; assert.equal(adapter.listenerCount('stateChange'), 0);
});
