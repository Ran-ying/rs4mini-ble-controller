// Current Ronin 2.2.2 source codecs. Source evidence is not hardware validation.
import { bytes, hex } from './bytes.js';
import { failure } from './async.js';
export const APP_PROFILE = 'ronin-2.2.2';
const copyMessage = message => ({ ...message, raw: bytes(message.raw), payload: bytes(message.payload) });
export function appProfile(profile) {
  if (profile !== APP_PROFILE) throw new TypeError('Select explicit ronin-2.2.2 source profile');
  return profile;
}
export function parameterContext(parameters) {
  if (!Array.isArray(parameters) || !parameters.length || parameters.length > 64) throw new RangeError('parameters must contain 1..64 explicit index/size records');
  return parameters.map(record => {
    if (!record || typeof record !== 'object' || Array.isArray(record) || Object.keys(record).some(key => !['index', 'size'].includes(key))) throw new TypeError('parameter record requires index and size only');
    const { index, size } = record;
    if (!Number.isInteger(index) || index < 0 || index > 255 || ![1, 2, 4, 8].includes(size)) throw new RangeError('index must be 0..255 and size 1/2/4/8');
    return { index, size };
  });
}
export const parameterRequest = context => bytes(parameterContext(context).map(record => record.index));
export function sensitivityPayload(mode) {
  if (!Number.isInteger(mode) || ![0, 1].includes(mode)) throw new RangeError('follow sensitivity mode must be 0 or 1');
  return bytes([150, 1, mode]);
}
export function appReply(message, commandId) {
  if (!message || message.sender !== 4 || message.receiver !== 2 || message.commandSet !== 4 || message.commandId !== commandId || !(message.flags & 0x80) || !message.payload?.length)
    throw failure('RS4MINI_PROTOCOL_ERROR', 'Expected a correlated App response with status byte');
  const statusCode = message.payload[0];
  if (statusCode !== 0) throw failure('RS4MINI_DEVICE_ERROR', `Device returned status ${statusCode}`, { statusCode, response: copyMessage(message) });
  return { profile: APP_PROFILE, deviceVerified: false, physicalCompletionVerified: false,
    statusCode, acknowledged: true, bodyHex: hex(message.payload.subarray(1)), message: copyMessage(message) };
}
export function parameterReply(message, parameters) {
  const context = parameterContext(parameters), result = appReply(message, 0x10), body = message.payload.subarray(1);
  const records = []; let offset = 0;
  for (const { index, size } of context) {
    if (offset + 2 + size > body.length || body[offset] !== index) throw failure('RS4MINI_PROTOCOL_ERROR', 'Parameter response does not match request context');
    // App skips this byte, and uses external metadata size. Keep it raw.
    records.push({ index, size, headerByte: body[offset + 1], rawHex: hex(body.subarray(offset + 2, offset + 2 + size)) });
    offset += 2 + size;
  }
  if (offset !== body.length) throw failure('RS4MINI_PROTOCOL_ERROR', 'Unconsumed parameter response bytes');
  return { ...result, parameters: records };
}
