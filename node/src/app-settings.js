// Named bitfields from the current App's Ronin2 abstraction, inherited by HG724.
// Source layout only: no device effect or PF/PTF preset is inferred.
import { bytes } from './bytes.js';
import { failure } from './async.js';
const schemas = {
  customFollow: { index: 132, max: 15, mask: 15, fields: { enabled: 1, pitch: 2, roll: 4, yaw: 8 } },
  motor: { index: 35, max: 255, mask: 113, fields: { enabled: 1, forbidSelfie: 16, forbidVertical: 32, roll360: 64 } },
};
export function settingsSchema(kind) {
  const schema = Object.hasOwn(schemas, kind) && schemas[kind];
  if (!schema) throw new TypeError('Unknown App setting group');
  return schema;
}
export function settingsPatch(kind, patch) {
  const schema = settingsSchema(kind);
  if (!patch || typeof patch !== 'object' || Array.isArray(patch) || !Object.keys(patch).length ||
      Object.keys(patch).some(key => !Object.hasOwn(schema.fields, key) || typeof patch[key] !== 'boolean'))
    throw new TypeError('Settings require at least one named boolean field');
  return { ...patch };
}
export function decodeSettings(result, kind) {
  const schema = settingsSchema(kind), rawValue = parseInt(result.parameters[0].rawHex, 16), settings = {};
  for (const [key, bit] of Object.entries(schema.fields))
    settings[key] = kind === 'motor' && key === 'enabled' ? !(rawValue & bit) : !!(rawValue & bit);
  return { ...result, settings, rawValue, unknownBits: rawValue & (255 ^ schema.mask) };
}
export function settingsWrite(kind, patch, rawValue) {
  const schema = settingsSchema(kind); patch = settingsPatch(kind, patch);
  if (!Number.isInteger(rawValue) || rawValue < 0 || rawValue > schema.max)
    throw failure('RS4MINI_UNSUPPORTED_VALUE', 'Current settings exceed the source setter range; no write sent');
  let value = rawValue;
  for (const [key, enabled] of Object.entries(patch)) {
    const bit = schema.fields[key], set = kind === 'motor' && key === 'enabled' ? !enabled : enabled;
    value = set ? value | bit : value & (255 ^ bit);
  }
  return { payload: bytes([schema.index, 1, value]), requestedRawValue: value };
}
