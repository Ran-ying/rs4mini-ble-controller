// Explicit HG724 source AUTO action; no physical execution/completion claim.
import {bytes,hex} from './bytes.js';
import {appReply} from './app-protocol.js';
const parts=['AUTO','JOINT_ANGLE','HALL_LINEAR','JOINT_ANGLE_CAMERA','JOINT_ANGLE_FIXTURE','GYRO','ACCELERATION','COMPASS','IMU_AND_SENSOR','SHOCK_PLATE'];
const states=['FAIL','SUCCESS','PROCESSING'];
export function componentCalibrationPayload(sourcePart){
  if(sourcePart!=='AUTO')throw new TypeError('Only explicit sourcePart AUTO has the selected HG724 action path');
  return bytes([0]);
}
export function componentCalibrationReply(message,motorRawValue){
  const ack=appReply(message,8),body=message.payload.subarray(1),businessComplete=body.length>=2;
  const calibration=businessComplete?{rawPart:body[0],sourcePart:parts[body[0]]??'AUTO',sourcePartKnown:body[0]<parts.length,rawStatus:body[1],sourceStatus:states[body[1]]??'PROCESSING',sourceStatusKnown:body[1]<states.length,bodyHex:hex(body),trailingHex:hex(body.subarray(2))}:null;
  return {...ack,requestedSourcePart:'AUTO',motorPreflightRawValue:motorRawValue,motorPreflightEnabled:!(motorRawValue&1),businessComplete,calibration,responsePartMatchesRequested:businessComplete?body[0]===0:null,modelLayoutVerified:false,motorStatePhysicalVerified:false,businessRequestAssociationVerified:false,firmwareAbortVerified:false};
}
