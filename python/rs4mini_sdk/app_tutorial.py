"""Passive source tutorial view only; never sends steps or infers completion."""
import time
from .app_protocol import APP_PROFILE
STEPS=('STEP_FINISH','STEP_START','STEP_UNLOCK_GIMBAL','STEP_HOLD_GIMBAL_UPRIGHT','STEP_FOLLOW','STEP_STICK','STEP_LOCK_DIRECTION','STEP_RECENTER','STEP_SELFIE','STEP_PUSH','STEP_APP_CONTROL')
GETTERS=('getIsUnlock','getIsUpright','getIsFollowFinish','getIsStickFinish','getIsLockDirectionFinish','getIsRecentFinish','getIsSelfieFinish','getIsHandlePushFinish','getIsAppControlFinish')
def tutorial_notification(message):
    flags=message.get('flags');body=message.get('payload')
    if message.get('sender')!=4 or message.get('receiver')!=2 or message.get('commandSet')!=4 or message.get('commandId')!=43 or type(flags) is not int or not 0<=flags<=255 or flags&0x87 or not isinstance(body,(bytes,bytearray)) or len(body)<5:return None
    raw=body[0];word=int.from_bytes(body[1:5],'little')
    return dict(kind='tutorial',profile=APP_PROFILE,commandId=43,timestamp=time.time()*1000,rawStep=raw,knownSourceStepName=STEPS[raw] if raw<len(STEPS) else None,sourceFindResult=STEPS[raw] if raw<len(STEPS) else 'STEP_FINISH',rawCompletionWord=word,sourceSignedCompletionWord=word if word<2147483648 else word-4294967296,unknownCompletionBits=word&0xfffffe00,sourceFlags={name:(word>>bit)&1 for bit,name in enumerate(GETTERS)},sourceStepStatus={name:bool((word>>((value-2)&31))&1) for value,name in enumerate(STEPS)},bodyHex=body.hex(),trailingHex=body[5:].hex(),deviceVerified=False,modelLayoutVerified=False,requestAssociationVerified=False,physicalCompletionVerified=False)
