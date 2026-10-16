"""Ordinary named numeric parameters; no preset/input-source selection."""
from .app_protocol import parameter_reply
AXES=('pitch','roll','yaw')
GROUPS={'follow':(('speed',(3,12,2),2,1,100),('acceleration',(15,16,14),2,1,100),('deadZone',(5,13,4),2,0,100)),
        'rc':(('speed',(42,43,41),2,0,100),('deadZone',(27,40,26),1,0,100),('smoothing',(9,39,8),2,0,30))}


def tuning_selection(domain,axis=None,parameter=None):
    if domain not in GROUPS:raise ValueError('Unknown tuning domain')
    if axis is not None and axis not in AXES:raise ValueError('axis must be pitch, roll or yaw')
    if parameter is not None and parameter not in [row[0] for row in GROUPS[domain]]:raise ValueError('Unknown named tuning parameter')
    return [dict(axis=a,parameter=p,index=indices[i],size=size,min=minimum,max=maximum)
            for p,indices,size,minimum,maximum in GROUPS[domain] for i,a in enumerate(AXES)
            if (axis is None or a==axis) and (parameter is None or p==parameter)]


def tuning_write(domain,axis,parameter,value):
    if axis is None or parameter is None:raise ValueError('Tuning write requires axis and parameter')
    row=tuning_selection(domain,axis,parameter)[0]
    if type(value) is not int or not row['min']<=value<=row['max']:raise ValueError('value outside named source range')
    return bytes((row['index'],row['size']))+value.to_bytes(row['size'],'little')


def tuning_reply(message,selection):
    result=parameter_reply(message,[dict(index=row['index'],size=row['size']) for row in selection])
    values=[]
    for record,row in zip(result['parameters'],selection):
        raw=int.from_bytes(bytes.fromhex(record['rawHex']),'little')
        values.append(dict(record,axis=row['axis'],parameter=row['parameter'],rawValue=raw,withinSourceRange=row['min']<=raw<=row['max']))
    return dict(result,activePresetVerified=False,values=values)
