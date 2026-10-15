// The application entry: basic device methods and composed motion share one owner.
import { BleDevice } from './device.js';
import { check, delay, failure, now } from './async.js';
import { known, positive, axisValue, velocity } from './values.js';
import { positionSettings } from './position-settings.js';
import { velocityKeyframes, interpolateVelocity } from './trajectory.js';
import { orientationFromComponents } from './orientation.js';
import { ExperimentalGimbal } from './experimental.js';

const axes = reading => ({ pan: reading.yaw, tilt: reading.pitch, roll: reading.roll });
const copy = value => value == null ? value : structuredClone(value);

export class RS4Mini extends BleDevice {
  constructor(options = {}) {
    super(options);
    this._trajectoryProgress = null; this._home = null;
    this.experimental = new ExperimentalGimbal(this);
  }
  _run(kind, body, stopAfter = true) {
    return super._run(kind, body, stopAfter, { cancelAsMove:
      ['moveTo', 'moveFor', 'runTrajectory', 'moveThrough', 'experimentalAbsolute', 'experimentalRate'].includes(kind) });
  }
  get moveToActive() { return this.operation?.kind === 'moveTo'; }

  get trajectoryProgress() { return copy(this._trajectoryProgress); }

  get home() { return copy(this._home); }

  async setVelocityDeg(options = {}) {
    known(options, ['pan', 'tilt', 'roll', 'panFullScale', 'tiltFullScale', 'rollFullScale'], 'setVelocityDeg');
    const values = {};
    for (const [axis, scale] of [['pan', 37.5], ['tilt', 27.5], ['roll', 30]]) {
      const full = options[`${axis}FullScale`] ?? scale;
      positive(full, `${axis}FullScale`); values[axis] = axisValue(options[axis] ?? 0, axis) / full;
    }
    return this.setVelocity(values);
  }

  async moveFor(options = {}) {
    known(options, ['durationMs', 'pan', 'tilt', 'roll'], 'moveFor');
    const { durationMs, ...inputs } = options;
    if (!Number.isFinite(durationMs) || durationMs < 0) throw new RangeError('durationMs must be a non-negative finite number');
    const values = velocity(inputs);
    return this._run('moveFor', async operation => {
      await this._setVelocity(values, operation); await delay(durationMs, operation.controller.signal);
    });
  }

  async getOrientation(options = {}) {
    known(options, ['componentOrder', 'conjugate', 'fresh', 'timeoutMs', 'normTolerance'], 'getOrientation');
    const { componentOrder, conjugate = false, fresh = false, timeoutMs = 3000, normTolerance = 0.1 } = options;
    // Validate the mathematical convention before waiting or accessing hardware.
    orientationFromComponents([1, 0, 0, 0], { componentOrder, conjugate });
    positive(timeoutMs, 'timeoutMs'); positive(normTolerance, 'normTolerance');
    if (typeof fresh !== 'boolean') throw new TypeError('fresh must be boolean');
    this._requireConnected();
    const sample = !fresh && this.latestTelemetry?.orientationQuaternion ? this.latestTelemetry :
      await this._waitForTelemetry(timeoutMs, { field: 'orientationQuaternion' });
    const raw = sample.orientationQuaternion;
    if (!Number.isFinite(raw.norm) || Math.abs(raw.norm - 1) > normTolerance) throw failure('RS4MINI_ORIENTATION_INVALID', 'Raw orientation components are not approximately unit length');
    return { ...orientationFromComponents(raw.components, { componentOrder, conjugate }), timestamp: sample.timestamp };
  }

  async moveTo(options = {}) {
    const settings = positionSettings(options);
    return this._run('moveTo', operation => this._moveTo(settings, operation));
  }

  async _moveTo({ target, toleranceDeg, timeoutMs, telemetryTimeoutMs, gain, minSpeed, maxSpeed }, operation) {
      const startedAt = now(); let current = null;
      const timeoutError = () => failure('RS4MINI_MOVE_TIMEOUT', `moveTo timed out after ${timeoutMs} ms`, { target: { ...target }, current: current ? axes(current) : null });
      const timer = setTimeout(() => operation.controller.abort(timeoutError()), timeoutMs);
      const read = () => this._reading('jointAngles', { fresh: true, timeoutMs: telemetryTimeoutMs }, operation.controller.signal);
      try {
        current = await read();
        while (true) {
          check(operation.controller.signal);
          if (now() - startedAt >= timeoutMs) throw timeoutError();
          const error = { pan: target.pan === undefined ? 0 : ((target.pan - current.yaw + 540) % 360) - 180,
            tilt: target.tilt === undefined ? 0 : target.tilt - current.pitch, roll: target.roll === undefined ? 0 : target.roll - current.roll };
          if (Object.values(error).every(value => Math.abs(value) <= toleranceDeg))
            return { target: { ...target }, current: axes(current), error, toleranceDeg, elapsedMs: now() - startedAt };
          const speed = value => Math.abs(value) <= toleranceDeg ? 0 : Math.sign(value) * Math.min(maxSpeed, Math.max(minSpeed, Math.abs(value) * gain));
          await this._setVelocity({ pan: speed(error.pan), tilt: -speed(error.tilt), roll: speed(error.roll) }, operation);
          current = await read();
        }
      } finally { clearTimeout(timer); }
  }

  async runTrajectory(keyframes, options = {}) {
    known(options, ['interpolation', 'maxLagMs'], 'runTrajectory');
    const { interpolation = 'linear', maxLagMs = 500 } = options;
    positive(maxLagMs, 'maxLagMs');
    const frames = velocityKeyframes(keyframes, interpolation);
    return this._run('runTrajectory', async operation => {
      const startedAt = now(), durationMs = frames.at(-1).timeMs, interval = 1000 / this.rateHz;
      let sentFrames = 0, skippedFrames = 0, due = 0;
      try {
        while (true) {
          await delay(Math.max(0, startedAt + due - now()), operation.controller.signal);
          const elapsedMs = now() - startedAt, lagMs = elapsedMs - due;
          if (lagMs > maxLagMs) throw failure('RS4MINI_TRAJECTORY_OVERRUN', 'Trajectory scheduler or BLE writes exceeded maxLagMs', { lagMs });
          if (elapsedMs >= durationMs) break;
          const values = interpolateVelocity(frames, elapsedMs, interpolation);
          await this._writeVelocity(values, operation);
          if (now() - startedAt - elapsedMs > maxLagMs) throw failure('RS4MINI_TRAJECTORY_OVERRUN', 'BLE trajectory write exceeded maxLagMs');
          sentFrames++;
          this._trajectoryProgress = { kind: 'velocity', elapsedMs, durationMs, sentFrames, skippedFrames };
          const next = Math.min(durationMs, Math.max(due + interval, Math.ceil((now() - startedAt) / interval) * interval));
          skippedFrames += Math.max(0, Math.round((next - due) / interval) - 1); due = next;
        }
        return { elapsedMs: now() - startedAt, durationMs, sentFrames, skippedFrames };
      } finally { this._trajectoryProgress = null; }
    });
  }

  async moveThrough(waypoints, options = {}) {
    known(options, ['toleranceDeg', 'timeoutMs', 'telemetryTimeoutMs', 'gain', 'minSpeed', 'maxSpeed'], 'moveThrough');
    if (!Array.isArray(waypoints) || !waypoints.length) throw new TypeError('moveThrough requires waypoints');
    const points = waypoints.map(point => {
      known(point, ['pan', 'tilt', 'roll', 'holdMs'], 'waypoint');
      const { holdMs = 0, ...target } = point;
      if (!Number.isFinite(holdMs) || holdMs < 0 || holdMs > 0x7fffffff) throw new RangeError('holdMs must be non-negative and within timer range');
      return { settings: positionSettings({ ...options, ...target }), holdMs };
    });
    return this._run('moveThrough', async operation => {
      const results = [];
      try {
        for (let index = 0; index < points.length; index++) {
          this._trajectoryProgress = { kind: 'waypoints', index, count: points.length };
          results.push(await this._moveTo(points[index].settings, operation));
          await this._stop(); check(operation.controller.signal);
          await delay(points[index].holdMs, operation.controller.signal);
        }
        return results;
      } finally { this._trajectoryProgress = null; }
    });
  }

  async captureHome(options = {}) {
    const reading = await this.getJointAngles(options);
    this._home = { ...axes(reading), timestamp: reading.timestamp, deviceId: this.deviceId };
    return this.home;
  }

  async moveHome(options = {}) {
    known(options, ['axes', 'toleranceDeg', 'timeoutMs', 'telemetryTimeoutMs', 'gain', 'minSpeed', 'maxSpeed'], 'moveHome');
    if (!this._home || this._home.deviceId !== this.deviceId) throw failure('RS4MINI_HOME_UNSET', 'Capture home for this device first');
    const { axes: selected = ['pan', 'tilt', 'roll'], ...settings } = options;
    if (!Array.isArray(selected) || !selected.length || selected.some(axis => !['pan', 'tilt', 'roll'].includes(axis)) || new Set(selected).size !== selected.length)
      throw new TypeError('axes must contain distinct pan, tilt or roll names');
    return this.moveTo({ ...settings, ...Object.fromEntries(selected.map(axis => [axis, this._home[axis]])) });
  }
}
