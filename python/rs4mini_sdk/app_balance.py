"""Named balance_test register; source evidence, no firmware task ownership."""
def balance_fields(raw_value):
    if type(raw_value) is not int or not 0 <= raw_value <= 255:
        raise ValueError('balance byte required')
    state_code=raw_value >> 6
    axes={}
    for axis,shift in (('roll',4),('pitch',2),('yaw',0)):
        value=(raw_value >> shift) & 3
        axes[axis]=dict(rawValue=value,result=None if value==0 else ('PASS','MARGINAL','FAIL')[value-1])
    return dict(rawValue=raw_value,stateCode=state_code,state=('DEFAULT','TESTING','FINISH','ERROR')[state_code],axisResults=axes,
                axisFieldsValid=all(row['result'] is not None for row in axes.values()))


def balance_reply(reply):
    return dict(reply,balance=balance_fields(int(reply['parameters'][0]['rawHex'],16)))
