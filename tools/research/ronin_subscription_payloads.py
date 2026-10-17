"""Offline subscription-body and request-push checks; never encode/send DUML."""


MOVEMENT_PROFILE_NAMES={0:'CUSTOM_1',1:'CUSTOM_2',3:'FAST',4:'MEDIUM',5:'SLOW'}

def subscription_group_body(command,channels):
    """One group; empty selection means omitted group, not a remote stop."""
    if type(command) is not int or not 0<=command<=255:raise ValueError('byte-sized source command required')
    if not isinstance(channels,(list,tuple)) or any(type(c) is not int or not 0<=c<=255 for c in channels):raise ValueError('explicit channels 0..255 required')
    if not channels:return b''
    highest=max(channels);mask=bytearray(highest//8+1)
    for channel in channels:mask[channel//8]|=1<<(channel%8)
    return bytes((command,highest))+bytes(mask)


def request_push_preset(body,flags):
    """Source getPresetID offset for unencrypted request-type 04:24 only.

    Caller supplies the already selected payload, not a complete DUML packet.
    No status byte is stripped and no device/model support is inferred.
    """
    if type(flags) is not int or not 0<=flags<=255 or flags&0x87:raise ValueError('unencrypted request-type push required')
    if not isinstance(body,(bytes,bytearray)) or len(body)<3:raise ValueError('three push bytes required')
    raw=body[2]
    return dict(rawValue=raw,sourceEnum=MOVEMENT_PROFILE_NAMES.get(raw),deviceVerified=False,activePresetVerified=False)
