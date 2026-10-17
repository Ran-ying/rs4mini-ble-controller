"""Explicit source-2 and named value in one App standalone request."""
from .app_protocol import parameter_reply
AXES=('pitch','roll','yaw')
GROUPS=(('speed',(80,79,81),0,100),('smoothing',(77,76,78),0,30))


def standalone_selection(axis=None,parameter=None):
    if axis is not None and axis not in AXES:raise ValueError('axis must be pitch, roll or yaw')
    if parameter is not None and parameter not in [row[0] for row in GROUPS]:raise ValueError('Unknown standalone parameter')
    return [dict(axis=a,parameter=p,index=indices[i],size=2,min=minimum,max=maximum)
            for p,indices,minimum,maximum in GROUPS for i,a in enumerate(AXES)
            if (axis is None or a==axis) and (parameter is None or p==parameter)]


def standalone_write(input_source,axis,parameter,value):
    if type(input_source) is not int or input_source!=2:raise ValueError('Explicit inputSource=2 required for this source path')
    if axis is None or parameter is None:raise ValueError('Standalone write requires axis and parameter')
    row=standalone_selection(axis,parameter)[0]
    if type(value) is not int or not row['min']<=value<=row['max']:raise ValueError('value outside named source range')
    return bytes((72,1,2,row['index'],2))+value.to_bytes(2,'little')


def standalone_context(selection):
    return [dict(index=72,size=1)]+[dict(index=row['index'],size=2) for row in selection]


def standalone_reply(message,selection):
    reply=parameter_reply(message,standalone_context(selection))
    values=[]
    for record,row in zip(reply['parameters'][1:],selection):
        raw=int.from_bytes(bytes.fromhex(record['rawHex']),'little')
        values.append(dict(record,axis=row['axis'],parameter=row['parameter'],rawValue=raw,withinSourceRange=row['min']<=raw<=row['max']))
    return dict(reply,inputSourceRaw=int(reply['parameters'][0]['rawHex'],16),activePresetVerified=False,values=values)
