"""Offline hypotheses from the pinned MSDK 4.18 provided-JAR tails.

No transport, frames, parameter-name database, SDK imports or device calls.
These payloads are NOT verified RS 4 Mini commands. See MSDK_V4.md.
"""


def byte(value):
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError('expected an explicit integer byte')
    return value


def reset_mode_payload(mode, center_command):
    """Legacy tail's two bytes, not an axis-based RS 4 Mini recenter API.

    INVALID/None leaves byte 1 zero, rather than transmitting enum value 255.
    Names and numbers are source enums only; e.g. FE01 is target ALL-axis reset
    in historical tests although legacy enum 1 is named YAW_CENTER.
    """
    if byte(mode) not in (0, 1, 2, 254):
        raise ValueError('not a mode in the inspected legacy enum')
    if center_command is None:
        center_command = 255
    if byte(center_command) not in (1, 3, 4, 11, 12, 255):
        raise ValueError('not a center command in the inspected legacy enum')
    return bytes((mode, 0 if center_command == 255 else center_command))


def ronin_parameter_request(indexes):
    """Candidate 04:32 body: caller supplies raw indexes, never parameter names."""
    if not isinstance(indexes, (list, tuple)) or not indexes:
        raise ValueError('a nonempty explicit index list is required')
    return bytes(byte(index) for index in indexes)


def ronin_parameter_body(body, requested):
    """Decode candidate post-status body using caller-supplied index/size pairs.

    The SDK method uses metadata sizes, NOT the record's second byte. That byte
    remains raw. No status prefix is guessed/removed, no number type is inferred.
    Strict forensic matching rejects incomplete/reordered/extra records instead
    of copying the legacy decoder's silent skipping or partial state mutations.
    """
    if not isinstance(body, (bytes, bytearray)):
        raise ValueError('body must be raw bytes after explicit status separation')
    if not isinstance(requested, (list, tuple)) or not requested:
        raise ValueError('explicit request context is required')
    result, offset = [], 0
    for record in requested:
        if not isinstance(record, (tuple, list)) or len(record) != 2:
            raise ValueError('context entries must be index/size pairs')
        index, size = record
        byte(index)
        if type(size) is not int or size not in (1, 2, 4, 8):
            raise ValueError('offline decoder supports explicit widths 1/2/4/8 only')
        if offset + 2 + size > len(body) or body[offset] != index:
            raise ValueError('reply does not match request context')
        result.append(dict(index=index, headerByte=body[offset + 1], size=size,
                           rawHex=body[offset + 2:offset + 2 + size].hex()))
        offset += 2 + size
    if offset != len(body):
        raise ValueError('unconsumed bytes; do not guess a status prefix or layout')
    return result


def handle_parameter_body(body):
    """Candidate 04:36 post-status body; non-camera fields remain raw bytes."""
    if not isinstance(body, (bytes, bytearray)) or len(body) != 8:
        raise ValueError('expected exactly eight post-status bytes')
    names = ('dualChannelRaw', 'tiltDirectionRaw', 'panDirectionRaw', 'profileRaw', 'pitchFreeRaw')
    return dict(zip(names, body[:5]), uninterpretedTailHex=body[5:].hex())
