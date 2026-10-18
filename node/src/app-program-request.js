// Fixed single-status request only; no subscription or program execution API.
import {bytes} from './bytes.js';
import {appReply} from './app-protocol.js';
import {failure} from './async.js';
const programs={track:0x62,timelapse:0x37,panorama:0x63};
export function programStatusRequestSpec(program) {
  if(typeof program!=='string' || !Object.hasOwn(programs,program))throw new TypeError('program must be track, timelapse or panorama');
  return {requestedProgram:program,requestedProgramCommandId:programs[program],payload:bytes([0,2,1,programs[program]])};
}
export function programStatusRequestReply(message,program) {
  const {payload,...requested}=programStatusRequestSpec(program);
  if(!message || !Number.isInteger(message.flags) || message.flags<0 || message.flags>255 || (message.flags&7))throw failure('RS4MINI_PROTOCOL_ERROR','Unencrypted App response required');
  return {...appReply(message,0x6b),...requested,requestType:'RequestSinglePush',freshStatusVerified:false,programCorrelationVerified:false,modelLayoutVerified:false};
}
