import test from 'node:test';
import assert from 'node:assert/strict';
import { orientationFromComponents } from '../src/orientation.js';
import { connected } from './fakes.js';
import { frame } from '../src/protocol.js';

test('explicit quaternion ordering, normalization and inversion follow ZYX math', () => {
  const s = Math.SQRT1_2;
  const a = orientationFromComponents([s * 2, 0, 0, s * 2], { componentOrder: 'wxyz' });
  assert(Math.abs(a.euler.yaw - 90) < 1e-10); assert(Math.abs(a.inputNorm - 2) < 1e-10);
  const b = orientationFromComponents([0, 0, s, s], { componentOrder: 'xyzw', conjugate: true });
  assert(Math.abs(b.euler.yaw + 90) < 1e-10);
  const c = orientationFromComponents([-s, 0, 0, -s], { componentOrder: 'wxyz' });
  for (const axis of ['roll', 'pitch', 'yaw']) assert(Math.abs(c.euler[axis] - a.euler[axis]) < 1e-10);
  assert.equal(a.deviceConventionVerified, false);
  assert.throws(() => orientationFromComponents([1, 0, 0, 0]), /componentOrder/);
  assert.throws(() => orientationFromComponents([0, 0, 0, 0], { componentOrder: 'wxyz' }), /zero/);
  assert.throws(() => orientationFromComponents([NaN, 0, 0, 0], { componentOrder: 'wxyz' }), /finite/);
});
test('orientation reads skip short frames, reject invalid norms, and copy outputs', async t => {
  const { gimbal, peripheral } = await connected(t);
  await assert.rejects(gimbal.getOrientation(), /componentOrder/);
  const reading = gimbal.getOrientation({ componentOrder: 'xyzw', fresh: true });
  peripheral.telemetry({ short: true }); assert.equal(gimbal.telemetryWaiters.size, 1);
  const payload = Buffer.alloc(49); payload.writeFloatLE(1, 36);
  peripheral.rx.emit('data', frame(1, 4, 5, payload), true);
  const result = await reading; result.quaternion.w = 123;
  assert.equal((await gimbal.getOrientation({ componentOrder: 'xyzw' })).quaternion.w, 1);
  peripheral.telemetry();
  await assert.rejects(gimbal.getOrientation({ componentOrder: 'wxyz' }), { code: 'RS4MINI_ORIENTATION_INVALID' });
});
