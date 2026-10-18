#!/usr/bin/env python3
"""Static 04:08/30 calibration audit and offline business views; no SDK/vendor execution."""
import argparse,hashlib,json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_subscription_trace import constructor_records
from ronin_external_device import source_enum
from ronin_status_trace import field_context
from ronin_program_receive import program_policy
AUTO='Ldji/midware/data/model/P3/DataGimbalAutoCalibration;'
PUSH='Ldji/midware/data/model/P3/DataGimbalGetPushSensorCalibrateStatus;'
UNBOUND='Ldji/midware/data/model/P3/DataGimbalGetPushAutoCalibrationStatus;'
SENSOR_STATUS=PUSH[:-1]+'$CalibrationStatus;'
PART=AUTO[:-1]+'$CalibrationPart;'
STATUS=AUTO[:-1]+'$CalibrationStatus;'
ENUM='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;'
BASE='Ldji/midware/data/manager/P3/DataBase;'
PARTS=('AUTO','JOINT_ANGLE','HALL_LINEAR','JOINT_ANGLE_CAMERA','JOINT_ANGLE_FIXTURE','GYRO','ACCELERATION','COMPASS','IMU_AND_SENSOR','SHOCK_PLATE')
STATES=('FAIL','SUCCESS','PROCESSING')


def source_start_body(part):
    if type(part) is not str or part not in PARTS:raise ValueError('explicit source part name required')
    return bytes((PARTS.index(part),))


def auto_calibration_response_body(body):
    if not isinstance(body,(bytes,bytearray)) or len(body)<2:raise ValueError('two-byte business response required, excluding outer return code')
    part,status=body[:2]
    return dict(rawPart=part,sourcePart=PARTS[part] if part<len(PARTS) else 'AUTO',sourcePartKnown=part<len(PARTS),rawStatus=status,sourceStatus=STATES[status] if status<len(STATES) else 'PROCESSING',sourceStatusKnown=status<len(STATES),bodyHex=bytes(body).hex(),trailingHex=bytes(body[2:]).hex(),targetDeviceVerified=False,physicalCompletionVerified=False)


def sensor_progress_body(body):
    if not isinstance(body,(bytes,bytearray)) or len(body)<2:raise ValueError('complete two-byte source push required')
    states={0:'COMPLETE',1:'PROCESSING',3:'FAIL',9:'OTHER'}
    return dict(rawProgressValue=body[0],rawStatus=body[1],sourceStatus=states.get(body[1],'OTHER'),sourceStatusKnown=body[1] in states,bodyHex=bytes(body).hex(),trailingHex=bytes(body[2:]).hex(),progressUnitVerified=False,targetDeviceVerified=False,physicalCompletionVerified=False)


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    images=[]
    for bank,pin in BANKS.items():
        raw=(bank_dir/('business-%02d-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('restored bank hash mismatch')
        images.append((bank,raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes=None;callers=[];typed=[];enum_refs=[]
    selected={AUTO,PUSH,PART,STATUS,SENSOR_STATUS,UNBOUND}
    for bank,raw in images:
        current={c.get_name():c for c in DEX(raw).get_classes()}
        if bank==5:classes=current
        for owner,c in current.items():
            if owner in selected:continue
            for m in c.get_methods():
                if any(t in m.get_descriptor() for t in selected):typed.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),hasCode=bool(m.get_code())))
                if not m.get_code():continue
                targets=[];fields=[]
                for op in m.get_instructions():
                    name,text=op.get_name(),op.get_output()
                    for target in (AUTO,PUSH,UNBOUND):
                        if name.startswith('invoke-') and target+'->' in text:targets.append(dict(owner=target,reference=text.split(target+'->',1)[1]))
                    for enum in (PART,STATUS,SENSOR_STATUS):
                        if name.startswith('sget') and enum+'->' in text:fields.append(dict(owner=enum,reference=text.split(enum+'->',1)[1]))
                if targets or fields:
                    row=dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
                    if targets:callers.append(dict(row,targets=targets))
                    if fields:enum_refs.append(dict(row,fields=fields))
    methods={}
    def take(owner,name,descriptor=None):
        ms=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(ms)!=1 or not ms[0].get_code():raise ValueError('missing or ambiguous calibration method '+name)
        m=ms[0];methods[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(ops,*tokens):
        for token in tokens:
            if not any(token in t for _,t in ops):raise ValueError('missing calibration source token '+token)
    for owner in selected:
        for m in classes[owner].get_methods():
            if m.get_code():take(owner,m.get_name(),m.get_descriptor())
    parts=source_enum(constructor_records(take(PART,'<clinit>'),PART));states=source_enum(constructor_records(take(STATUS,'<clinit>'),STATUS))
    if [(r['name'],r['sourceId']) for r in parts]!=[(n,i) for i,n in enumerate(PARTS)]:raise ValueError('part enum changed')
    if [(r['name'],r['sourceId']) for r in states]!=[(n,i) for i,n in enumerate(STATES)]:raise ValueError('status enum changed')
    require(take(AUTO,'<init>'),PART+'->AUTO ',AUTO+'->mCalType ')
    packed=take(AUTO,'doPack');require(packed,'v0, 1','->mCalType ',PART+'->value I','->_sendData [B')
    if [o for o,_ in packed]!=['const/4','new-array','iput-object','iget-object','iget-object','iget','int-to-byte','const/4','aput-byte','return-void']:raise ValueError('one-byte source packing changed')
    require(take(AUTO,'setCalType'),AUTO+'->mCalType ')
    part_get=take(AUTO,'getType');require(part_get,'v1, 0','v3, 1',AUTO+'->get(I I Ljava/lang/Class; [I)',PART+'->values()',PART+'->value I',PART+'->AUTO ')
    state_get=take(AUTO,'getStatus');require(state_get,'->_recData [B','v1, 1',AUTO+'->get(I I Ljava/lang/Class; [I)',STATUS+'->values()',STATUS+'->value I',STATUS+'->PROCESSING ')
    start=take(AUTO,'start','(Ldji/midware/interfaces/DJIDataCallBack;)V');require(start,'DeviceType;->APP ','DeviceType;->GIMBAL ','CMDTYPE;->REQUEST ','NEEDACK;->YES ','EncryptType;->NO ',ENUM+'->AutoCalibration ',AUTO+'->getSendData()[B','->data [B')
    sensor_states=source_enum(constructor_records(take(SENSOR_STATUS,'<clinit>'),SENSOR_STATUS))
    if {r['name']:r['sourceId'] for r in sensor_states}!={'COMPLETE':0,'PROCESSING':1,'FAIL':3,'OTHER':9}:raise ValueError('sensor status enum changed')
    progress=take(PUSH,'getProgress');require(progress,'->_recData [B','v1, 0','v2, 1',PUSH+'->get(I I Ljava/lang/Class; [I)')
    sensor_state_get=take(PUSH,'getStatus');require(sensor_state_get,'->_recData [B','v1, 1',PUSH+'->get(I I Ljava/lang/Class; [I)',SENSOR_STATUS+'->find(I)',SENSOR_STATUS+'->OTHER ')
    if take(PUSH,'start','(Ldji/midware/interfaces/DJIDataCallBack;)V')!=[('return-void','')]:raise ValueError('sensor start no longer inert')
    if any(m.get_name()=='isChanged' for m in classes[PUSH].get_methods()):raise ValueError('sensor push overrides change detection')
    if take(PUSH,'doPack')!=[('return-void','')]:raise ValueError('sensor push packing changed')
    require(take(SENSOR_STATUS,'find'),SENSOR_STATUS+'->OTHER ',SENSOR_STATUS+'->_equals(I)Z')
    fields=[dict(sourceGetter=n,**field_context(take(UNBOUND,n),UNBOUND,False)) for n in ('getProgress','getStatus')]
    if [(f['sourceGetter'],f['offset'],f['size'],f['mask']) for f in fields]!=[('getProgress',0,1,255),('getStatus',1,1,255)]:raise ValueError('unbound auto-status byte offsets changed')
    if take(UNBOUND,'isChanged')!=[('const/4','v1, 1'),('return','v1')]:raise ValueError('unbound auto-status isChanged changed')
    require(take(BASE,'get','(I I Ljava/lang/Class; [I)Ljava/lang/Number;'),'BytesUtil;->getInt([B)I')
    require(take('Ldji/midware/util/BytesUtil;','getInt','([B)I'),'ByteOrder;->LITTLE_ENDIAN ')
    require(take(BASE,'setPushRecPack'),'Pack;->data [B','->setPushRecData([B)V')
    require(take(BASE,'setPushRecData'),'->setRecData([B)V','->post()V')
    take(BASE,'setRecData')
    entries=constructor_records(take(ENUM,'<clinit>'),ENUM);policies=[program_policy(entries[n]) for n in ('AutoCalibration','GetPushSensorCalibrationStatus')]
    if [p['commandId'] for p in policies]!=[8,48] or policies[1]['modelClass']!=PUSH:raise ValueError('base calibration table changed')
    if take(ENUM,'isNeedCcode')!=[('const/4','v0, 1'),('return','v0')]:raise ValueError('base ccode rule changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(b):p for b,p in BANKS.items()},appCodeExecuted=False,liveUiExecuted=False,targetDeviceVerified=False,modelLayoutVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,sdkSendAdded=False,sdkReceiveAdded=False,methods=sorted(methods.values(),key=lambda m:(m['className'],m['method'],m['descriptor'])),directCallers=callers,typedMethodDeclarations=typed,externalEnumReferences=enum_refs,parts=parts,responseStates=states,sensorStates=sensor_states,basePolicies=policies,unboundAutoStatusFields=fields,
        sourceFacts=dict(requestCommand='04:08',requestBodyBytes=1,defaultPart='AUTO',ackRequested=True,receiverIdExplicitlyAssigned=any('->receiverId I' in t for _,t in start),requestResponseBusinessOffsets=dict(part=0,status=1),unknownPartFallback='AUTO',unknownResponseStatusFallback='PROCESSING',shortResponseStatusFallback='PROCESSING',baseAckCcodeStrippedBeforeBusinessView=True,pushCommand='04:30',pushModelClass=PUSH,pushBusinessOffsets=dict(progress=0,status=1),pushProgressShortFallback=0,pushStatusShortOrUnknownFallback='OTHER',pushStartIsInert=True,pushStatusUsesOwnEnum=True,pushStatusShares08EnumProven=False,pushInheritsChangeDetection=True,unboundAutoStatusModelClass=UNBOUND,unboundClassAssignedTo30InBaseTable=False,unboundProgressAcceptsSenderIdVarargs=True,unboundStatusUsesDefaultSenderContext=True,unboundAlwaysChanged=True,sourceBaseTableActualExtensionVerified=False,sourceProgressUnitVerified=False,horizontalCalibrationIdentityVerified=False,firmwareAbortVerified=False),
        scope=dict(restoredBanks=sorted(BANKS),unrestoredBanks=[1,7],reflectionNativeOrOtherClassLoadersRuledOut=False,cameraFeaturesImplemented=False),remaining=['Base command table and class names are not proof of an HG724 business entry or actual BLE routing.','04:08 request response, 04:30 raw push, system_calc/index36, balance_test/index37 and 6A/6E auto-tune remain separate.','Unknown/short source response falls back to PROCESSING, not proof that a device is calibrating.','04:30 has its own COMPLETE0/PROCESSING1/FAIL3/OTHER9 enum, not bool inProgress or the 04:08 response enum.','The similarly named GetPushAutoCalibrationStatus is a separate class not assigned to 04:30 in this base table.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d methods; %d direct callers; %d external enum-reference methods; no SDK/hardware execution'%(len(r['methods']),len(r['directCallers']),len(r['externalEnumReferences'])))
if __name__=='__main__':main()
