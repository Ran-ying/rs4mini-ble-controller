"""Source float32/truncation fine-tune codec, without hardware completion claims."""
import math,struct
AXES={'roll':0,'pitch':2}
def fine_tune_spec(axis,delta):
    if type(axis) is not str or axis not in AXES:raise ValueError('axis must be pitch or roll')
    if type(delta) not in (int,float) or not -2<=delta<=2 or not math.isfinite(delta):raise ValueError('adjustmentDegrees must be finite -2..2')
    value=struct.unpack('<f',struct.pack('<f',delta))[0]
    encoded=int(struct.unpack('<f',struct.pack('<f',value*10))[0])
    return dict(payload=bytes((encoded&255,AXES[axis])),axis=axis,requestedAdjustmentDegrees=delta,encodedTenths=encoded,nominalAdjustmentDegrees=encoded/10)
