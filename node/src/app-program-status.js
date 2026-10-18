// Passive source candidates; never subscribe, ACK, or complete motion/queries.
import {bytes,hex} from './bytes.js';
import {APP_PROFILE} from './app-protocol.js';
function values(tag,p) {
  if(tag===0x62)return {status:p[0],finishedPoints:p[1],currentPercent:p[2],totalPercent:p[3]};
  if(tag===0x37)return {rawFlags:p[0],status:p[0]&7,recordingOrPreview:(p[0]>>3)&1,finishedPoints:p[1],currentRoadPercent:p[2],totalRoadPercent:p[3],unknownFlagBits:p[0]&0xf0};
  if(tag===0x63)return {status:p[0],currentPictures:p[1]|(p[2]<<8),totalPictures:p[3]|(p[4]<<8)};
  return null;
}
export function programStatusNotification(message) {
  if(!message || message.sender!==4 || message.receiver!==2 || message.commandSet!==4 || ![0x38,0x64,0x6b].includes(message.commandId) || !Number.isInteger(message.flags) || message.flags<0 || message.flags>255 || (message.flags&0x87) || !(message.payload instanceof Uint8Array))return null;
  const body=bytes(message.payload),commandId=message.commandId;
  if(body.length<(commandId===0x38?4:commandId===0x64?5:2))return null;
  const result={kind:'program',profile:APP_PROFILE,commandId,timestamp:Date.now(),bodyHex:hex(body),format:commandId===0x38?'standalone-timelapse':commandId===0x64?'standalone-panorama':'program-records',sourceValues:null,rawSuccessByte:null,sourceSuccess:null,records:[],deviceVerified:false,modelLayoutVerified:false,programCorrelationVerified:false,physicalCompletionVerified:false};
  if(commandId===0x38) {result.sourceValues={rawFlags:body[0],status:body[0]&3,takingOrPreview:(body[0]>>3)&1,finishedPoints:body[1],currentRoadPercent:body[2],totalRoadPercent:body[3],unknownFlagBits:body[0]&0xf4};return result;}
  if(commandId===0x64) {result.sourceValues=values(0x63,body);return result;}
  result.rawSuccessByte=body[0];result.sourceSuccess=body[0]===0 || body[0]===1;
  if(!result.sourceSuccess)return result;
  for(let offset=1;offset<body.length;) {
    if(body.length-offset<2)return null;
    const tag=body[offset],length=body[offset+1],end=offset+2+length;
    if(length>=128 || end>body.length)return null;
    const minimum=tag===0x62||tag===0x37?4:tag===0x63?5:0;
    if(length<minimum)return null;
    const p=body.subarray(offset+2,end);
    result.records.push({rawTag:tag,sourceSignedTag:tag<128?tag:tag-256,length,payloadHex:hex(p),sourceValues:values(tag,p)});
    offset=end;
  }
  return result;
}
