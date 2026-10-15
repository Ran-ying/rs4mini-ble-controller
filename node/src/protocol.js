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
  const normalized = Math.max(-1, Math.min(1, Number(value) || 0));
  return 1024 + Math.round(normalized * 660);
}

export function frame(sequence, commandSet, commandId, payload = Buffer.alloc(0), flags = 0) {
  const body = Buffer.from(payload);
  const total = 13 + body.length;
  if (total > 0x3ff) throw new RangeError("DUML frame is too long");
  const packet = Buffer.alloc(total);
  packet[0] = 0x55;
  packet[1] = total & 0xff;
  packet[2] = 0x04 | ((total >>> 8) & 0x03);
  packet[3] = crc8(packet.subarray(0, 3));
  packet[4] = APP;
  packet[5] = GIMBAL;
  packet.writeUInt16LE(sequence & 0xffff, 6);
  packet[8] = flags;
  packet[9] = commandSet;
  packet[10] = commandId;
  body.copy(packet, 11);
  packet.writeUInt16LE(crc16(packet.subarray(0, total - 2)), total - 2);
  return packet;
}

export function velocityFrame(sequence, { pan = 0, tilt = 0, roll = 0 } = {}) {
  const payload = Buffer.alloc(9);
  payload.writeInt16LE(rcUnits(tilt), 0);
  payload.writeInt16LE(rcUnits(roll), 2);
  payload.writeInt16LE(rcUnits(pan), 4);
  payload.writeInt16LE(0, 6);
  payload[8] = 0x02;
  return frame(sequence, 0x04, 0x01, payload);
}

export function stopFrame(sequence) {
  return velocityFrame(sequence);
}

export function recenterFrame(sequence) {
  return frame(sequence, 0x04, 0x4c, Buffer.from([0xfe, 0x01]), 0x40);
}
