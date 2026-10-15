export function known(options, allowed, method) {
  if (!options || typeof options !== 'object' || Array.isArray(options)) throw new TypeError(`${method} options must be an object`);
  const unknown = Object.keys(options).filter(key => !allowed.includes(key));
  if (unknown.length) throw new TypeError(`${method} received unknown option${unknown.length > 1 ? 's' : ''}: ${unknown.join(', ')}`);
}
export function positive(value, name) { if (!Number.isFinite(value) || value <= 0) throw new RangeError(`${name} must be greater than 0`); }
export function axisValue(value, name) {
  const number = Number(value); if (!Number.isFinite(number)) throw new TypeError(`${name} must be a finite number`); return number;
}
export function velocity(options) {
  known(options, ['pan', 'tilt', 'roll'], 'setVelocity');
  return Object.fromEntries(['pan', 'tilt', 'roll'].map(axis => [axis, Math.max(-1, Math.min(1, axisValue(options[axis] ?? 0, axis)))]));
}
