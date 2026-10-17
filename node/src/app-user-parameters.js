// Source fixed-layout push; target model/firmware compatibility is unverified.
import {bytes,hex} from './bytes.js';
import {APP_PROFILE} from './app-protocol.js';
const fields=[["getPitchAccel",59,2],["getPitchDeadband",21,2],["getPitchSmoothTrack",70,1],["getPitchSpeed",13,2],["getPresetID",2,1],["getRollAccel",63,2],["getRollDeadband",51,2],["getRollSmoothTrack",73,1],["getRollSpeed",47,2],["getStickPitchSmooth",37,2],["getStickPitchSpeed",29,2],["getStickYawSmooth",33,2],["getStickYawSpeed",25,2],["getYawAccel",55,2],["getYawDeadband",17,2],["getYawSmoothTrack",67,1],["getYawSpeed",9,2]];
const presets={0:'CUSTOM_1',1:'CUSTOM_2',3:'FAST',4:'MEDIUM',5:'SLOW'};
export function userParameterNotification(message) {
  if (!message || message.sender!==4 || message.receiver!==2 || message.commandSet!==4 || message.commandId!==0x24 || !Number.isInteger(message.flags) || message.flags<0 || message.flags>255 || (message.flags&0x87)) return null;
  if (!(message.payload instanceof Uint8Array)) return null;
  const body=bytes(message.payload);
  if (body.length<74) return null;
  const values=fields.map(([sourceGetter,offset,size])=>({sourceGetter,offset,size,rawValue:body[offset]+(size===2?256*body[offset+1]:0),rawHex:hex(body.subarray(offset,offset+size))}));
  const rawValue=values.find(row=>row.sourceGetter==='getPresetID').rawValue;
  return {kind:'userParameters',profile:APP_PROFILE,timestamp:Date.now(),values,preset:{rawValue,sourceEnum:presets[rawValue]??null},bodyHex:hex(body),deviceVerified:false,modelLayoutVerified:false,activePresetVerified:false,physicalCompletionVerified:false};
}
