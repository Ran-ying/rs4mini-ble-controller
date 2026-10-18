// Current-App source candidate; independent from 04:08 response and 6E auto-tune.
import {bytes,hex} from './bytes.js';
import {APP_PROFILE} from './app-protocol.js';
const states=new Map([[0,'COMPLETE'],[1,'PROCESSING'],[3,'FAIL'],[9,'OTHER']]);
export function sensorCalibrationNotification(message) {
  if(!message || message.sender!==4 || message.receiver!==2 || message.commandSet!==4 || message.commandId!==48 || !Number.isInteger(message.flags) || message.flags<0 || message.flags>255 || (message.flags&0x87) || !(message.payload instanceof Uint8Array) || message.payload.length<2)return null;
  const body=bytes(message.payload),rawStatus=body[1];
  return {kind:'sensorCalibration',profile:APP_PROFILE,commandId:48,timestamp:Date.now(),rawProgressValue:body[0],rawStatus,sourceStatus:states.get(rawStatus)??'OTHER',sourceStatusKnown:states.has(rawStatus),bodyHex:hex(body),trailingHex:hex(body.subarray(2)),deviceVerified:false,modelLayoutVerified:false,progressUnitVerified:false,requestAssociationVerified:false,physicalCompletionVerified:false};
}
