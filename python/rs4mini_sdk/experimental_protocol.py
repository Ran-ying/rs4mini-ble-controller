"""Other-model research profiles. RS 4 Mini support is not hardware verified."""
import math
import struct
import time
from .protocol import frame


def research_profile(profile):
    if profile not in ('rs3', 'rs3mini'):
        raise ValueError('Select an explicit rs3 or rs3mini research profile')
    return profile


def _tenths(value, name, limit):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > limit:
        raise ValueError(name + ' outside finite research command range')
    return math.floor(value * 10 + .5)


def rs3_absolute_frame(sequence, *, pan=None, roll=None, tilt=None, parameterByte):
    if type(parameterByte) is not int or not 0 <= parameterByte <= 255:
        raise ValueError('parameterByte must be a byte')
    payload, flags, supplied = bytearray(8), 1, False
    for axis, value, offset, invalid in [('pan', pan, 0, 2), ('roll', roll, 2, 4), ('tilt', tilt, 4, 8)]:
        if value is None:
            flags |= invalid
        else:
            struct.pack_into('<h', payload, offset, _tenths(value, axis, 180))
            supplied = True
    if not supplied:
        raise ValueError('at least one absolute angle is required')
    payload[6:8] = bytes([flags, parameterByte])
    return frame(sequence, 4, 0x14, payload, flags=0x40)


def rs3_rate_frame(sequence, *, pan=0, roll=0, tilt=0, release=False):
    if not isinstance(release, bool):
        raise ValueError('release must be boolean')
    payload = struct.pack('<hhhB', _tenths(pan, 'pan', 360), _tenths(roll, 'roll', 360),
                          _tenths(tilt, 'tilt', 360), 0 if release else 0x80)
    return frame(sequence, 4, 0x0c, payload, flags=0x40)


def research_sleep_frame(sequence, profile, asleep):
    research_profile(profile)
    if not isinstance(asleep, bool):
        raise ValueError('asleep must be boolean')
    return frame(sequence, 4, 0x0f, bytes([0x23, 1, (0x10 if profile == 'rs3mini' else 0) | int(asleep)]), flags=0x40)


def decode_research_status(message, profile):
    research_profile(profile)
    if not message or message['receiver'] != 2 or type(message.get('flags')) is not int or not 0<=message['flags']<=255 or message['flags']&7:
        return None
    payload = message['payload']
    base = dict(profile=profile, deviceVerified=False, timestamp=message.get('receivedAt', time.time() * 1000), payloadHex=payload.hex())
    if message['sender'] == 4 and message['commandSet'] == 4:
        if message.get('flags', 0) & 0x80 and message['commandId'] == 0x10 and payload:
            parameters, offset = [], 1
            while offset < len(payload):
                index = payload[offset]
                offset += 1
                if index >= 0x80:
                    parameters.append(dict(errorCode=index - 256))
                    continue
                if offset >= len(payload):
                    return None
                size = payload[offset]
                offset += 1
                if size not in (1, 2, 4, 8) or offset + size > len(payload):
                    return None
                parameters.append(dict(index=index, size=size, rawHex=payload[offset:offset + size].hex()))
                offset += size
            return dict(base, kind='user-parameters', layoutSource='legacy-duml', statusCode=payload[0], parameters=parameters)
        if message.get('flags', 0) & 0x80 and message['commandId'] == 0x0f and len(payload) == 1:
            return dict(base, kind='user-parameter-ack', layoutSource='legacy-duml', statusCode=payload[0])
        if message['commandId'] == 0x27 and len(payload) == 5 and payload[:4] == b'\0' * 4 and payload[4] <= 1:
            return dict(base, kind='sleep', asleep=bool(payload[4]))
        values = (0x10, 0x11) if profile == 'rs3mini' else (0, 1)
        if message['commandId'] == 0x0f and len(payload) == 4 and payload[:3] == bytes([0, 0x23, 1]) and payload[3] in values:
            return dict(base, kind='sleep', asleep=bool(payload[3] & 1))
        if message['commandId'] == 0x30 and len(payload) == 2 and payload[0] <= 100 and payload[1] <= 1:
            return dict(base, kind='calibration', percent=payload[0], inProgress=bool(payload[1]))
    if message['sender'] != 0xe5:
        return None
    if message['commandSet'] == 0x0d and message['commandId'] == 2 and len(payload) >= 17:
        fields = [struct.unpack_from('<i', payload, offset)[0] for offset in (1, 5, 9, 13)]
        percent = payload[20] if profile == 'rs3mini' and len(payload) == 21 and payload[20] <= 100 else None
        return dict(base, kind='battery-status', rawFields=fields, batteryPercent=percent)
    if message['commandSet'] == 4 and message['commandId'] == 0x66 and payload:
        fields, offset = [], 1
        while offset < len(payload):
            if offset + 2 > len(payload):
                return None
            tag, size = payload[offset:offset + 2]
            offset += 2
            if not size or offset + size > len(payload):
                return None
            fields.append(dict(tag=tag, size=size, rawHex=payload[offset:offset + size].hex()))
            offset += size
        return dict(base, kind='status-tlv', header=payload[0], fields=fields)
    return None
