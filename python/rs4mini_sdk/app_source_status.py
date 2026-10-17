"""Source candidates only; no target alarms, completion or control decisions."""
import time
from .app_protocol import APP_PROFILE
FIELDS=(('getFanDirection', 2, 1, 1, False), ('getGimbalDirectionWhenVertical', 2, 5, 1, False), ('getGimbalGravity', 3, 1, 3, False), ('getSleepMode', 4, 0, 1, False), ('getVerticalDirection', 2, 2, 1, False), ('isErrorRecentOrSelfie', 1, 6, 1, True), ('isErrorRecentWhenStartUp', 1, 3, 1, True), ('isInFlashlight', 2, 3, 1, True), ('isJointLockAfterStartup', 1, 0, 1, True), ('isJointLockWhenStartup', 1, 1, 1, True), ('isMotorProtected', 1, 2, 1, True), ('isPanoReady', 1, 7, 1, True), ('isPhoneOutGimbal', 3, 0, 1, True), ('isPitchLimitedInTracking', 3, 6, 1, True), ('isPitchLocked', 0, 1, 1, True), ('isPortrait', 2, 4, 1, True), ('isRollLocked', 0, 0, 1, True), ('isUpgrading', 1, 4, 1, True), ('isYawLimit', 1, 5, 1, True), ('isYawLimitedInTracking', 3, 5, 1, True), ('isYawLocked', 0, 2, 1, True))

def source_status_notification(message):
    flags=message.get('flags');command=message.get('commandId')
    if (message.get('sender')!=4 or message.get('receiver')!=2 or message.get('commandSet')!=4 or command not in (39,51) or type(flags) is not int or not 0<=flags<=255 or flags&0x87):return None
    body=message.get('payload');abnormal=command==39
    if not isinstance(body,(bytes,bytearray)) or len(body)<(5 if abnormal else 1):return None
    common=dict(profile=APP_PROFILE,timestamp=time.time()*1000,bodyHex=body.hex(),deviceVerified=False,modelLayoutVerified=False,physicalCompletionVerified=False)
    if not abnormal:return dict(common,kind='battery',rawCapacityValue=body[0],sourceGetter='getCapacityPercentage')
    values={name:bool((body[offset]>>shift)&mask) if boolean else (body[offset]>>shift)&mask for name,offset,shift,mask,boolean in FIELDS}
    values['isGimbalLocked']=values['isRollLocked'] or values['isPitchLocked']
    return dict(common,kind='abnormal',sourceValues=values)
