"""Source fixed-layout push, without target model/firmware compatibility claims."""
import time
from .app_protocol import APP_PROFILE
FIELDS=(('getPitchAccel', 59, 2), ('getPitchDeadband', 21, 2), ('getPitchSmoothTrack', 70, 1), ('getPitchSpeed', 13, 2), ('getPresetID', 2, 1), ('getRollAccel', 63, 2), ('getRollDeadband', 51, 2), ('getRollSmoothTrack', 73, 1), ('getRollSpeed', 47, 2), ('getStickPitchSmooth', 37, 2), ('getStickPitchSpeed', 29, 2), ('getStickYawSmooth', 33, 2), ('getStickYawSpeed', 25, 2), ('getYawAccel', 55, 2), ('getYawDeadband', 17, 2), ('getYawSmoothTrack', 67, 1), ('getYawSpeed', 9, 2))
PRESETS={0:'CUSTOM_1',1:'CUSTOM_2',3:'FAST',4:'MEDIUM',5:'SLOW'}

def user_parameter_notification(message):
    flags=message.get('flags')
    if (message.get('sender')!=4 or message.get('receiver')!=2 or message.get('commandSet')!=4 or message.get('commandId')!=0x24 or type(flags) is not int or not 0<=flags<=255 or flags&0x87):return None
    body=message.get('payload')
    if not isinstance(body,(bytes,bytearray)) or len(body)<74:return None
    values=[dict(sourceGetter=name,offset=offset,size=size,rawValue=int.from_bytes(body[offset:offset+size],'little'),rawHex=body[offset:offset+size].hex()) for name,offset,size in FIELDS]
    raw=next(row['rawValue'] for row in values if row['sourceGetter']=='getPresetID')
    return dict(kind='userParameters',profile=APP_PROFILE,timestamp=time.time()*1000,values=values,preset=dict(rawValue=raw,sourceEnum=PRESETS.get(raw)),bodyHex=body.hex(),deviceVerified=False,modelLayoutVerified=False,activePresetVerified=False,physicalCompletionVerified=False)
