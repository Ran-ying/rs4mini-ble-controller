import assert from 'node:assert/strict';
import test from 'node:test';
import { setTimeout as sleep } from 'node:timers/promises';
import { connected, setup, until, gate } from './fakes.js';
import { velocityKeyframes, interpolateVelocity } from '../src/trajectory.js';

const trajectory = [{ timeMs: 0, pan: 0.1 }, { timeMs: 60, tilt: -0.1 }];
const retry = { initialDelayMs: 5, maxDelayMs: 10, timeoutMs: 30, directConnectTimeoutMs: 10, maxAttempts: 2 };
const neutral = item => [0, 2, 4].every(offset => item.payload.readInt16LE(offset) === 1024);

test('velocity keyframes validate, copy and interpolate all axes', () => {
  const input = [{ timeMs: 0, pan: 1 }, { timeMs: 100, tilt: -1 }];
  const frames = velocityKeyframes(input, 'linear'); input[0].pan = -1;
  assert.deepEqual(interpolateVelocity(frames, 25, 'linear'), { pan: 0.75, tilt: -0.25, roll: 0 });
  assert.deepEqual(interpolateVelocity(frames, 25, 'smoothstep'), { pan: 0.84375, tilt: -0.15625, roll: 0 });
  assert.equal(interpolateVelocity(frames, 99, 'step').pan, 1);
  assert.equal(interpolateVelocity(frames, 100, 'step').pan, 0);
  for (const bad of [[], [{ timeMs: 1 }, { timeMs: 2 }], [{ timeMs: 0 }, { timeMs: 0 }], [{ timeMs: 0, pan: 2 }, { timeMs: 1 }]])
    assert.throws(() => velocityKeyframes(bad, 'linear'));
});
test('trajectory emits evolving velocities, owns motion and finishes with three neutrals', async t => {
  const { gimbal, peripheral } = await connected(t, { rateHz: 100 });
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'performance'); let clock = 0, chunks = 0;
  const write = peripheral.tx.writeAsync.bind(peripheral.tx);
  // One virtual 20ms step per complete two-chunk velocity frame, independent of host scheduling.
  peripheral.tx.writeAsync = async (...args) => { await write(...args); if (++chunks % 2 === 0) clock += 20; };
  try {
    Object.defineProperty(globalThis, 'performance', { value: { now: () => clock }, configurable: true });
    const motion = gimbal.runTrajectory(trajectory);
    await until(() => peripheral.frames().length > 0);
    await assert.rejects(gimbal.setVelocity({ pan: 1 }), { code: 'RS4MINI_BUSY' });
    const snapshot = gimbal.trajectoryProgress; if (snapshot) snapshot.sentFrames = 99;
    const result = await motion;
    assert.equal(result.sentFrames, 3); assert.equal(result.elapsedMs, 60);
    const frames = peripheral.frames(); assert.equal(frames.length, 6);
    assert.deepEqual(frames.slice(0,3).map(f=>[f.payload.readInt16LE(4),f.payload.readInt16LE(0)]),[[1090,1024],[1068,1002],[1046,980]]);
    assert(frames.slice(-3).every(neutral)); assert.equal(gimbal.trajectoryProgress, null);assert.equal(gimbal.activeOperation,null);
  } finally { Object.defineProperty(globalThis, 'performance', descriptor); }
});
test('trajectory stop cancels immediately, discards schedule and releases ownership', async t => {
  const { gimbal, peripheral } = await connected(t);
  const motion = gimbal.runTrajectory([{ timeMs: 0, pan: 0.1 }, { timeMs: 10000, pan: 0.1 }]);
  const rejected = assert.rejects(motion, { code: 'RS4MINI_MOVE_CANCELLED' });
  await until(() => peripheral.frames().length > 0); await gimbal.stop(); await rejected;
  const count = peripheral.frames().length; await sleep(10); assert.equal(peripheral.frames().length, count);
  await gimbal.setVelocity({ tilt: 0.1 }); await gimbal.stop();
});
test('trajectory slow writes fail with overrun instead of bursting stale frames', async t => {
  const { gimbal, peripheral } = await connected(t);
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'performance'); let clock = 0;
  const write = peripheral.tx.writeAsync.bind(peripheral.tx);
  // Advance only while the fake transport writes, never because the host is busy.
  peripheral.tx.writeAsync = async (...args) => { clock += 12; return write(...args); };
  try {
    Object.defineProperty(globalThis, 'performance', { value: { now: () => clock }, configurable: true });
    await assert.rejects(gimbal.runTrajectory(trajectory, { maxLagMs: 5 }), { code: 'RS4MINI_TRAJECTORY_OVERRUN' });
    assert.equal(peripheral.frames().length, 4); assert(!neutral(peripheral.frames()[0]));
    assert(peripheral.frames().slice(1).every(neutral));
  } finally { Object.defineProperty(globalThis, 'performance', descriptor); }
});
test('trajectory scheduler overrun before first write sends only three neutral frames', async t => {
  const { gimbal, peripheral } = await connected(t);
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'performance'); let reads = 0;
  try {
    // startedAt and the first delay see zero; the first scheduler check sees lag.
    Object.defineProperty(globalThis, 'performance', { value: { now: () => ++reads <= 2 ? 0 : 10 }, configurable: true });
    await assert.rejects(gimbal.runTrajectory(trajectory, { maxLagMs: 5 }), { code: 'RS4MINI_TRAJECTORY_OVERRUN' });
    assert.equal(peripheral.frames().length, 3); assert(peripheral.frames().every(neutral));
    assert.equal(gimbal.activeOperation, null); assert.equal(gimbal.trajectoryProgress, null);
  } finally { Object.defineProperty(globalThis, 'performance', descriptor); }
});
test('waypoints keep one motion owner across arrivals and cancellable dwell', async t => {
  const { gimbal, peripheral } = await connected(t);
  const motion = gimbal.moveThrough([{ pan: 5 }, { tilt: 3, holdMs: 10000 }]);
  const rejected = assert.rejects(motion, { code: 'RS4MINI_MOVE_CANCELLED' });
  peripheral.telemetry({ yaw: 5 });
  await until(() => gimbal.trajectoryProgress?.index === 1 && gimbal.telemetryWaiters.size > 0);
  await assert.rejects(gimbal.moveTo({ pan: 1 }), { code: 'RS4MINI_BUSY' });
  peripheral.telemetry({ pitch: 3 }); await until(() => peripheral.frames().length >= 6);
  await gimbal.stop(); await rejected; assert.equal(gimbal.trajectoryProgress, null);
});
test('invalid later waypoint cannot start any part of a trajectory', async t => {
  const { gimbal, peripheral } = await connected(t);
  await assert.rejects(gimbal.moveThrough([{ pan: 1 }, { pan: 181 }]), /between/);
  await assert.rejects(gimbal.moveThrough([{ pan: 1, holdMs: -1 }]), /holdMs/);
  await assert.rejects(gimbal.runTrajectory(trajectory, { interpolaton: 'linear' }), /unknown/);
  assert.equal(peripheral.frames().length, 0);
});
test('saved home returns only selected axes and is bound to device identity', async t => {
  const { gimbal, peripheral } = await connected(t);
  await assert.rejects(gimbal.moveHome(), { code: 'RS4MINI_HOME_UNSET' });
  peripheral.telemetry({ yaw: 4, pitch: 3, roll: 2 });
  const saved = await gimbal.captureHome(); saved.pan = 123;
  assert.equal(gimbal.home.pan, 4);
  const motion = gimbal.moveHome({ axes: ['pan'] }); peripheral.telemetry({ yaw: 4, pitch: 20 });
  assert.deepEqual((await motion).target, { pan: 4 });
  await assert.rejects(gimbal.moveHome({ axes: ['pan', 'pan'] }), /distinct/);
  gimbal.deviceId = 'DIFFERENT'; await assert.rejects(gimbal.moveHome(), { code: 'RS4MINI_HOME_UNSET' });
});
test('automatic reconnect restores link exactly once and never resumes motion', async t => {
  const { gimbal, peripheral } = await connected(t);
  const states = []; gimbal.onReconnect = state => states.push(state.state); gimbal.enableAutoReconnect(retry);
  await gimbal.setVelocity({ pan: 0.1 }); await peripheral.disconnectAsync();
  await until(() => gimbal.reconnectState.state === 'restored');
  assert.equal(gimbal.connected, true); assert.deepEqual(gimbal.velocity, { pan: 0, tilt: 0, roll: 0 });
  const count = peripheral.frames().length; await sleep(15); assert.equal(peripheral.frames().length, count);
  assert.deepEqual(states, ['idle', 'waiting', 'connecting', 'restored']);
  assert.equal(peripheral.rx.listenerCount('data'), 1); assert.equal(peripheral.listenerCount('disconnect'), 1);
});
test('automatic retry is bounded and reports exhaustion', async t => {
  const { gimbal, peripheral, adapter } = await connected(t);
  gimbal.enableAutoReconnect(retry); adapter.connectAsync = async () => { throw new Error('offline'); };
  adapter.startScanningAsync = async () => { adapter.scans++; };
  await peripheral.disconnectAsync(); await until(() => gimbal.reconnectState.state === 'exhausted');
  assert.equal(gimbal.reconnectState.attempt, 2); assert.equal(adapter.scans, 3); assert.equal(gimbal.connected, false);
});
test('manual disconnect disables pending automatic retry', async t => {
  const { gimbal, peripheral, adapter } = await connected(t);
  gimbal.enableAutoReconnect({ ...retry, initialDelayMs: 50, maxDelayMs: 50 });
  await peripheral.disconnectAsync(); await until(() => gimbal.reconnectState.state === 'waiting');
  await gimbal.disconnect(); await gimbal.reconnectTask; await sleep(60);
  assert.equal(gimbal.connected, false); assert.equal(adapter.scans, 1); assert.equal(gimbal.reconnectState.state, 'disabled');
});
test('disabling retries during connection cancels it and disposes late results', async t => {
  const { gimbal, peripheral, adapter } = await connected(t);
  const block = gate(); adapter.connectAsync = () => block.promise;
  gimbal.enableAutoReconnect({ ...retry, directConnectTimeoutMs: 500, timeoutMs: 1000 });
  await peripheral.disconnectAsync(); await until(() => gimbal.connection?.reconnectOwner);
  await gimbal.disableAutoReconnect();
  assert.equal(gimbal.connectPromise, null); assert.equal(gimbal.reconnectTask, null);
  await peripheral.connectAsync(); block.resolve(peripheral); await until(() => peripheral.state === 'disconnected');
});
test('close cancels retry and retry configuration is validated without Bluetooth', async () => {
  const { gimbal, adapter } = setup();
  assert.throws(() => gimbal.enableAutoReconnect({ maxAttempts: 1.5 }), /invalid/);
  assert.throws(() => gimbal.enableAutoReconnect({ maxDelayMs: 1 }), /invalid/);
  assert.throws(() => gimbal.enableAutoReconnect({ typo: 1 }), /unknown/);
  await gimbal.close(); assert.equal(adapter.scans, 0);
  assert.throws(() => gimbal.enableAutoReconnect(), /closed/);
});
test('waypoint dwell does not consume the next leg timeout and returns every arrival', async t => {
  const { gimbal, peripheral } = await connected(t);
  const motion = gimbal.moveThrough([{ pan: 2, holdMs: 40 }, { tilt: 3 }], { timeoutMs: 20 });
  peripheral.telemetry({ yaw: 2 });
  await until(() => gimbal.trajectoryProgress?.index === 1 && gimbal.telemetryWaiters.size > 0);
  peripheral.telemetry({ pitch: 3 });
  assert.deepEqual((await motion).map(result => result.target), [{ pan: 2 }, { tilt: 3 }]);
});
test('failed manual write may recover its link but never retries the failed command', async t => {
  const { gimbal, peripheral } = await connected(t);
  const write = peripheral.tx.writeAsync.bind(peripheral.tx);
  let failed = false;
  peripheral.tx.writeAsync = (...args) => { if (!failed) { failed = true; throw new Error('write lost'); } return write(...args); };
  gimbal.enableAutoReconnect(retry);
  await assert.rejects(gimbal.setVelocity({ pan: 0.2 }), /write lost/);
  await until(() => gimbal.reconnectState.state === 'restored');
  assert.equal(peripheral.frames().length, 0); assert.equal(gimbal.velocity.pan, 0);
});
test('a second loss from a restored observer schedules a distinct recovery', async t => {
  const { gimbal, peripheral } = await connected(t);
  let restored = 0;
  gimbal.onReconnect = state => { if (state.state === 'restored' && ++restored === 1) peripheral.disconnectAsync(); };
  gimbal.enableAutoReconnect(retry); await peripheral.disconnectAsync();
  await until(() => restored === 2); assert.equal(gimbal.connected, true);
});
