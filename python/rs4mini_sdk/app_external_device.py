"""Passive source candidate; raw speed names imply no unit, reference frame or control."""
import time
from .app_protocol import APP_PROFILE
CONTROL_TYPES={1:'CommonStick',2:'RockWheel',3:'Sensor',7:'Other'}
def external_device_notification(message):
    flags=message.get('flags');body=message.get('payload')
    if (message.get('sender')!=4 or message.get('receiver')!=2 or message.get('commandSet')!=4 or message.get('commandId')!=105 or type(flags) is not int or not 0<=flags<=255 or flags&0x87 or not isinstance(body,(bytes,bytearray)) or len(body)<2):return None
    records=[];offset=0
    while offset<len(body):
        if len(body)-offset<2:return None
        tag,length=body[offset:offset+2];end=offset+2+length
        if length>=128 or end>len(body):return None
        payload=body[offset+2:end];record=dict(rawTag=tag,sourceSignedTag=tag if tag<128 else tag-256,length=length,payloadHex=payload.hex())
        if tag==2:
            if length<7:return None
            raw=payload[0];record['speedControl']=dict(rawControlType=raw,sourceControlType=CONTROL_TYPES.get(raw,'Other'),sourceControlTypeKnown=raw in CONTROL_TYPES,sourcePitchSpeed=int.from_bytes(payload[1:3],'little',signed=True),sourceRollSpeed=int.from_bytes(payload[3:5],'little',signed=True),sourceYawSpeed=int.from_bytes(payload[5:7],'little',signed=True),trailingHex=payload[7:].hex())
        records.append(record);offset=end
    return dict(kind='externalDevice',profile=APP_PROFILE,commandId=105,timestamp=time.time()*1000,bodyHex=body.hex(),records=records,deviceVerified=False,modelLayoutVerified=False,unitVerified=False,referenceFrameVerified=False,physicalCompletionVerified=False)
