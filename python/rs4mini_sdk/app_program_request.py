"""Fixed single-status request; no subscription or program execution API."""
from .app_protocol import app_reply
from .errors import RS4MiniError
PROGRAMS={'track':0x62,'timelapse':0x37,'panorama':0x63}

def program_status_request_spec(program):
    if type(program) is not str or program not in PROGRAMS:raise ValueError('program must be track, timelapse or panorama')
    return dict(requestedProgram=program,requestedProgramCommandId=PROGRAMS[program],payload=bytes((0,2,1,PROGRAMS[program])))

def program_status_request_reply(message,program):
    requested=program_status_request_spec(program);requested.pop('payload')
    if not isinstance(message,dict) or type(message.get('flags')) is not int or not 0<=message['flags']<=255 or message['flags']&7:raise RS4MiniError('RS4MINI_PROTOCOL_ERROR','Unencrypted App response required')
    return dict(app_reply(message,0x6b),**requested,requestType='RequestSinglePush',freshStatusVerified=False,programCorrelationVerified=False,modelLayoutVerified=False)
