"""Named motor tuning in the current App's 04:31/32 command namespace."""
from .app_protocol import parameter_reply

AXES = ('pitch','roll','yaw')
GROUPS = (('stiffness',5),('strength',1),('gyroFiltering',0),('preControl',0))
CATALOG = tuple(dict(axis=axis,parameter=parameter,index=group*3+i,size=1,min=minimum,max=100)
                for group,(parameter,minimum) in enumerate(GROUPS) for i,axis in enumerate(AXES))


def motor_selection(axis=None, parameter=None):
    if axis is not None and axis not in AXES:
        raise ValueError('axis must be pitch, roll or yaw')
    if parameter is not None and parameter not in [group[0] for group in GROUPS]:
        raise ValueError('Unknown named motor parameter')
    return [row.copy() for row in CATALOG if (axis is None or row['axis']==axis) and (parameter is None or row['parameter']==parameter)]


def motor_write(axis,parameter,value):
    if axis is None or parameter is None:
        raise ValueError('Motor write requires axis and parameter')
    row=motor_selection(axis,parameter)[0]
    if type(value) is not int or not row['min']<=value<=row['max']:
        raise ValueError('value outside named source range')
    return bytes((row['index'],1,value))


def motor_reply(message,selection):
    result=parameter_reply(message,[dict(index=row['index'],size=1) for row in selection],0x32)
    values=[]
    for record,row in zip(result['parameters'],selection):
        raw=int(record['rawHex'],16)
        values.append(dict(record,axis=row['axis'],parameter=row['parameter'],rawValue=raw,withinSourceRange=row['min']<=raw<=row['max']))
    return dict(result,values=values)
