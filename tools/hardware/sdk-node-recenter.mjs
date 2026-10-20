// Separate explicit large-motion opt-in. Not part of the continuous settings batch.
import assert from 'node:assert/strict';
import { BleDevice } from '../../node/src/device-node.js';
if (process.argv.includes('--help')) {
  console.log('RS4MINI_SDK_TEST=yes RS4MINI_ALLOW_FULL_RECENTER=yes RS4MINI_DEVICE_ID=<local ID> node tools/hardware/sdk-node-recenter.mjs');
  console.log('Optional authorized offset from an already centered reference: RS4MINI_ALLOW_LARGE_MOTION=yes RS4MINI_RECENTER_YAW_OFFSET_DEG=15');
  process.exit(0);
}
if (process.env.RS4MINI_SDK_TEST !== 'yes' || process.env.RS4MINI_ALLOW_FULL_RECENTER !== 'yes' || !process.env.RS4MINI_DEVICE_ID)
  throw Error('Explicit full three-axis recenter authorization, clear/balanced/unlocked device and local ID required');
const offsetRequested = process.env.RS4MINI_RECENTER_YAW_OFFSET_DEG !== undefined;
if (offsetRequested && (process.env.RS4MINI_RECENTER_YAW_OFFSET_DEG !== '15' || process.env.RS4MINI_ALLOW_LARGE_MOTION !== 'yes'))
  throw Error('Explicit large motion authorization required for the fixed15degree yaw offset test');
const g = new BleDevice({ deviceId: process.env.RS4MINI_DEVICE_ID.replaceAll('-', '').toLowerCase() });
const rows = [], samples = [], diff = (a, b) => (a - b + 540) % 360 - 180;
let reference, guardTrip = false, telemetryAt = 0, watchdog, offsetSample;
g.onTelemetry = s => {
  telemetryAt = Date.now();
  if (offsetRequested && reference && s.jointAngles && (Math.abs(diff(s.jointAngles.yaw, reference.yaw)) > 25 ||
      ['pitch', 'roll'].some(k => Math.abs(diff(s.jointAngles[k], reference[k])) > 5))) {
    guardTrip = true; void g.stop().catch(() => {});
  }
};
const startedAt = new Date().toISOString();
try {
  await g.connect({ timeoutMs: 15000, directConnectTimeoutMs: 8000 });
  const before = await g.getJointAngles({ fresh: true, timeoutMs: 3000 }); samples.push(before);
  reference = before;
  if (offsetRequested) {
    watchdog = setInterval(() => {
      if (Object.values(g.velocity).some(v => v !== 0) && Date.now() - telemetryAt > 2500) {
        guardTrip = true; void g.stop().catch(() => {});
      }
    }, 100);
    const offsetDeadline = Date.now() + 20000;
    try {
      await g.setVelocity({ pan: 0.06 });
      do {
        offsetSample = await g.getJointAngles({ fresh: true, timeoutMs: 2500 }); samples.push(offsetSample);
        assert.equal(guardTrip, false);
      } while (Math.abs(diff(offsetSample.yaw, before.yaw)) < 15 && Date.now() < offsetDeadline);
    } finally { await g.stop(); clearInterval(watchdog); watchdog = null; }
    assert.ok(Math.abs(diff(offsetSample.yaw, before.yaw)) >= 15, 'Yaw offset deadline expired');
    assert.equal(guardTrip, false);
    offsetSample = await g.getJointAngles({ fresh: true, timeoutMs: 3000 }); samples.push(offsetSample);
    assert.equal(guardTrip, false);
    rows.push({ name: 'yaw.offsetMeasured', ok: true, offsetDegrees: diff(offsetSample.yaw, before.yaw) });
  }
  await g.recenter(); rows.push({ name: 'recenter.write', ok: true });
  const deadline = Date.now() + 15000; let stable = 0;
  while (Date.now() < deadline && stable < 2) {
    const current = await g.getJointAngles({ fresh: true, timeoutMs: 3000 });
    const previous = samples.at(-1); samples.push(current);
    stable = ['yaw', 'pitch', 'roll'].every(k => Math.abs(diff(current[k], previous[k])) <= 0.2) ? stable + 1 : 0;
  }
  assert.equal(stable, 2);
  rows.push({ name: 'recenter.measuredSettledFeedback', ok: true });
  // Joint zero has no verified mapping to the device's recenter reference.
  // User observation is required separately; stable feedback alone is not physical completion.
  if (offsetRequested) {
    const final = samples.at(-1), yawError = diff(final.yaw, before.yaw);
    assert.ok(Math.abs(yawError) <= 1, 'Recenter did not return near the measured baseline');
    rows.push({ name: 'recenter.returnMeasuredBaseline', ok: true, yawErrorDegrees: yawError });
  }
  assert.equal(g.decoder.invalidFrames, 0); assert.equal(g.decoder.discardedBytes, 0);
  rows.push({ name: 'decoder', ok: true });
} catch (e) { rows.push({ name: 'session', ok: false, code: e.code || e.name, message: e.message }); }
finally {
  clearInterval(watchdog);
  try { await g.close(); assert.equal(g.connected, false); rows.push({ name: 'close', ok: true }); }
  catch (e) { rows.push({ name: 'close', ok: false, code: e.code || e.name }); }
}
console.log(JSON.stringify({ port: 'node', entry: 'BleDevice', sdkVersion: '0.7.38', startedAt, finishedAt: new Date().toISOString(), rows, samples,
  offsetRequested, guardTrip, precisionGuarantee: false, physicalCompletionVerified: false, absoluteReferenceVerified: false, separateAxisCenteringVerified: false }, null, 2));
if (rows.some(r => !r.ok)) process.exitCode = 1;
