"""Explicit source-version CENTER/id7 GET; no activation writes or source cache fallback."""
import copy
from .errors import RS4MiniError
VERSIONS={'Ver1_0':1,'Ver1_1':17,'Ver1_3':17,'Ver13':1}

def center_info_spec(source_version):
    if type(source_version) is not str or source_version not in VERSIONS:
        raise ValueError('Explicit sourceVersion Ver1_0, Ver1_1, Ver1_3 or Ver13 required')
    return dict(sourceVersion=source_version,payload=bytes([VERSIONS[source_version]]))

def center_info_reply(message,source_version):
    center_info_spec(source_version)
    flags=message.get('flags') if isinstance(message,dict) else None
    p=message.get('payload') if isinstance(message,dict) else None
    if (not isinstance(message,dict) or message.get('sender')!=229 or message.get('receiver')!=2 or message.get('commandSet')!=0 or message.get('commandId')!=50 or type(flags) is not int or not 0<=flags<=255 or not flags&128 or flags&7 or not isinstance(p,(bytes,bytearray)) or not p):
        raise RS4MiniError('RS4MINI_PROTOCOL_ERROR','Expected unencrypted CENTER/id7 activation-info ACK')
    if p[0]:raise RS4MiniError('RS4MINI_DEVICE_ERROR','Device rejected CENTER GET',statusCode=p[0],response=copy.deepcopy(message))
    body=bytes(p[1:]);old=source_version=='Ver1_0'
    if len(body)<(18 if old else 9):raise RS4MiniError('RS4MINI_PROTOCOL_ERROR','Incomplete CENTER GET business body')
    offset,length=(8,10) if old else (9,body[8])
    if length>16 or len(body)<offset+length:raise RS4MiniError('RS4MINI_PROTOCOL_ERROR','Invalid or incomplete declared CENTER serial number')
    sn=body[offset:offset+length]
    text=''.join(chr(v) if 48<=v<=57 or 65<=v<=90 or 97<=v<=122 else str(v if v<128 else v-256) for v in sn)
    return dict(profile='ronin-2.2.2',statusCode=0,acknowledged=True,sourceVersion=source_version,receiverByte=229,sourceGetRequestByte=VERSIONS[source_version],bodyHex=body.hex(),message=copy.deepcopy(message),activeByte=body[0],sourceActiveBit=bool(body[0]&1),unknownActiveBits=body[0]&254,dateRaw=dict(year=int.from_bytes(body[1:3],'little'),month=body[3],day=body[4],hour=body[5],minute=body[6],second=body[7]),serialNumberRawHex=sn.hex(),sourceSerialNumber=text,serialNumberLength=length,trailingBodyHex=body[offset+length:].hex(),dateValidityVerified=False,actualSessionVersionVerified=False,activationValidityVerified=False,modelLayoutVerified=False,deviceVerified=False,physicalCompletionVerified=False)
