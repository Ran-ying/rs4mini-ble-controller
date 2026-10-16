"""App system_calc calibration, distinct from motor auto-tune 6A/6E."""
def system_calibration_fields(raw_value):
    if type(raw_value) is not int or not 0 <= raw_value <= 255:
        raise ValueError('system calibration byte required')
    return dict(rawValue=raw_value,state=('DEFAULT','START','FAIL','SUCCESS')[raw_value] if raw_value<4 else None)


def system_calibration_reply(reply):
    return dict(reply,systemCalibration=system_calibration_fields(int(reply['parameters'][0]['rawHex'],16)))
