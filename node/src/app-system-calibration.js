// App's system_calc auto-calibration, distinct from motor auto-tune 6A/6E.
import { bytes } from './bytes.js';
export const systemCalibrationPayload = () => bytes([36,1,1]);
export function systemCalibrationFields(rawValue) {
  if (!Number.isInteger(rawValue) || rawValue<0 || rawValue>255) throw new RangeError('system calibration byte required');
  return {rawValue,state:['DEFAULT','START','FAIL','SUCCESS'][rawValue] ?? null};
}
export function systemCalibrationReply(reply) {
  return {...reply,systemCalibration:systemCalibrationFields(parseInt(reply.parameters[0].rawHex,16))};
}
