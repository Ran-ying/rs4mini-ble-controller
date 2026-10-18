// HG702 override inherited by HG724; source code is not physical validation.
import { bytes, hex } from './bytes.js';
import { failure } from './async.js';
import { APP_PROFILE, appReply } from './app-protocol.js';
const states = { 0: 'UnStart', 1: 'Processing', 2: 'Complete', 3: 'Failure', 255: 'UnKnown' };
export function autoTunePayload(start) {
  if (typeof start !== 'boolean') throw new TypeError('start must be boolean');
  return bytes([0, 1, Number(start)]);
}
export function calibrationRecords(body) {
  const invalid = () => failure('RS4MINI_PROTOCOL_ERROR', 'Malformed current-App calibration records');
  if (body.length && ![0, 1].includes(body[0])) throw invalid();
  const records = []; let offset = 0, rawState = null, rawPercent = null;
  while (offset < body.length) {
    if (offset + 2 > body.length) throw invalid();
    const tag = body[offset++], size = body[offset++];
    if (size > 127 || offset + size > body.length || (tag === 0 && size < 2)) throw invalid();
    const value = body.subarray(offset, offset + size);
    records.push({ tag, size, rawHex: hex(value) });
    if (tag === 0) { rawState = value[0]; rawPercent = value[1]; }
    offset += size;
  }
  return { records, rawState, state: Object.hasOwn(states, rawState) ? states[rawState] : null,
    rawPercent, percent: rawPercent !== null && rawPercent <= 100 ? rawPercent : null, bodyHex: hex(body) };
}
export function calibrationReply(message) {
  const ack = appReply(message, 0x6e);
  return { ...ack, calibration: calibrationRecords(message.payload.subarray(1)) };
}
export function calibrationNotification(message) {
  if (message.sender !== 4 || message.receiver !== 2 || message.commandSet !== 4 || message.commandId !== 0x6e || !Number.isInteger(message.flags) || message.flags<0 || message.flags>255 || (message.flags & 0x87)) return null;
  try {
    const calibration = calibrationRecords(message.payload);
    if (calibration.rawState === null) return null; // Unknown-only records never reset known progress to zero.
    return { ...calibration, kind: 'calibration', profile: APP_PROFILE, deviceVerified: false,
      physicalCompletionVerified: false, timestamp: Date.now() };
  } catch { return null; }
}
