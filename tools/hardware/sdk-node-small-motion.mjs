// Authorized direct device-SDK velocity/stop and real reconnect test, no facade.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { BleDevice } from '../../node/src/device-node.js';
if (process.argv.includes('--help')) {
  console.log('RS4MINI_SDK_TEST=yes RS4MINI_ALLOW_SMALL_MOTION=yes RS4MINI_DEVICE_ID=<local ID> node tools/hardware/sdk-node-small-motion.mjs');
  process.exit(0);
}
if (process.env.RS4MINI_SDK_TEST !== 'yes' || process.env.RS4MINI_ALLOW_SMALL_MOTION !== 'yes' || !process.env.RS4MINI_DEVICE_ID)
  throw Error('Explicit SDK test, balanced/unlocked/clear small-motion authorization and local device ID required');
const g = new BleDevice({ deviceId: process.env.RS4MINI_DEVICE_ID.replaceAll('-', '').toLowerCase() });
const sleep = ms => new Promise(r => setTimeout(r, ms)), diff = (a, b) => (a - b + 540) % 360 - 180;
const rows = [], samples = [], reconnectEvents = [], errors = [], axes = ['yaw', 'pitch', 'roll'];
let base, guardTrip = false, telemetryAt = 0, watchdog;
const startedAt = new Date().toISOString(), capture = new URL('../../node/captures/node-small-motion-' + Date.now() + '.jsonl', import.meta.url);
fs.mkdirSync(new URL('../../node/captures/', import.meta.url), { recursive: true });
const save = (type, data) => fs.appendFileSync(capture, JSON.stringify({ at: Date.now(), type, data }) + '\n');
const trip = () => { if (guardTrip) return; guardTrip = true; void g.stop().catch(e => save('guard.stop.error', { code: e.code, message: e.message })); };
g.onTelemetry = s => {
  telemetryAt = Date.now(); save('telemetry', s);
  if (base && s.jointAngles && axes.some(k => Math.abs(diff(s.jointAngles[k], base[k])) > 5)) trip();
};
g.onMessage = m => save('message', m);
g.onError = e => { errors.push({ code: e.code || e.name }); save('error', { code: e.code, message: e.message }); };
g.onReconnect = s => { reconnectEvents.push(s.state); save('reconnect', s); };
const current = () => g.getJointAngles({ fresh: true, timeoutMs: 3000 });
async function check(name, fn) {
  const start = Date.now();
  try { const value = await fn(); rows.push({ name, ok: true, elapsedMs: Date.now() - start, value }); console.error('PASS', name); return value; }
  catch (e) { rows.push({ name, ok: false, elapsedMs: Date.now() - start, code: e.code || e.name }); save(name, { message: e.message }); console.error('FAIL', name, e.code || e.name); throw e; }
}
try {
  await g.connect({ timeoutMs: 15000, directConnectTimeoutMs: 8000 });
  base = await current(); samples.push({ label: 'baseline', joints: base });
  watchdog = setInterval(() => { if (Object.values(g.velocity).some(v => v !== 0) && Date.now() - telemetryAt > 2500) trip(); }, 100);
  for (const [control, joint] of [['pan', 'yaw'], ['tilt', 'pitch'], ['roll', 'roll']]) {
    await check('velocity.' + control + '.outBackStop', async () => {
      const before = await current();
      const positions = [];
      for (const speed of [0.025, -0.025]) {
        assert.equal(guardTrip, false);
        try { await g.setVelocity({ [control]: speed }); await sleep(350); }
        finally { await g.stop(); }
        assert.equal(guardTrip, false);
        assert.deepEqual(g.velocity, { pan: 0, tilt: 0, roll: 0 });
        await sleep(1200); positions.push(await current());
      }
      const outward = diff(positions[0][joint], before[joint]), reverse = diff(positions[1][joint], positions[0][joint]);
      // Do not promise closed-loop return precision for time-limited speed control.
      assert.ok(Math.abs(outward) >= 0.1 && Math.abs(reverse) >= 0.1 && outward * reverse < 0, 'No measured opposite joint changes');
      for (const p of positions) assert.ok(axes.every(k => Math.abs(diff(p[k], base[k])) <= 5));
      samples.push({ label: control, before, positions });
      return { outwardDegrees: outward, reverseDegrees: reverse, finalOffsetDegrees: diff(positions[1][joint], before[joint]), velocityZero: true };
    });
  }
  clearInterval(watchdog); watchdog = null;
  await check('decoder.beforeLinkDrop', () => { assert.equal(g.decoder.invalidFrames, 0); assert.equal(g.decoder.discardedBytes, 0); });
  for (let round = 0; round < 3; round++) await check('autoReconnect.realLinkDrop.' + round, async () => {
    g.enableAutoReconnect({ maxAttempts: 3, initialDelayMs: 250, maxDelayMs: 1000, timeoutMs: 12000, directConnectTimeoutMs: 8000 });
    try {
      // Fault injection only for this connected gimbal; public disconnect intentionally disables retry.
      await g.peripheral.disconnectAsync();
      const deadline = Date.now() + 30000;
      while (!(g.connected && g.reconnectState.state === 'restored') && Date.now() < deadline) await sleep(100);
      assert.equal(g.connected, true); assert.equal(g.reconnectState.state, 'restored');
      assert.deepEqual(g.velocity, { pan: 0, tilt: 0, roll: 0 });
      const joints = await current(); assert.equal(g.decoder.invalidFrames, 0); assert.equal(g.decoder.discardedBytes, 0);
      return { restored: true, attempt: g.reconnectState.attempt, velocityZero: true, joints };
    } finally { await g.disableAutoReconnect(); }
  });
  await check('noGuardOrBackgroundError', () => { assert.equal(guardTrip, false); assert.deepEqual(errors, []); });
} catch (e) { save('sessionError', { code: e.code, message: e.message }); if (!rows.some(r => !r.ok)) rows.push({ name: 'session', ok: false, code: e.code || e.name }); }
finally {
  clearInterval(watchdog);
  try { await g.close(); assert.equal(g.connected, false); assert.equal(g.closed, true); rows.push({ name: 'close', ok: true }); }
  catch (e) { rows.push({ name: 'close', ok: false, code: e.code || e.name }); }
}
console.log(JSON.stringify({ port: 'node', entry: 'BleDevice', sdkVersion: '0.7.38', startedAt, finishedAt: new Date().toISOString(), rows, samples, reconnectEvents, guardTrip, errors,
  exclusions: ['calibration', 'fine tune', 'recenter', 'composed motion', 'nonzero motion during link drop'] }, null, 2));
if (rows.some(r => !r.ok)) process.exitCode = 1;
