#!/usr/bin/env python3
"""Static 04:69 source audit and bounded offline body views. No SDK or vendor execution."""
import argparse,hashlib,json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_subscription_trace import constructor_records
from ronin_program_receive import program_policy
MODEL='Ldji/midware/data/model/P3/DataGimbalGetPushExternalDeviceData;'
TYPE=MODEL[:-1]+'$DataType;'
SPEED=MODEL[:-1]+'$SpeedControlType;'
ENUM='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;'
BASE='Ldji/midware/data/manager/P3/DataBase;'

def source_enum(records):
    result=[]
    for name,r in records.items():
        args=r['arguments']
        if r['descriptor']!='(Ljava/lang/String; I I)V' or len(args)!=3 or args[0]!=name or any(type(v) is not int for v in args[1:]) or args[1]<0 or not 0<=args[2]<=255:raise ValueError('unsupported source enum constructor')
        result.append(dict(name=name,ordinal=args[1],sourceId=args[2]))
    return result


def external_body(body):
    """Complete per-frame view only: no singleton retention or malformed-source behavior."""
    if not isinstance(body,(bytes,bytearray)) or len(body)<2:raise ValueError('complete TLV business body required')
    records=[];offset=0
    while offset<len(body):
        if len(body)-offset<2:raise ValueError('truncated external header')
        tag,length=body[offset:offset+2];end=offset+2+length
        if length>=128 or end>len(body):raise ValueError('negative source length or truncated record')
        payload=body[offset+2:end];record=dict(rawTag=tag,sourceSignedTag=tag if tag<128 else tag-256,length=length,payloadHex=payload.hex())
        if tag==2:
            if length<7:raise ValueError('incomplete source SpeedControl record')
            record['speedControl']=dict(rawControlType=payload[0],sourceControlType={1:'CommonStick',2:'RockWheel',3:'Sensor',7:'Other'}.get(payload[0],'Other'),sourceControlTypeKnown=payload[0] in (1,2,3,7),sourcePitchSpeed=int.from_bytes(payload[1:3],'little',signed=True),sourceRollSpeed=int.from_bytes(payload[3:5],'little',signed=True),sourceYawSpeed=int.from_bytes(payload[5:7],'little',signed=True),trailingHex=payload[7:].hex())
        records.append(record);offset=end
    return dict(bodyHex=bytes(body).hex(),records=records,unitVerified=False,referenceFrameVerified=False,targetDeviceVerified=False)


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
    classes=None;callers=[];typed_handlers=[]
    for bank,raw in images:
        current={c.get_name():c for c in DEX(raw).get_classes()}
        if bank==5:classes=current
        for owner,c in current.items():
            if owner==MODEL or owner.startswith(MODEL[:-1]+'$'):continue
            for m in c.get_methods():
                if MODEL in m.get_descriptor():typed_handlers.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),hasCode=bool(m.get_code())))
                if not m.get_code():continue
                targets=[o.get_output().split(MODEL+'->',1)[1] for o in m.get_instructions() if o.get_name().startswith('invoke-') and MODEL+'->' in o.get_output()]
                if targets:callers.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest(),targets=targets))
    methods={}
    def take(owner,name,descriptor=None):
        ms=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(ms)!=1 or not ms[0].get_code():raise ValueError('missing or ambiguous external method '+name)
        m=ms[0];methods[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
        return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(ops,*tokens):
        for token in tokens:
            if not any(token in text for _,text in ops):raise ValueError('missing source token '+token)
    for owner in (MODEL,TYPE,SPEED,MODEL[:-1]+'$InstanceHolder;'):
        for m in classes[owner].get_methods():
            if m.get_code():take(owner,m.get_name(),m.get_descriptor())
    types=source_enum(constructor_records(take(TYPE,'<clinit>'),TYPE));speeds=source_enum(constructor_records(take(SPEED,'<clinit>'),SPEED))
    expected={'CameraFanPWM':0,'CameraLensDust':1,'SpeedControl':2,'BaseFloorHeight':3,'LocationCtrGimbal':4,'AttitudeCtrGimbal':5,'USBControl':6,'CameraLensSetups':7,'MouseValue':8,'ReceiveVersion':9,'CameraStatus':10,'Other':255}
    if {r['name']:r['sourceId'] for r in types}!=expected:raise ValueError('external type catalog changed')
    if {r['name']:r['sourceId'] for r in speeds}!={'CommonStick':1,'RockWheel':2,'Sensor':3,'Other':7}:raise ValueError('source speed enum changed')
    if take(MODEL,'doPack')!=[('return-void','')]:raise ValueError('source doPack no longer empty')
    if take(MODEL,'convertTwoSignInt')!=[('shl-int/lit8','v1, v1, 8'),('and-int/lit16','v0, v0, 255'),('or-int/2addr','v0, v1'),('return','v0')]:raise ValueError('source signed16 conversion changed')
    receive=take(MODEL,'setPushRecData');require(receive,BASE+'->setPushRecData([B)V',TYPE+'->SpeedControl ',MODEL+'->resetValue()V','v5, v2, 2','v4, v2, 3','v6, v2, 4','v4, v2, 5','v6, v2, 6','v4, v2, 7','v2, v2, 8','v2, v5, v3','v4, v4, 255')
    if receive[0][0]!='invoke-super':raise ValueError('source superclass receive ordering changed')
    if len([1 for op,text in receive if op=='aget-byte'])!=8:raise ValueError('source record signed byte reads changed')
    reset=take(MODEL,'resetValue');require(reset,'->mPitchSpeed I','->mRollSpeed I','->mYawSpeed I')
    if any('->mCtrType ' in t for _,t in reset):raise ValueError('source reset now clears type')
    for name,field in (('getPitchSpeed','mPitchSpeed'),('getRollSpeed','mRollSpeed'),('getYawSpeed','mYawSpeed')):
        if take(MODEL,name)!=[('iget','v0, v1, '+MODEL+'->'+field+' I'),('return','v0')]:raise ValueError('source speed getter changed')
    require(take(MODEL,'getSpeedControlType'),SPEED+'->find(I)')
    start=take(MODEL,'start','(Ldji/midware/interfaces/DJIDataCallBack;)V');require(start,'DeviceType;->APP ','DeviceType;->GIMBAL ','NEEDACK;->NO ','EncryptType;->NO ','CmdSet;->GIMBAL ',ENUM+'->GetPushExternalDeviceData ','v1, 2','v1, 1000')
    entries=constructor_records(take(ENUM,'<clinit>'),ENUM);policy=program_policy(entries['GetPushExternalDeviceData'])
    if policy['commandId']!=105 or policy['modelClass']!=MODEL:raise ValueError('external base table mapping changed')
    if take(ENUM,'isNeedCcode')!=[('const/4','v0, 1'),('return','v0')]:raise ValueError('base ccode policy changed')
    for name in ('setPushRecData','setPushRecPack','setRecData','post'):take(BASE,name)
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(b):p for b,p in BANKS.items()},appCodeExecuted=False,liveUiExecuted=False,targetDeviceVerified=False,modelLayoutVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,sdkSendAdded=False,sdkReceiveAdded=False,methods=list(methods.values()),directCallers=callers,typedMethodDeclarations=typed_handlers,sourceTypes=types,sourceSpeedControlTypes=speeds,basePolicy=policy,
        request=dict(commandSet=4,commandId=105,sender='APP',receiver='GIMBAL',ackRequested=False,encrypted=False,sourceRepeatTimes=2,sourceTimeoutMs=1000,receiverIdExplicitlyAssigned=any('->receiverId I' in t for _,t in start),doPackAssignsBody=False,emptyBodyInActualTransportVerified=False),
        receive=dict(recordOffset=0,header=['signedTag','signedLength'],speedControlTag=2,minimumSpeedControlPayloadLength=7,layout=['controlType:uint8','pitch:int16le','roll:int16le','yaw:int16le'],sourceUnitVerified=False,sourceReferenceFrameVerified=False,sourceCtrTypeMasked255=True,duplicateSpeedRecordLastWinsInSource=True,sourceRetainsPreviousFieldsWhenMissing=True,sourceNullOrLengthAtMostOneResetsOnlySpeeds=True,sourceResetClearsControlType=False,sourceSuperReceiveRunsBeforeFieldParsing=True,sourceBaseAckCcodePolicy=True,actualExtensionSelectionVerified=False),
        scope=dict(restoredBanks=sorted(BANKS),unrestoredBanks=[1,7],reflectionOrOtherClassLoadersRuledOut=False,cameraFeaturesImplemented=False,visionTrackingImplemented=False),remaining=['Direct invoke scan does not rule out reflection, native code, unrecovered banks or other class loaders.','Source fields are external-device raw values, not verified angular velocity or RS4Mini attitude/joint feedback.','Do not copy stale singleton fields or malformed signed-length loops into SDK snapshots.','Source start and base command mapping do not prove HG724 business entry, actual routing, request-body transport or target notifications.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d methods; %d external direct-caller methods; no SDK/hardware execution'%(len(r['methods']),len(r['directCallers'])))
if __name__=='__main__':main()
