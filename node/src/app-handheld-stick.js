// Source candidate only: no target model, physical axis or center mapping.
import {bytes,hex,view} from './bytes.js';
import {APP_PROFILE} from './app-protocol.js';
export function handheldStickNotification(message) {
  if (!message || message.sender!==4 || message.receiver!==2 || message.commandSet!==4 || message.commandId!==0x57 || !Number.isInteger(message.flags) || message.flags<0 || message.flags>255 || (message.flags&0x87)) return null;
  if (!(message.payload instanceof Uint8Array) || message.payload.length<6) return null;
  const body=bytes(message.payload),data=view(body),word=data.getUint16(4,true);
  return {kind:'handheldStick',profile:APP_PROFILE,timestamp:Date.now(),sourceStickX:data.getInt16(0,true),sourceStickY:data.getInt16(2,true),rawStateWord:word,unknownStateBits:word&0xfffc,sourceTriggerPressed:!!(word&1),sourceStickControlEnabled:!!(word&2),bodyHex:hex(body),deviceVerified:false,modelLayoutVerified:false,axisMappingVerified:false,physicalCompletionVerified:false};
}
