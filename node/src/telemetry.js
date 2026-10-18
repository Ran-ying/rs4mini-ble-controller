import { crc8, crc16 } from "./protocol.js";
import { bytes as byteArray, view, hex, concat } from "./bytes.js";

const MIN_FRAME_LENGTH = 13;
const MAX_FRAME_LENGTH = 0x3ff;

export function parseDumlFrame(bytes) {
  const packet = byteArray(bytes);
  if (packet.length < MIN_FRAME_LENGTH) throw new RangeError("DUML frame is too short");
  if (packet[0] !== 0x55) throw new Error("DUML frame does not start with 0x55");

  const length = packet[1] | ((packet[2] & 0x03) << 8);
  if (length !== packet.length) throw new Error(`DUML length mismatch: header=${length}, actual=${packet.length}`);
  if (crc8(packet.subarray(0, 3)) !== packet[3]) throw new Error("DUML header CRC8 mismatch");

  const expectedCrc = view(packet).getUint16(packet.length - 2, true);
  const actualCrc = crc16(packet.subarray(0, packet.length - 2));
  if (actualCrc !== expectedCrc) throw new Error("DUML frame CRC16 mismatch");

  return {
    raw: packet,
    length,
    sender: packet[4],
    receiver: packet[5],
    sequence: view(packet).getUint16(6, true),
    flags: packet[8],
    commandSet: packet[9],
    commandId: packet[10],
    payload: packet.subarray(11, packet.length - 2),
  };
}

export class DumlStreamDecoder {
  constructor({ maxBufferedBytes = 8192 } = {}) {
    if (!Number.isInteger(maxBufferedBytes) || maxBufferedBytes < 13) throw new RangeError("maxBufferedBytes must be an integer >= 13");
    this.maxBufferedBytes = maxBufferedBytes;
    this.buffer = byteArray(0);
    this.discardedBytes = 0;
    this.invalidFrames = 0;
  }

  reset() {
    this.buffer = byteArray(0);
    this.discardedBytes = 0;
    this.invalidFrames = 0;
  }

  push(chunk) {
    if (!chunk?.length) return [];
    this.buffer = concat([this.buffer, byteArray(chunk)]);
    if (this.buffer.length > this.maxBufferedBytes) {
      const keepFrom = Math.max(0, this.buffer.lastIndexOf(0x55));
      this.discardedBytes += keepFrom;
      this.buffer = this.buffer.subarray(keepFrom);
      if (this.buffer.length > this.maxBufferedBytes) {
        this.discardedBytes += this.buffer.length;
        this.buffer = byteArray(0);
      }
    }

    const messages = [];
    while (this.buffer.length) {
      const start = this.buffer.indexOf(0x55);
      if (start < 0) {
        this.discardedBytes += this.buffer.length;
        this.buffer = byteArray(0);
        break;
      }
      if (start > 0) {
        this.discardedBytes += start;
        this.buffer = this.buffer.subarray(start);
      }
      if (this.buffer.length < 4) break;

      const length = this.buffer[1] | ((this.buffer[2] & 0x03) << 8);
      const headerValid = length >= MIN_FRAME_LENGTH && length <= MAX_FRAME_LENGTH &&
        crc8(this.buffer.subarray(0, 3)) === this.buffer[3];
      if (!headerValid) {
        this.invalidFrames++;
        this.discardedBytes++;
        this.buffer = this.buffer.subarray(1);
        continue;
      }
      if (this.buffer.length < length) break;

      const candidate = this.buffer.subarray(0, length);
      try {
        messages.push(parseDumlFrame(candidate));
        this.buffer = this.buffer.subarray(length);
      } catch {
        this.invalidFrames++;
        this.discardedBytes++;
        this.buffer = this.buffer.subarray(1);
      }
    }
    return messages;
  }
}

export function decodeGimbalTelemetry(message) {
  if (!message || message.commandSet !== 0x04 || message.commandId !== 0x05 || !Number.isInteger(message.flags) || message.flags<0 || message.flags>255 || (message.flags&0x87)) return null;
  if (message.payload.length < 6) return null;

  const attitudeRaw = {
    pitch: view(message.payload).getInt16(0, true),
    roll: view(message.payload).getInt16(2, true),
    yaw: view(message.payload).getInt16(4, true),
  };
  const attitude = {
    pitch: attitudeRaw.pitch / 10,
    roll: attitudeRaw.roll / 10,
    yaw: attitudeRaw.yaw / 10,
    unit: "deg",
    wrap: 180,
    raw: attitudeRaw,
  };

  // RS 4 Mini 49-byte profile, verified with independent Pan/Tilt/Roll runs:
  // joint yaw is centidegrees at +16; pitch/roll are decidegrees at +20/+22.
  let jointAngles = null;
  if (message.payload.length >= 24) {
    const raw = {
      pitch: view(message.payload).getInt16(20, true),
      roll: view(message.payload).getInt16(22, true),
      yaw: view(message.payload).getInt16(16, true),
    };
    jointAngles = {
      pitch: raw.pitch / 10,
      roll: raw.roll / 10,
      yaw: raw.yaw / 100,
      unit: "deg",
      raw,
    };
  }

  // These four floats have unit norm in captures. Keep their order explicitly
  // unverified until DJI's RS 4 Mini coordinate convention is established.
  let orientationQuaternion = null;
  if (message.payload.length >= 40) {
    const components = [24, 28, 32, 36].map(offset => view(message.payload).getFloat32(offset, true));
    orientationQuaternion = {
      components,
      norm: Math.hypot(...components),
      componentOrder: "unverified",
    };
  }

  return {
    kind: "gimbal-telemetry",
    verified: true,
    // Backward-compatible flat fields; new code should use attitude.
    pitch: attitude.pitch,
    roll: attitude.roll,
    yaw: attitude.yaw,
    raw: attitudeRaw,
    attitude,
    jointAngles,
    orientationQuaternion,
    modeFlags: message.payload.length >= 7 ? message.payload[6] : null,
    rollAdjust: message.payload.length >= 8 ? view(message.payload).getInt8(7) : null,
    yawAngle: message.payload.length >= 10 ? view(message.payload).getInt16(8, true) / 10 : null,
    limitFlags: message.payload.length >= 11 ? message.payload[10] : null,
    stateFlags: message.payload.length >= 12 ? message.payload[11] : null,
    payloadHex: hex(message.payload),
    sequence: message.sequence,
    timestamp: message.receivedAt ?? Date.now(),
  };
}

// Kept for source compatibility with the 0.2.x experimental API.
export function decodeGimbalPositionCandidate(message) {
  return decodeGimbalTelemetry(message);
}
