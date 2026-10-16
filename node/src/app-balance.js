// Named balance_test register, source evidence only; no firmware task ownership.
import { bytes } from './bytes.js';
export const balanceStartPayload = () => bytes([37,1,64]);
export function balanceFields(rawValue) {
  if (!Number.isInteger(rawValue) || rawValue<0 || rawValue>255) throw new RangeError('balance byte required');
  const stateCode=rawValue>>>6, state=['DEFAULT','TESTING','FINISH','ERROR'][stateCode];
  const axisResults={};
  for (const [axis,shift] of [['roll',4],['pitch',2],['yaw',0]]) {
    const rawValueForAxis=(rawValue>>>shift)&3;
    axisResults[axis]={rawValue:rawValueForAxis,result:rawValueForAxis===0?null:['PASS','MARGINAL','FAIL'][rawValueForAxis-1]};
  }
  return {rawValue,stateCode,state,axisResults,axisFieldsValid:Object.values(axisResults).every(row=>row.result!==null)};
}
export function balanceReply(reply) {
  return {...reply,balance:balanceFields(parseInt(reply.parameters[0].rawHex,16))};
}
