"""Source-derived named bitfields; no PF/PTF or hardware-effect inference."""
from .errors import RS4MiniError

SCHEMAS = {
    'customFollow': dict(index=132, max=15, mask=15, fields=dict(enabled=1, pitch=2, roll=4, yaw=8)),
    'motor': dict(index=35, max=255, mask=113, fields=dict(enabled=1, forbidSelfie=16, forbidVertical=32, roll360=64)),
}


MODES=('custom','low','middle','high')
MODE_GROUPS={'follow':{'speed':('followSpeed',65),'acceleration':('followAcceleration',71),'deadZone':('followDeadZone',66)},
             'rc':{'speed':('rcSpeed',67),'deadZone':('rcDeadZone',68),'smoothing':('rcSmoothing',69)}}
for group in MODE_GROUPS.values():
    for kind,index in group.values():SCHEMAS[kind]=dict(index=index,max=255,mask=252,modes=True,fields=dict(pitch=2,roll=4,yaw=6))


def mode_kind(domain,parameter):
    if not isinstance(parameter,str) or parameter not in MODE_GROUPS[domain]:raise ValueError('Unknown named follow/RC parameter')
    return MODE_GROUPS[domain][parameter][0]


def settings_patch(kind, patch):
    schema = SCHEMAS[kind]
    if not isinstance(patch, dict) or not patch or any(key not in schema['fields'] or (value not in MODES if schema.get('modes') else type(value) is not bool) for key, value in patch.items()):
        raise ValueError('Settings require at least one valid named field')
    return patch.copy()


def decode_settings(result, kind):
    schema = SCHEMAS[kind]
    raw = int(result['parameters'][0]['rawHex'], 16)
    settings = {key: (MODES[(raw >> bit)&3] if schema.get('modes') else (not bool(raw & bit) if kind == 'motor' and key == 'enabled' else bool(raw & bit))) for key, bit in schema['fields'].items()}
    return dict(result, settings=settings, rawValue=raw, unknownBits=raw & (255 ^ schema['mask']))


def settings_write(kind, patch, raw):
    schema, patch = SCHEMAS[kind], settings_patch(kind, patch)
    if type(raw) is not int or not 0 <= raw <= schema['max']:
        raise RS4MiniError('RS4MINI_UNSUPPORTED_VALUE', 'Current settings exceed source setter range; no write sent')
    value = raw
    for key, enabled in patch.items():
        if schema.get('modes'):
            shift=schema['fields'][key]
            value=(value & (255 ^ (3 << shift))) | (MODES.index(enabled) << shift)
            continue
        bit = schema['fields'][key]
        set_bit = not enabled if kind == 'motor' and key == 'enabled' else enabled
        value = value | bit if set_bit else value & (255 ^ bit)
    return bytes((schema['index'], 1, value)), value
