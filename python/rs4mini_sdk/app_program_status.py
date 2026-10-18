"""Passive source candidates; never subscribe, ACK or complete motion/queries."""
import time
from .app_protocol import APP_PROFILE

def _values(tag,p):
    if tag==0x62:return dict(status=p[0],finishedPoints=p[1],currentPercent=p[2],totalPercent=p[3])
    if tag==0x37:return dict(rawFlags=p[0],status=p[0]&7,recordingOrPreview=(p[0]>>3)&1,finishedPoints=p[1],currentRoadPercent=p[2],totalRoadPercent=p[3],unknownFlagBits=p[0]&0xf0)
    if tag==0x63:return dict(status=p[0],currentPictures=int.from_bytes(p[1:3],'little'),totalPictures=int.from_bytes(p[3:5],'little'))
    return None

def program_status_notification(message):
    flags=message.get('flags');command=message.get('commandId');body=message.get('payload')
    if (message.get('sender')!=4 or message.get('receiver')!=2 or message.get('commandSet')!=4 or command not in (0x38,0x64,0x6b) or type(flags) is not int or not 0<=flags<=255 or flags&0x87 or not isinstance(body,(bytes,bytearray))):return None
    if len(body)<(4 if command==0x38 else 5 if command==0x64 else 2):return None
    result=dict(kind='program',profile=APP_PROFILE,commandId=command,timestamp=time.time()*1000,bodyHex=body.hex(),format='standalone-timelapse' if command==0x38 else 'standalone-panorama' if command==0x64 else 'program-records',sourceValues=None,rawSuccessByte=None,sourceSuccess=None,records=[],deviceVerified=False,modelLayoutVerified=False,programCorrelationVerified=False,physicalCompletionVerified=False)
    if command==0x38:
        result['sourceValues']=dict(rawFlags=body[0],status=body[0]&3,takingOrPreview=(body[0]>>3)&1,finishedPoints=body[1],currentRoadPercent=body[2],totalRoadPercent=body[3],unknownFlagBits=body[0]&0xf4);return result
    if command==0x64:result['sourceValues']=_values(0x63,body);return result
    result['rawSuccessByte']=body[0];result['sourceSuccess']=body[0] in (0,1)
    if not result['sourceSuccess']:return result
    offset=1
    while offset<len(body):
        if len(body)-offset<2:return None
        tag,length=body[offset:offset+2];end=offset+2+length
        if length>=128 or end>len(body):return None
        minimum=4 if tag in (0x62,0x37) else 5 if tag==0x63 else 0
        if length<minimum:return None
        p=body[offset+2:end]
        result['records'].append(dict(rawTag=tag,sourceSignedTag=tag if tag<128 else tag-256,length=length,payloadHex=p.hex(),sourceValues=_values(tag,p)));offset=end
    return result
