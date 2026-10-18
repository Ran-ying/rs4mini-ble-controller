// Passive source candidate. Raw speed names imply no unit, reference frame or control.
import {bytes,hex,view} from './bytes.js';
import {APP_PROFILE} from './app-protocol.js';
const controlTypes=new Map([[1,'CommonStick'],[2,'RockWheel'],[3,'Sensor'],[7,'Other']]);
export function externalDeviceNotification(message) {
  if(!message || message.sender!==4 || message.receiver!==2 || message.commandSet!==4 || message.commandId!==105 || !Number.isInteger(message.flags) || message.flags<0 || message.flags>255 || (message.flags&0x87) || !(message.payload instanceof Uint8Array) || message.payload.length<2)return null;
  const body=bytes(message.payload),records=[];
  for(let offset=0;offset<body.length;){
    if(body.length-offset<2)return null;
    const rawTag=body[offset],length=body[offset+1],end=offset+2+length;
    if(length>=128 || end>body.length)return null;
    const payload=body.subarray(offset+2,end),record={rawTag,sourceSignedTag:rawTag<128?rawTag:rawTag-256,length,payloadHex:hex(payload)};
    if(rawTag===2){
      if(length<7)return null;
      const data=view(payload),rawControlType=payload[0];
      record.speedControl={rawControlType,sourceControlType:controlTypes.get(rawControlType)??'Other',sourceControlTypeKnown:controlTypes.has(rawControlType),sourcePitchSpeed:data.getInt16(1,true),sourceRollSpeed:data.getInt16(3,true),sourceYawSpeed:data.getInt16(5,true),trailingHex:hex(payload.subarray(7))};
    }
    records.push(record);offset=end;
  }
  return {kind:'externalDevice',profile:APP_PROFILE,commandId:105,timestamp:Date.now(),bodyHex:hex(body),records,deviceVerified:false,modelLayoutVerified:false,unitVerified:false,referenceFrameVerified:false,physicalCompletionVerified:false};
}
