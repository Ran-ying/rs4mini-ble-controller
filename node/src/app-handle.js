// Current App handle business body, distinct from table_choice and 04:24.
import {appReply} from './app-protocol.js';
import {failure} from './async.js';
const fields=[["getDualChannelEnable",0,false],["getTiltDirection",1,false],["getPanDirection",2,false],["getProfile",3,false],["getPitchFree",4,false],["getZoom2SpeedEnable",5,true],["getRotationFocusEnable",6,true],["getCellphoneSensorDisable",7,true]];
export function handleReply(message) {
  const reply=appReply(message,0x36),body=message.payload.subarray(1);
  if(body.length<8)throw failure('RS4MINI_PROTOCOL_ERROR','Handle body requires eight source bytes');
  return {...reply,modelLayoutVerified:false,values:fields.map(([sourceGetter,offset,bit])=>({sourceGetter,offset,size:1,rawValue:body[offset],sourceBit0:bit?Boolean(body[offset]&1):null}))};
}
