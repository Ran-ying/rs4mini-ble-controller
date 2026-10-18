"""Source-derived current-App codecs; no claim of hardware compatibility."""
import copy
from .errors import RS4MiniError

APP_PROFILE = 'ronin-2.2.2'


def app_profile(profile):
    if profile != APP_PROFILE:
        raise ValueError('Select explicit ronin-2.2.2 source profile')
    return profile


def parameter_context(parameters):
    if not isinstance(parameters, (list, tuple)) or not 1 <= len(parameters) <= 64:
        raise ValueError('parameters must contain 1..64 explicit index/size records')
    result = []
    for row in parameters:
        if not isinstance(row, dict) or set(row) != {'index', 'size'}:
            raise ValueError('parameter record requires index and size only')
        index, size = row['index'], row['size']
        if type(index) is not int or not 0 <= index <= 255 or type(size) is not int or size not in (1, 2, 4, 8):
            raise ValueError('index must be 0..255 and size 1/2/4/8')
        result.append(dict(index=index, size=size))
    return result


def parameter_request(parameters):
    return bytes(row['index'] for row in parameter_context(parameters))


def sensitivity_payload(mode):
    if type(mode) is not int or mode not in (0, 1):
        raise ValueError('follow sensitivity mode must be 0 or 1')
    return bytes((150, 1, mode))


def app_reply(message, command_id):
    if (not isinstance(message, dict) or message.get('sender') != 4 or message.get('receiver') != 2
            or message.get('commandSet') != 4 or message.get('commandId') != command_id
            or type(message.get('flags')) is not int or not 0<=message['flags']<=255 or not message['flags'] & 0x80 or message['flags']&7 or not isinstance(message.get('payload'),(bytes,bytearray)) or not message['payload']):
        raise RS4MiniError('RS4MINI_PROTOCOL_ERROR', 'Expected correlated unencrypted App response with status byte')
    status = message['payload'][0]
    if status:
        error = RS4MiniError('RS4MINI_DEVICE_ERROR', 'Device returned status ' + str(status))
        error.statusCode, error.response = status, copy.deepcopy(message)
        raise error
    return dict(profile=APP_PROFILE, deviceVerified=False, physicalCompletionVerified=False,
                statusCode=status, acknowledged=True, bodyHex=message['payload'][1:].hex(), message=copy.deepcopy(message))


def parameter_reply(message, parameters, command_id=0x10):
    context, result = parameter_context(parameters), app_reply(message, command_id)
    body, offset, records = message['payload'][1:], 0, []
    for row in context:
        index, size = row['index'], row['size']
        if offset + 2 + size > len(body) or body[offset] != index:
            raise RS4MiniError('RS4MINI_PROTOCOL_ERROR', 'Parameter response does not match request context')
        records.append(dict(index=index, size=size, headerByte=body[offset + 1], rawHex=body[offset + 2:offset + 2 + size].hex()))
        offset += 2 + size
    if offset != len(body):
        raise RS4MiniError('RS4MINI_PROTOCOL_ERROR', 'Unconsumed parameter response bytes')
    result['parameters'] = records
    return result


def factory_reset_spec(source_platform):
    if type(source_platform) is not str or source_platform!='HG724':raise ValueError('Explicit sourcePlatform HG724 required')
    return dict(payload=bytes((1,0,1)),requestedSourcePlatform='HG724')
