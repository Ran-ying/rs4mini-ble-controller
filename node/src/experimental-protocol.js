// RS 3 / RS 3 Mini research profiles, NOT hardware-verified RS 4 Mini commands.
// Provenance and model differences are recorded in docs/PROTOCOL.md.
import { bytes, view, hex } from './bytes.js';
import { frame } from './protocol.js';

export function researchProfile(profile) {
  if (!['rs3', 'rs3mini'].includes(profile)) throw new TypeError('Select an explicit rs3 or rs3mini research profile');
  return profile;
}
function byte(value, name) {
  if (!Number.isInteger(value) || value < 0 || value > 255) throw new RangeError(`${name} must be a byte`);
  return value;
}
function tenths(value, name, limit) {
  if (!Number.isFinite(value) || Math.abs(value) > limit) throw new RangeError(`${name} must be finite and in -${limit}..${limit}`);
  return Math.round(value * 10);
}
export function rs3AbsoluteFrame(sequence, { pan, roll, tilt, parameterByte } = {}) {
  const payload = bytes(8); let flags = 1, supplied = 0;
  for (const [axis, value, offset, invalid] of [['pan', pan, 0, 2], ['roll', roll, 2, 4], ['tilt', tilt, 4, 8]]) {
    if (value === undefined) flags |= invalid;
    else { view(payload).setInt16(offset, tenths(value, axis, 180), true); supplied++; }
  }
  if (!supplied) throw new TypeError('at least one absolute angle is required');
  payload[6] = flags; payload[7] = byte(parameterByte, 'parameterByte');
  return frame(sequence, 4, 0x14, payload, 0x40);
}
export function rs3RateFrame(sequence, { pan = 0, roll = 0, tilt = 0 } = {}, release = false) {
  if (typeof release !== 'boolean') throw new TypeError('release must be boolean');
  const payload = bytes(7);
  for (const [axis, value, offset] of [['pan', pan, 0], ['roll', roll, 2], ['tilt', tilt, 4]])
    view(payload).setInt16(offset, tenths(value, axis, 360), true);
  payload[6] = release ? 0 : 0x80;
  return frame(sequence, 4, 0x0c, payload, 0x40);
}
export function researchSleepFrame(sequence, profile, asleep) {
  researchProfile(profile);
  if (typeof asleep !== 'boolean') throw new TypeError('asleep must be boolean');
  return frame(sequence, 4, 0x0f, bytes([0x23, 1, (profile === 'rs3mini' ? 0x10 : 0) | Number(asleep)]), 0x40);
}
export function decodeResearchStatus(message, profile) {
  researchProfile(profile);
  if (!message || message.receiver !== 2) return null;
  const p = message.payload, v = view(p);
  const base = { profile, deviceVerified: false, timestamp: message.receivedAt ?? Date.now(), payloadHex: hex(p) };
  if (message.sender === 4 && message.commandSet === 4) {
    if (message.commandId === 0x27 && p.length === 5 && p.slice(0, 4).every(value => value === 0) && p[4] <= 1)
      return { ...base, kind: 'sleep', asleep: p[4] === 1 };
    if (message.commandId === 0x0f && p.length === 4 && p[0] === 0 && p[1] === 0x23 && p[2] === 1 &&
      (profile === 'rs3mini' ? [0x10, 0x11] : [0, 1]).includes(p[3]))
      return { ...base, kind: 'sleep', asleep: !!(p[3] & 1) };
    if (message.commandId === 0x30 && p.length === 2 && p[0] <= 100 && p[1] <= 1)
      return { ...base, kind: 'calibration', percent: p[0], inProgress: !!p[1] };
  }
  if (message.sender !== 0xe5) return null;
  if (message.commandSet === 0x0d && message.commandId === 2 && p.length >= 17) {
    const fields = [1, 5, 9, 13].map(offset => v.getInt32(offset, true));
    return { ...base, kind: 'battery-status', rawFields: fields,
      batteryPercent: profile === 'rs3mini' && p.length === 21 && p[20] <= 100 ? p[20] : null };
  }
  if (message.commandSet === 4 && message.commandId === 0x66 && p.length >= 1) {
    const fields = []; let offset = 1;
    while (offset < p.length) {
      if (offset + 2 > p.length) return null;
      const tag = p[offset++], size = p[offset++];
      if (!size || offset + size > p.length) return null;
      fields.push({ tag, size, rawHex: hex(p.subarray(offset, offset + size)) }); offset += size;
    }
    // Keep TLV values raw: do not substitute another model's layout for RS 4 Mini joints.
    return { ...base, kind: 'status-tlv', header: p[0], fields };
  }
  return null;
}
