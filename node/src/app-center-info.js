// Explicit versioned CENTER/id7 GET; no activation writes, negotiation or cache fallback.
import {bytes,hex,view} from './bytes.js';
import {failure} from './async.js';
const versions=Object.freeze({Ver1_0:1,Ver1_1:17,Ver1_3:17,Ver13:1});
export function centerInfoSpec(sourceVersion){
 if(typeof sourceVersion!=='string'||!Object.hasOwn(versions,sourceVersion))throw new TypeError('Explicit sourceVersion Ver1_0, Ver1_1, Ver1_3 or Ver13 required');
 return {sourceVersion,payload:bytes([versions[sourceVersion]])};
}
export function centerInfoReply(message,sourceVersion){
 centerInfoSpec(sourceVersion);
 if(!message||message.sender!==229||message.receiver!==2||message.commandSet!==0||message.commandId!==50||!Number.isInteger(message.flags)||message.flags<0||message.flags>255||!(message.flags&128)||(message.flags&7)||!(message.payload instanceof Uint8Array)||!message.payload.length)throw failure('RS4MINI_PROTOCOL_ERROR','Expected unencrypted CENTER/id7 activation-info ACK');
 const copy={...message,raw:bytes(message.raw),payload:bytes(message.payload)},statusCode=message.payload[0];
 if(statusCode!==0)throw failure('RS4MINI_DEVICE_ERROR',`Device returned status ${statusCode}`,{statusCode,response:copy});
 const body=message.payload.subarray(1),old=sourceVersion==='Ver1_0';
 if(body.length<(old?18:9))throw failure('RS4MINI_PROTOCOL_ERROR','Incomplete CENTER GET business body');
 const offset=old?8:9,length=old?10:body[8];
 if(length>16||body.length<offset+length)throw failure('RS4MINI_PROTOCOL_ERROR','Invalid or incomplete declared CENTER serial number');
 const sn=body.subarray(offset,offset+length);
 const sourceSerialNumber=Array.from(sn,v=>(v>=48&&v<=57)||(v>=65&&v<=90)||(v>=97&&v<=122)?String.fromCharCode(v):String(v<128?v:v-256)).join('');
 return {profile:'ronin-2.2.2',statusCode,acknowledged:true,sourceVersion,receiverByte:229,sourceGetRequestByte:versions[sourceVersion],bodyHex:hex(body),message:copy,
  activeByte:body[0],sourceActiveBit:!!(body[0]&1),unknownActiveBits:body[0]&254,dateRaw:{year:view(body).getUint16(1,true),month:body[3],day:body[4],hour:body[5],minute:body[6],second:body[7]},
  serialNumberRawHex:hex(sn),sourceSerialNumber,serialNumberLength:length,trailingBodyHex:hex(body.subarray(offset+length)),
  dateValidityVerified:false,actualSessionVersionVerified:false,activationValidityVerified:false,modelLayoutVerified:false,deviceVerified:false,physicalCompletionVerified:false};
}
