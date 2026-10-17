"""Offline source payload/body checks only: no DUML, SDK imports or transport."""
import math
import struct

HANDLE_FIELDS=(('getDualChannelEnable',0,False),('getTiltDirection',1,False),('getPanDirection',2,False),('getProfile',3,False),('getPitchFree',4,False),('getZoom2SpeedEnable',5,True),('getRotationFocusEnable',6,True),('getCellphoneSensorDisable',7,True))


def fine_tune_payload(axis,degrees):
    if axis not in ('roll','pitch'):raise ValueError('only source caller axes roll/pitch; no inferred yaw action')
    if type(degrees) not in (int,float) or not -2<=degrees<=2 or not math.isfinite(degrees):raise ValueError('finite source delta -2..2 required')
    value=struct.unpack('<f',struct.pack('<f',degrees))[0]
    scaled=struct.unpack('<f',struct.pack('<f',value*10))[0]
    return bytes((int(scaled)&255,0 if axis=='roll' else 2))


def handle_patch_payload(**fields):
    offsets={'dualChannelMode':0,'tiltDirection':1,'panDirection':2}
    if not fields or any(k not in offsets or type(v) is not int or v not in (0,1) for k,v in fields.items()):raise ValueError('named non-camera source fields with explicit 0/1 required')
    result=bytearray([255]*8)
    for name,value in fields.items():result[offsets[name]]=value
    return bytes(result)


def handle_reply_body(body):
    if not isinstance(body,(bytes,bytearray)) or len(body)<8:raise ValueError('explicit post-status handle business body of at least8bytes required')
    return dict(values=[dict(sourceGetter=name,offset=offset,rawValue=body[offset],sourceBit0=bool(body[offset]&1) if bit else None) for name,offset,bit in HANDLE_FIELDS],bodyHex=body.hex(),deviceVerified=False)


def hg724_reset_payload(platform):
    if platform!='HG724':raise ValueError('explicit source PlatformType.HG724 condition required')
    return bytes((1,0,1))
