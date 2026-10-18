"""HG702 calibration override/records, inherited by HG724; not hardware proof."""
import time
from .app_protocol import APP_PROFILE, app_reply
from .errors import RS4MiniError

STATES = {0: 'UnStart', 1: 'Processing', 2: 'Complete', 3: 'Failure', 255: 'UnKnown'}


def auto_tune_payload(start):
    if type(start) is not bool:
        raise ValueError('start must be boolean')
    return bytes((0, 1, int(start)))


def calibration_records(body):
    def invalid():
        return RS4MiniError('RS4MINI_PROTOCOL_ERROR', 'Malformed current-App calibration records')
    if body and body[0] not in (0, 1):
        raise invalid()
    offset, records, raw_state, raw_percent = 0, [], None, None
    while offset < len(body):
        if offset + 2 > len(body):
            raise invalid()
        tag, size = body[offset:offset+2]
        offset += 2
        if size > 127 or offset + size > len(body) or (tag == 0 and size < 2):
            raise invalid()
        value = body[offset:offset+size]
        records.append(dict(tag=tag, size=size, rawHex=value.hex()))
        if tag == 0:
            raw_state, raw_percent = value[0], value[1]
        offset += size
    return dict(records=records, rawState=raw_state, state=STATES.get(raw_state), rawPercent=raw_percent,
                percent=raw_percent if raw_percent is not None and raw_percent <= 100 else None, bodyHex=body.hex())


def calibration_reply(message):
    result = app_reply(message, 0x6e)
    result['calibration'] = calibration_records(message['payload'][1:])
    return result


def calibration_notification(message):
    if (message.get('sender') != 4 or message.get('receiver') != 2 or message.get('commandSet') != 4
            or message.get('commandId') != 0x6e or type(message.get('flags')) is not int or not 0<=message['flags']<=255 or message['flags'] & 0x87):
        return None
    try:
        result = calibration_records(message['payload'])
        if result['rawState'] is None:
            return None
        return dict(result, kind='calibration', profile=APP_PROFILE, deviceVerified=False,
                    physicalCompletionVerified=False, timestamp=time.time()*1000)
    except (RS4MiniError, KeyError):
        return None
