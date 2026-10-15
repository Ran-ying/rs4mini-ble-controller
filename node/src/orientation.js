// Mathematical convention: right-handed intrinsic Z-Y-X (yaw, pitch, roll).
// This does not establish the device's quaternion order or physical frame.
const deg = 180 / Math.PI;
export function orientationFromComponents(components, { componentOrder, conjugate = false } = {}) {
  if (!['wxyz', 'xyzw'].includes(componentOrder)) throw new TypeError('componentOrder must explicitly be wxyz or xyzw');
  if (typeof conjugate !== 'boolean') throw new TypeError('conjugate must be boolean');
  if (!Array.isArray(components) || components.length !== 4 || !components.every(Number.isFinite)) throw new TypeError('four finite quaternion components required');
  const norm = Math.hypot(...components);
  if (!Number.isFinite(norm) || norm < 1e-12) throw new RangeError('quaternion norm is zero or non-finite');
  let [w, x, y, z] = (componentOrder === 'wxyz' ? components : [components[3], ...components.slice(0, 3)]).map(value => value / norm);
  if (conjugate) { x = -x; y = -y; z = -z; }
  return { quaternion: { w, x, y, z }, inputNorm: norm,
    euler: { roll: Math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)) * deg,
      pitch: Math.asin(Math.max(-1, Math.min(1, 2 * (w * y - z * x)))) * deg,
      yaw: Math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)) * deg },
    componentOrder, conjugate, convention: 'right-handed-intrinsic-ZYX', deviceConventionVerified: false };
}
