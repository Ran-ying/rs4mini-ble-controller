// Separate explicit large-motion opt-in. Not part of the continuous settings batch.
import assert from 'node:assert/strict';
import { BleDevice } from '../../node/src/device-node.js';
if (process.argv.includes('--help')) {
  console.log('RS4MINI_SDK_TEST=yes RS4MINI_ALLOW_FULL_RECENTER=yes RS4MINI_DEVICE_ID=<local ID> node tools/hardware/sdk-node-recenter.mjs');
  process.exit(0);
}
if (process.env.RS4MINI_SDK_TEST !== 'yes' || process.env.RS4MINI_ALLOW_FULL_RECENTER !== 'yes' || !process.env.RS4MINI_DEVICE_ID)
  throw Error('Explicit full three-axis recenter authorization, clear/balanced/unlocked device and local ID required');
const g = new BleDevice({ deviceId: process.env.RS4MINI_DEVICE_ID.replaceAll('-', '').toLowerCase() });
const rows = [], samples = [], diff = (a, b) => (a - b + 540) % 360 - 180;
const startedAt = new Date().toISOString();
try {
  await g.connect({ timeoutMs: 15000, directConnectTimeoutMs: 8000 });
  const before = await g.getJointAngles({ fresh: true, timeoutMs: 3000 }); samples.push(before);
  await g.recenter(); rows.push({ name: 'recenter.write', ok: true });
  const deadline = Date.now() + 15000; let stable = 0;
  while (Date.now() < deadline && stable < 2) {
    const current = await g.getJointAngles({ fresh: true, timeoutMs: 3000 });
    const previous = samples.at(-1); samples.push(current);
    stable = ['yaw', 'pitch', 'roll'].every(k => Math.abs(diff(current[k], previous[k])) <= 0.2) ? stable + 1 : 0;
  }
  const final = samples.at(-1); assert.equal(stable, 2);
  assert.ok(Math.abs(diff(final.yaw, 0)) <= 3, 'Yaw did not settle near centered reference');
  if (Math.abs(before.yaw) > 10) assert.ok(Math.abs(diff(final.yaw, before.yaw)) > 5, 'No expected yaw change');
  rows.push({ name: 'recenter.measuredSettledYaw', ok: true });
  // Roll/Pitch reference and precise final offset depend on device settings, retained as measurements.
  assert.equal(g.decoder.invalidFrames, 0); assert.equal(g.decoder.discardedBytes, 0);
  rows.push({ name: 'decoder', ok: true });
} catch (e) { rows.push({ name: 'session', ok: false, code: e.code || e.name, message: e.message }); }
finally {
  try { await g.close(); assert.equal(g.connected, false); rows.push({ name: 'close', ok: true }); }
  catch (e) { rows.push({ name: 'close', ok: false, code: e.code || e.name }); }
}
console.log(JSON.stringify({ port: 'node', entry: 'BleDevice', sdkVersion: '0.7.38', startedAt, finishedAt: new Date().toISOString(), rows, samples,
  precisionGuarantee: false, separateAxisCenteringVerified: false }, null, 2));
if (rows.some(r => !r.ok)) process.exitCode = 1;
