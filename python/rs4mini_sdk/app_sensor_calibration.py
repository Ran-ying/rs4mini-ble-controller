"""Current-App source candidate; separate from 04:08 response and 6E auto-tune."""
import time
from .app_protocol import APP_PROFILE
STATES={0:'COMPLETE',1:'PROCESSING',3:'FAIL',9:'OTHER'}
def sensor_calibration_notification(message):
    flags=message.get('flags');body=message.get('payload')
    if (message.get('sender')!=4 or message.get('receiver')!=2 or message.get('commandSet')!=4 or message.get('commandId')!=48 or type(flags) is not int or not 0<=flags<=255 or flags&0x87 or not isinstance(body,(bytes,bytearray)) or len(body)<2):return None
    raw=body[1]
    return dict(kind='sensorCalibration',profile=APP_PROFILE,commandId=48,timestamp=time.time()*1000,rawProgressValue=body[0],rawStatus=raw,sourceStatus=STATES.get(raw,'OTHER'),sourceStatusKnown=raw in STATES,bodyHex=body.hex(),trailingHex=body[2:].hex(),deviceVerified=False,modelLayoutVerified=False,progressUnitVerified=False,requestAssociationVerified=False,physicalCompletionVerified=False)
