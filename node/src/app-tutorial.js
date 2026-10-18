// Passive source view only. No tutorial step sends or completion inference.
import {bytes,hex,view} from './bytes.js';
import {APP_PROFILE} from './app-protocol.js';
const steps=['STEP_FINISH','STEP_START','STEP_UNLOCK_GIMBAL','STEP_HOLD_GIMBAL_UPRIGHT','STEP_FOLLOW','STEP_STICK','STEP_LOCK_DIRECTION','STEP_RECENTER','STEP_SELFIE','STEP_PUSH','STEP_APP_CONTROL'];
const getters=['getIsUnlock','getIsUpright','getIsFollowFinish','getIsStickFinish','getIsLockDirectionFinish','getIsRecentFinish','getIsSelfieFinish','getIsHandlePushFinish','getIsAppControlFinish'];
export function tutorialNotification(message){
 if(!message||message.sender!==4||message.receiver!==2||message.commandSet!==4||message.commandId!==43||!Number.isInteger(message.flags)||message.flags<0||message.flags>255||(message.flags&0x87)||!(message.payload instanceof Uint8Array)||message.payload.length<5)return null;
 const body=bytes(message.payload),data=view(body),rawStep=body[0],word=data.getUint32(1,true);
 return {kind:'tutorial',profile:APP_PROFILE,commandId:43,timestamp:Date.now(),rawStep,knownSourceStepName:steps[rawStep]??null,sourceFindResult:steps[rawStep]??'STEP_FINISH',rawCompletionWord:word,sourceSignedCompletionWord:data.getInt32(1,true),unknownCompletionBits:(word&0xfffffe00)>>>0,sourceFlags:Object.fromEntries(getters.map((key,bit)=>[key,(word>>>bit)&1])),sourceStepStatus:Object.fromEntries(steps.map((key,value)=>[key,!!((word>>>((value-2)&31))&1)])),bodyHex:hex(body),trailingHex:hex(body.subarray(5)),deviceVerified:false,modelLayoutVerified:false,requestAssociationVerified:false,physicalCompletionVerified:false};
}
