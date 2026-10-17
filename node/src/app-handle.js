import {bytes} from './bytes.js';
// Current App handle business body, distinct from table_choice and 04:24.
import {appReply} from './app-protocol.js';
import {failure} from './async.js';
const fields=[["getDualChannelEnable",0,false],["getTiltDirection",1,false],["getPanDirection",2,false],["getProfile",3,false],["getPitchFree",4,false],["getZoom2SpeedEnable",5,true],["getRotationFocusEnable",6,true],["getCellphoneSensorDisable",7,true]];
export function handleReply(message) {
  const reply=appReply(message,0x36),body=message.payload.subarray(1);
  if(body.length<8)throw failure('RS4MINI_PROTOCOL_ERROR','Handle body requires eight source bytes');
  return {...reply,modelLayoutVerified:false,values:fields.map(([sourceGetter,offset,bit])=>({sourceGetter,offset,size:1,rawValue:body[offset],sourceBit0:bit?Boolean(body[offset]&1):null}))};
}

const settings={"dualChannelMode":0,"tiltDirection":1,"panDirection":2};
export function handleWriteSpec({setting,value}) {
  if(typeof setting!=='string'||!Object.hasOwn(settings,setting))throw new TypeError('Unknown named handle setting');
  if(!Number.isInteger(value)||![0,1].includes(value))throw new RangeError('value must be integer 0 or 1');
  const payload=bytes(Array(8).fill(255));payload[settings[setting]]=value;
  return {payload,setting,requestedValue:value};
}
