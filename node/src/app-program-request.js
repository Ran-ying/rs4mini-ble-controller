// Explicit source status requests; no program execution or automatic subscription lifecycle.
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

export function programStatusSubscriptionSpec(program, enabled) {
  if (typeof enabled !== 'boolean') throw new TypeError('enabled must be a boolean');
  const {payload, ...requested} = programStatusRequestSpec(program);
  return {...requested, requestedEnabled: enabled, requestType: enabled ? 'StartContinuePush' : 'StopContinuePush',
    payload: bytes([0, enabled ? 0 : 1, 1, requested.requestedProgramCommandId])};
}
export function programStatusSubscriptionReply(message, program, enabled) {
  const {payload, ...requested} = programStatusSubscriptionSpec(program, enabled);
  return {...programStatusRequestReply(message, program), ...requested,
    notificationStreamVerified: false, remoteSubscriptionStateVerified: false};
}
