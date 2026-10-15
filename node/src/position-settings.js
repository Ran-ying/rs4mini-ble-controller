import { known, positive, axisValue } from './values.js';

export function positionSettings(options) {
  known(options, ['pan', 'tilt', 'roll', 'toleranceDeg', 'timeoutMs', 'telemetryTimeoutMs', 'gain', 'minSpeed', 'maxSpeed'], 'moveTo');
  const { toleranceDeg = 1, timeoutMs = 30000, telemetryTimeoutMs = 3000, gain = 0.02, minSpeed = 0.05, maxSpeed = 0.18 } = options;
  for (const [name, value] of Object.entries({ toleranceDeg, timeoutMs, telemetryTimeoutMs, gain })) positive(value, name);
  if (![minSpeed, maxSpeed].every(value => Number.isFinite(value) && value >= 0 && value <= 1) || minSpeed > maxSpeed)
    throw new RangeError('speeds must satisfy 0 <= minSpeed <= maxSpeed <= 1');
  const target = {};
  for (const axis of ['pan', 'tilt', 'roll']) if (options[axis] !== undefined) {
    const angle = axisValue(options[axis], axis);
    if (angle < -180 || angle > 180) throw new RangeError(`${axis} must be between -180 and 180 degrees`);
    target[axis] = angle;
  }
  if (!Object.keys(target).length) throw new TypeError('moveTo requires at least one of pan, tilt, or roll');
  return { target, toleranceDeg, timeoutMs, telemetryTimeoutMs, gain, minSpeed, maxSpeed };
}
