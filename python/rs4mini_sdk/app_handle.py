"""Handle reply business fields; no inferred profile or firmware write semantics."""
from .app_protocol import app_reply
from .errors import RS4MiniError
FIELDS=(('getDualChannelEnable', 0, False), ('getTiltDirection', 1, False), ('getPanDirection', 2, False), ('getProfile', 3, False), ('getPitchFree', 4, False), ('getZoom2SpeedEnable', 5, True), ('getRotationFocusEnable', 6, True), ('getCellphoneSensorDisable', 7, True))
def handle_reply(message):
    reply=app_reply(message,0x36);body=message['payload'][1:]
    if len(body)<8:raise RS4MiniError('RS4MINI_PROTOCOL_ERROR','Handle body requires eight source bytes')
    return dict(reply,modelLayoutVerified=False,values=[dict(sourceGetter=name,offset=offset,size=1,rawValue=body[offset],sourceBit0=bool(body[offset]&1) if bit else None) for name,offset,bit in FIELDS])

SETTINGS={'dualChannelMode':0,'tiltDirection':1,'panDirection':2}
def handle_write_spec(setting,value):
    if type(setting) is not str or setting not in SETTINGS:raise ValueError('Unknown named handle setting')
    if type(value) is not int or value not in (0,1):raise ValueError('value must be integer 0 or 1')
    payload=bytearray([255]*8);payload[SETTINGS[setting]]=value
    return dict(payload=bytes(payload),setting=setting,requestedValue=value)
