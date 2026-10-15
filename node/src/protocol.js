import { bytes, view } from './bytes.js';
const APP = 0x02;
const GIMBAL = 0x04;

export function crc8(bytes) {
  let value = 0x77;
  for (const byte of bytes) {
    value ^= byte;
    for (let bit = 0; bit < 8; bit++) value = value & 1 ? (value >>> 1) ^ 0x8c : value >>> 1;
  }
  return value & 0xff;
}

export function crc16(bytes) {
  let value = 0x3692;
  for (const byte of bytes) {
    value ^= byte;
    for (let bit = 0; bit < 8; bit++) value = value & 1 ? (value >>> 1) ^ 0x8408 : value >>> 1;
  }
  return value & 0xffff;
}

function rcUnits(value) {
  if (!Number.isFinite(Number(value))) throw new TypeError('Axis input must be finite');
  const normalized = Math.max(-1, Math.min(1, Number(value)));
  return 1024 + Math.round(normalized * 660);
}

export function frame(sequence, commandSet, commandId, payload = bytes(0), flags = 0) {
  const body = bytes(payload);
  const total = 13 + body.length;
  if (total > 0x3ff) throw new RangeError("DUML frame is too long");
  const packet = bytes(total);
  packet[0] = 0x55;
  packet[1] = total & 0xff;
  packet[2] = 0x04 | ((total >>> 8) & 0x03);
  packet[3] = crc8(packet.subarray(0, 3));
  packet[4] = APP;
  packet[5] = GIMBAL;
  view(packet).setUint16(6, sequence & 0xffff, true);
  packet[8] = flags;
  packet[9] = commandSet;
  packet[10] = commandId;
  packet.set(body, 11);
  view(packet).setUint16(total - 2, crc16(packet.subarray(0, total - 2)), true);
  return packet;
}

export function velocityFrame(sequence, { pan = 0, tilt = 0, roll = 0 } = {}) {
  const payload = bytes(9);
  view(payload).setInt16(0, rcUnits(tilt), true);
  view(payload).setInt16(2, rcUnits(roll), true);
  view(payload).setInt16(4, rcUnits(pan), true);
  view(payload).setInt16(6, 0, true);
  payload[8] = 0x02;
  return frame(sequence, 0x04, 0x01, payload);
}

export function stopFrame(sequence) {
  return velocityFrame(sequence);
}

export function recenterFrame(sequence) {
  return frame(sequence, 0x04, 0x4c, bytes([0xfe, 0x01]), 0x40);
}
