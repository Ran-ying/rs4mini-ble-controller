"""57 layout/axes unverified; 58 has a conditional HG724 source path only."""
import time
from .app_protocol import APP_PROFILE,app_reply

def handheld_stick_notification(message):
    flags=message.get('flags')
    if (message.get('sender')!=4 or message.get('receiver')!=2 or message.get('commandSet')!=4 or message.get('commandId')!=0x57 or type(flags) is not int or not 0<=flags<=255 or flags&0x87):return None
    body=message.get('payload')
    if not isinstance(body,(bytes,bytearray)) or len(body)<6:return None
    word=int.from_bytes(body[4:6],'little')
    return dict(kind='handheldStick',profile=APP_PROFILE,timestamp=time.time()*1000,sourceStickX=int.from_bytes(body[:2],'little',signed=True),sourceStickY=int.from_bytes(body[2:4],'little',signed=True),rawStateWord=word,unknownStateBits=word&65532,sourceTriggerPressed=bool(word&1),sourceStickControlEnabled=bool(word&2),bodyHex=body.hex(),deviceVerified=False,modelLayoutVerified=False,axisMappingVerified=False,physicalCompletionVerified=False)

def handheld_stick_control_payload(enabled):
    if type(enabled) is not bool:raise ValueError('enabled must be boolean')
    return bytes((int(enabled),))
def handheld_stick_control_reply(message,enabled):
    handheld_stick_control_payload(enabled)
    return dict(app_reply(message,0x58),sourceSetting='StickGimbalControlEnabled',requestedEnabled=enabled,modelLayoutVerified=False,readbackVerified=False,persistenceVerified=False,notificationAssociationVerified=False)
