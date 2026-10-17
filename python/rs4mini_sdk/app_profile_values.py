"""Separate source profile0 and work-mode62, without inferred movement presets."""
from .app_protocol import parameter_reply
PARAMETERS={'userProfile':{'index':0,'size':1,'min':0,'max':5},'workMode':{'index':62,'size':1,'min':0,'max':128}}
WORK_MODES={'Free':0,'Flower':1,'Fpv':2,'Center':3}
def profile_value_selection(kind):
    if type(kind) is not str or kind not in PARAMETERS:raise ValueError('Unknown profile parameter')
    return dict(PARAMETERS[kind])
def profile_value_write(kind,value):
    row=profile_value_selection(kind)
    if kind=='userProfile':
        if type(value) is not int or not 0<=value<=5:raise ValueError('sourceProfileValue must be integer0..5')
        raw=value;metadata=dict(requestedSourceProfileValue=value)
    else:
        if type(value) is not str or value not in WORK_MODES:raise ValueError('Named source work mode required')
        raw=WORK_MODES[value];metadata=dict(requestedSourceMode=value)
    return dict(payload=bytes((row['index'],1,raw)),parameter=kind,requestedRawValue=raw,**metadata)
def profile_value_reply(message,kind):
    row=profile_value_selection(kind);result=parameter_reply(message,[dict(index=row['index'],size=1)]);raw=int(result['parameters'][0]['rawHex'],16)
    reading=dict(sourceUiName=('M1','M2','M3')[raw] if raw<3 else None) if kind=='userProfile' else dict(sourceMode=next((n for n,v in WORK_MODES.items() if v==raw),None))
    return dict(result,parameter=kind,rawValue=raw,withinSourceRange=raw<=row['max'],modelLayoutVerified=False,activePresetVerified=False,**reading)
