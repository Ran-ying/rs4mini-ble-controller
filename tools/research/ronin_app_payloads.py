"""Pure offline payloads from restored current-App code. No device transport.

These have source-level evidence, not RS 4 Mini hardware validation. This module
is never imported by SDK/UI; it cannot send, calibrate, or change a device.
"""


def reset_mode_payload(mode, reset):
    """Current App 04:4C: mode byte + boolean reset, NOT legacy axis enums."""
    if type(mode) is not int or mode not in (0, 1, 2, 254):
        raise ValueError('explicit current-App mode byte required')
    if type(reset) is not bool:
        raise ValueError('reset must be boolean; no axis selector exists here')
    return bytes((mode, int(reset)))


def follow_sensitivity_payload(mode):
    """HG724 setter 04:0F, cmd_follow_mode_sensitivity/index150, width1.

    App normalizes any non-1 input to 0; offline tool rejects other inputs
    explicitly instead of silently changing the intended mode.
    """
    if type(mode) is not int or mode not in (0, 1):
        raise ValueError('only source enum modes 0 and 1 are supported')
    return bytes((150, 1, mode))


def follow_sensitivity_request():
    """04:10 index request body from DataGimbalGetUserParams, not 04:32."""
    return bytes((150,))


def follow_sensitivity_body(body):
    """Strict post-status business body only. Never guesses/strips status bytes.

    Index150 is unsigned; it must not become a legacy negative error code.
    Unknown value bytes remain raw rather than mapping to a mode.
    """
    if not isinstance(body, (bytes, bytearray)) or len(body) != 3 or body[:2] != b'\x96\x01':
        raise ValueError('expected index150/width1/raw-value business body')
    value = body[2]
    return dict(index=150, size=1, rawValue=value, mode=value if value in (0, 1) else None)
