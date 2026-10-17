"""Source axis mode byte; no inferred PF/PTF or motor-bit alias."""
from .app_protocol import parameter_reply
MODES={'ThreeAxis':0,'TwoAxis':8,'Roll360':16,'ThreeDRoll360':24}
NAMES=('ThreeAxis','TwoAxis','Roll360','ThreeDRoll360')
def axis_mode_write(source_mode):
    if type(source_mode) is not str or source_mode not in MODES:raise ValueError('Explicit source axis mode required')
    return dict(payload=bytes((34,1,MODES[source_mode])),requestedSourceMode=source_mode,requestedRawValue=MODES[source_mode])
def axis_mode_reply(message):
    result=parameter_reply(message,[dict(index=34,size=1)]);raw=int(result['parameters'][0]['rawHex'],16);mode=(raw>>3)&3
    return dict(result,rawValue=raw,sourceModeValue=mode,sourceMode=NAMES[mode],unknownBits=raw&231,modelLayoutVerified=False,activePresetVerified=False)
