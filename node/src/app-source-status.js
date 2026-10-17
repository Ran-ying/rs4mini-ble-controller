// Source candidates only; no target alarms, completion or control decisions.
import {bytes,hex} from './bytes.js';
import {APP_PROFILE} from './app-protocol.js';
const fields=[["getFanDirection",2,1,1,false],["getGimbalDirectionWhenVertical",2,5,1,false],["getGimbalGravity",3,1,3,false],["getSleepMode",4,0,1,false],["getVerticalDirection",2,2,1,false],["isErrorRecentOrSelfie",1,6,1,true],["isErrorRecentWhenStartUp",1,3,1,true],["isInFlashlight",2,3,1,true],["isJointLockAfterStartup",1,0,1,true],["isJointLockWhenStartup",1,1,1,true],["isMotorProtected",1,2,1,true],["isPanoReady",1,7,1,true],["isPhoneOutGimbal",3,0,1,true],["isPitchLimitedInTracking",3,6,1,true],["isPitchLocked",0,1,1,true],["isPortrait",2,4,1,true],["isRollLocked",0,0,1,true],["isUpgrading",1,4,1,true],["isYawLimit",1,5,1,true],["isYawLimitedInTracking",3,5,1,true],["isYawLocked",0,2,1,true]];
export function sourceStatusNotification(message) {
  if (!message || message.sender!==4 || message.receiver!==2 || message.commandSet!==4 || ![0x27,0x33].includes(message.commandId) || !Number.isInteger(message.flags) || message.flags<0 || message.flags>255 || (message.flags&0x87)) return null;
  if (!(message.payload instanceof Uint8Array)) return null;
  const body=bytes(message.payload),abnormal=message.commandId===0x27;
  if (body.length<(abnormal?5:1)) return null;
  const common={profile:APP_PROFILE,timestamp:Date.now(),bodyHex:hex(body),deviceVerified:false,modelLayoutVerified:false,physicalCompletionVerified:false};
  if (!abnormal) return {...common,kind:'battery',rawCapacityValue:body[0],sourceGetter:'getCapacityPercentage'};
  const sourceValues=Object.fromEntries(fields.map(([name,offset,shift,mask,boolean])=>{const value=(body[offset]>>shift)&mask;return [name,boolean?!!value:value];}));
  sourceValues.isGimbalLocked=sourceValues.isRollLocked||sourceValues.isPitchLocked;
  return {...common,kind:'abnormal',sourceValues};
}
