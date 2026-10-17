"""Source candidate only; no target model, physical axis or center mapping."""
import time
from .app_protocol import APP_PROFILE

def handheld_stick_notification(message):
    flags=message.get('flags')
    if (message.get('sender')!=4 or message.get('receiver')!=2 or message.get('commandSet')!=4 or message.get('commandId')!=0x57 or type(flags) is not int or not 0<=flags<=255 or flags&0x87):return None
    body=message.get('payload')
    if not isinstance(body,(bytes,bytearray)) or len(body)<6:return None
    word=int.from_bytes(body[4:6],'little')
    return dict(kind='handheldStick',profile=APP_PROFILE,timestamp=time.time()*1000,sourceStickX=int.from_bytes(body[:2],'little',signed=True),sourceStickY=int.from_bytes(body[2:4],'little',signed=True),rawStateWord=word,unknownStateBits=word&65532,sourceTriggerPressed=bool(word&1),sourceStickControlEnabled=bool(word&2),bodyHex=body.hex(),deviceVerified=False,modelLayoutVerified=False,axisMappingVerified=False,physicalCompletionVerified=False)
