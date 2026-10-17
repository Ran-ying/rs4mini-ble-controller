"""Named ordinary axis switches; raw values are not inferred presets."""
from .app_protocol import parameter_reply
AXES={'yaw':17,'pitch':18,'roll':19}
def smooth_track_selection(axis=None):
    if axis is not None and (type(axis) is not str or axis not in AXES):raise ValueError('axis must be yaw, pitch or roll')
    return [dict(axis=name,index=index,size=1) for name,index in AXES.items() if axis is None or axis==name]
def smooth_track_write(patch):
    if type(patch) is not dict or not patch or any(k not in AXES or type(v) is not bool for k,v in patch.items()):raise ValueError('One or more named boolean axes required')
    selected=[r for r in smooth_track_selection() if r['axis'] in patch];requested={r['axis']:patch[r['axis']] for r in selected}
    return dict(payload=bytes(v for r in selected for v in (r['index'],1,int(requested[r['axis']]))),requestedAxes=requested)
def smooth_track_reply(message,selection):
    result=parameter_reply(message,[dict(index=r['index'],size=1) for r in selection]);values=[]
    for row,record in zip(selection,result['parameters']):
        raw=int(record['rawHex'],16);valid=raw<=1
        values.append(dict(record,axis=row['axis'],rawValue=raw,withinSourceRange=valid,sourceEnabled=raw==1,enabled=(raw==1) if valid else None))
    return dict(result,values=values,modelLayoutVerified=False,activePresetVerified=False)
