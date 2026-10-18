"""HG724 source AUTO action codec; no physical completion or abort guarantee."""
from .app_protocol import app_reply
PARTS=('AUTO','JOINT_ANGLE','HALL_LINEAR','JOINT_ANGLE_CAMERA','JOINT_ANGLE_FIXTURE','GYRO','ACCELERATION','COMPASS','IMU_AND_SENSOR','SHOCK_PLATE')
STATES=('FAIL','SUCCESS','PROCESSING')
def component_calibration_payload(source_part):
    if type(source_part) is not str or source_part!='AUTO':raise ValueError('Only explicit sourcePart AUTO has the selected HG724 action path')
    return bytes((0,))
def component_calibration_reply(message,motor_raw_value):
    ack=app_reply(message,8);body=message['payload'][1:];complete=len(body)>=2;calibration=None
    if complete:
        p,s=body[:2];calibration=dict(rawPart=p,sourcePart=PARTS[p] if p<len(PARTS) else 'AUTO',sourcePartKnown=p<len(PARTS),rawStatus=s,sourceStatus=STATES[s] if s<len(STATES) else 'PROCESSING',sourceStatusKnown=s<len(STATES),bodyHex=body.hex(),trailingHex=body[2:].hex())
    return dict(ack,requestedSourcePart='AUTO',motorPreflightRawValue=motor_raw_value,motorPreflightEnabled=not bool(motor_raw_value&1),businessComplete=complete,calibration=calibration,responsePartMatchesRequested=(body[0]==0) if complete else None,modelLayoutVerified=False,motorStatePhysicalVerified=False,businessRequestAssociationVerified=False,firmwareAbortVerified=False)
