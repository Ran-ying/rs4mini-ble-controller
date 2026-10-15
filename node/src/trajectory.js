// Pure trajectory validation/interpolation; scheduling uses the controller's monotonic clock.
export function velocityKeyframes(input, interpolation) {
  if (!['linear', 'smoothstep', 'step'].includes(interpolation)) throw new TypeError('interpolation must be linear, smoothstep or step');
  if (!Array.isArray(input) || input.length < 2) throw new TypeError('trajectory requires at least two keyframes');
  let previous = -1;
  const frames = input.map((point, index) => {
    if (!point || typeof point !== 'object' || Array.isArray(point) ||
      Object.keys(point).some(key => !['timeMs', 'pan', 'tilt', 'roll'].includes(key))) throw new TypeError('invalid trajectory keyframe');
    if (!Number.isFinite(point.timeMs) || point.timeMs > 0x7fffffff || point.timeMs <= previous || (index === 0 && point.timeMs !== 0))
      throw new RangeError('keyframe times must start at zero and strictly increase');
    previous = point.timeMs;
    const result = { timeMs: point.timeMs };
    for (const axis of ['pan', 'tilt', 'roll']) {
      const value = point[axis] ?? 0;
      if (!Number.isFinite(value) || Math.abs(value) > 1) throw new RangeError(`${axis} must be in -1..1`);
      result[axis] = value;
    }
    return result;
  });
  return frames;
}

export function interpolateVelocity(frames, timeMs, interpolation) {
  let index = 0;
  while (index < frames.length - 2 && frames[index + 1].timeMs <= timeMs) index++;
  const a = frames[index], b = frames[index + 1];
  let ratio = Math.max(0, Math.min(1, (timeMs - a.timeMs) / (b.timeMs - a.timeMs)));
  if (interpolation === 'step') ratio = timeMs >= b.timeMs ? 1 : 0;
  if (interpolation === 'smoothstep') ratio = ratio * ratio * (3 - 2 * ratio);
  return Object.fromEntries(['pan', 'tilt', 'roll'].map(axis => [axis, a[axis] + (b[axis] - a[axis]) * ratio]));
}
