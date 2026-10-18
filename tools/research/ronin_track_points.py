#!/usr/bin/env python3
"""Pinned offline track-point/ActualPose audit; no SDK imports, DUML or vendor execution."""
import argparse,hashlib,json,math,re,struct
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_subscription_trace import constructor_records
from ronin_track_workflow import direct_calls
UI='Lcom/dji/ronin/ui/create/'
TRACK=UI+'track/CreateTrackView;'
PATH=UI+'track/CreateTrackPathView;'
GIMBAL_PATH=UI+'CreateGimbalPathView;'
BASE=UI+'CreatePathBaseView;'
POINT=TRACK[:-1]+'$RoadPoint;'
MODEL='Ldji/midware/data/model/P3/DataGimbalSetPushPeripheralStatus;'
TYPE=MODEL[:-1]+'$DataType;'
PRODUCER='Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalRonin2Abstraction;'
SETTER='Ldji/midware/data/model/P3/DataGimbalSetTrackStatus;'
POSE_IDS={'PActualPose':34,'RActualPose':35,'YActualPose':36,'PMotorAngle':16,'RMotorAngle':17,'YMotorAngle':18}


def float32(value):
    return struct.unpack('<f',struct.pack('<f',value))[0]


def slider_seconds(value):
    """Only the source UI's finite 1..159 slider subset, not a firmware time range."""
    if type(value) not in (int,float):raise ValueError('finite UI progress 1..159 required')
    try:valid=math.isfinite(value) and 1<=value<=159
    except OverflowError:valid=False
    if not valid:raise ValueError('finite UI progress 1..159 required')
    progress=int(float32(value))
    return progress if progress<=60 else (progress-59)*60


def seconds_slider(value):
    if type(value) is not int or not 1<=value<=6000:raise ValueError('source UI seconds 1..6000 required')
    return value if value<=60 else value//60+59


def peripheral_records(body):
    """Independent complete-frame view; never copies source singleton stale/default-zero fields."""
    if not isinstance(body,(bytes,bytearray)) or not body:raise ValueError('source flag byte required')
    result=dict(rawFlag=body[0],sourceRecordBranchSelected=body[0]==1,records=[],bodyHex=body.hex())
    if body[0]!=1:return result
    names={v:k for k,v in POSE_IDS.items()};offset=1
    while offset<len(body):
        if len(body)-offset<2:raise ValueError('truncated source record header')
        tag,length=body[offset:offset+2];end=offset+2+length
        if length>=128 or end>len(body):raise ValueError('invalid source signed length or truncated body')
        payload=body[offset+2:end];name=names.get(tag)
        record=dict(rawTag=tag,sourceSignedTag=tag if tag<128 else tag-256,length=length,payloadHex=payload.hex(),sourceType=name,sourceInt32=None,sourceDividedFloat32=None)
        if name and length in (1,2,4,8):
            value=int.from_bytes(payload,'little',signed=True)
            value=((value+2**31)%2**32)-2**31
            record.update(sourceInt32=value,sourceDividedFloat32=float32(float32(value)/10))
        result['records'].append(record);offset=end
    return result


def track_argument_views(operations):
    """Read bounded straight-line argument windows, not loops, branches or vendor instructions."""
    result=[]
    for index,(op,text) in enumerate(operations):
        if not op.startswith('invoke-') or SETTER+'->addRoadPoint(F F F F F)' not in text:continue
        raw=text.split(', '+SETTER)[0];regs=re.findall(r'v\d+',raw)
        if ' ... ' in raw:regs=['v%d'%i for i in range(int(regs[0][1:]),int(regs[-1][1:])+1)]
        if len(regs)!=6:raise ValueError('expected receiver and five source arguments')
        origins={}
        for before,source in operations[max(0,index-12):index]:
            parts=source.split(', ');dest=parts[0]
            if before=='iget' and re.search(r'\$RoadPoint;->(?:moveTime|stopTime|yaw|pitch) F$',source):origins[dest]=source.split('->')[-1].split()[0]
            elif before.startswith('const') and before not in ('const-class','const-string','const-string/jumbo'):
                try:value=int(parts[1]);origins[dest]=value if value==0 else None
                except ValueError:origins[dest]=None
            elif before.startswith('move-object') or before=='move':origins[dest]=origins.get(parts[1])
            elif before.startswith(('move-result','new-','iget','sget','aget','add-','sub-','mul-','div-','int-to-','float-to-')):origins[dest]=None
        arguments=[origins.get(r) for r in regs[1:]]
        if any(value is None for value in arguments):raise ValueError('unresolved source track argument window')
        result.append(arguments)
    return result


def cache_pose_bindings(operations):
    """Exact local getter -> Float -> key -> notify register chain, no global call graph claim."""
    result=[];getters={'getPActualPose','getYActualPose','getRActualPose'}
    for index,(op,text) in enumerate(operations):
        match=re.search(re.escape(MODEL)+r'->(get\w+)\(\)F$',text)
        if not op.startswith('invoke-') or not match or match[1] not in getters:continue
        window=operations[index:index+8]
        if len(window)!=8:raise ValueError('incomplete source pose notification')
        (_,call),(op1,number),(op2,box),(op3,boxed),(op4,key),(op5,path),(op6,keyreg),(op7,notify)=window
        keyparts=key.split(', ',1);pathregs=path.split(', '+PRODUCER)[0].split(', ');notifyregs=notify.split(', '+PRODUCER)[0].split(', ')
        if not (op1=='move-result' and op2=='invoke-static' and box==number+', Ljava/lang/Float;->valueOf(F)Ljava/lang/Float;' and op3=='move-result-object' and op4.startswith('const-string') and len(keyparts)==2 and op5=='invoke-virtual' and '->convertKeyToPath(Ljava/lang/String;)' in path and len(pathregs)==2 and pathregs[1]==keyparts[0] and op6=='move-result-object' and op7=='invoke-virtual' and '->notifyValueChangeForKeyPath(Ljava/lang/Object; Ldji/sdksharedlib/keycatalog/DJISDKCacheKey;)V' in notify and notifyregs==[pathregs[0],boxed,keyreg]):raise ValueError('unresolved source pose register binding')
        if keyparts[1] in [r['key'] for r in result]:raise ValueError('duplicate source pose key')
        result.append(dict(getter=match[1],key=keyparts[1]))
    return result


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    images={}
    for bank in (3,5):
        raw=(bank_dir/('business-%02d-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=BANKS[bank]:raise ValueError('restored bank hash mismatch')
        images[bank]=raw
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes={bank:{c.get_name():c for c in DEX(raw).get_classes()} for bank,raw in images.items()};methods={}
    def take(bank,owner,name,descriptor=None):
        candidates=[m for m in classes[bank][owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(candidates)!=1 or not candidates[0].get_code():raise ValueError('missing or ambiguous readable point method '+name)
        m=candidates[0];methods[(bank,owner,name,m.get_descriptor())]=dict(bank=bank,className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return [(i.get_name(),i.get_output()) for i in m.get_instructions()]
    def require(ops,*tokens):
        for token in tokens:
            if not any(token in text for _,text in ops):raise ValueError('missing point source token '+token)
    for owner,names in ((TRACK,('onPointAdd','onPointFocusChange','sendToDeviceStop','formatTimeInSecond','formatValueInDegree','transferProgressToSecond','transferSecondToProgress','transferTime','updateTotalTime','onClick','<init>')),(PATH,('generatePoint','onAddPoint','onValueChange','getMaxPoints','setListener')),(GIMBAL_PATH,('onAttachedToWindow','onValueChange','updateYawPitch','updatePanAndTilt','updatePanAndTiltForFocus')),(BASE,('gridToAngleYaw','gridToAnglePitch','angleToGridYaw','angleToGridPitch','setCameraPosition'))):
        for name in names:take(3,owner,name)
    for number,name in ((7,'format'),(8,'onValueChange'),(9,'onValueChange')):take(3,TRACK[:-1]+'$%d;'%number,name,'(Ljava/lang/Float;)Ljava/lang/String;' if number==7 else None)
    take(3,POINT,'<init>','(F F F F)V')
    require(take(3,POINT,'<init>','(Lorg/json/JSONObject;)V'),'4663319084467748864','Ljava/lang/Math;->min(D D)D')
    take(3,UI+'newui/BaseRoadPoint;','<init>','(F F)V')
    progress=take(3,TRACK,'transferProgressToSecond');require(progress,'v0, 60','v2, v2, -59');
    if not any(op=='mul-int/2addr' for op,_ in progress):raise ValueError('source time multiplication changed')
    require(take(3,TRACK,'onClick'),'1126105088','1114636288','->setMinMax(F F)')
    require(take(3,TRACK,'formatValueInDegree'),'%d°')
    require(take(3,TRACK,'<init>'),'1073741824','->mLastMoveTime F','->mLastStopTime F')
    require(take(3,GIMBAL_PATH,'onValueChange'),'->updatePanAndTilt()V')
    require(take(3,GIMBAL_PATH,'updatePanAndTilt'),'->updateYawPitch()Z','->setCameraPosition(F F)V')
    require(take(3,BASE,'setCameraPosition'),'->angleToGridYaw(F)F','->angleToGridPitch(F)F','->mCameraCenterPointF Landroid/graphics/PointF;')
    require(take(3,GIMBAL_PATH,'onAttachedToWindow'),'PeripheralPosYaw','PeripheralPosPitch')
    require(take(3,PATH,'onAddPoint'),'->gridToAngleYaw(F)F','->gridToAnglePitch(F)F','PeripheralPosRoll','->onPointAdd(F F F)V')
    preview=take(3,TRACK,'previewToggle');send=take(3,TRACK,'sendToDeviceStart')
    preview_args=track_argument_views(preview);send_args=track_argument_views(send)
    if preview_args!=[['moveTime','stopTime','yaw','pitch',0]] or send_args!=[['moveTime','stopTime','yaw','pitch',0],[0,'stopTime','yaw','pitch',0],['moveTime','stopTime','yaw','pitch',0]]:raise ValueError('track point argument paths changed')
    require(send,'->clearPoint()V')
    enum=constructor_records(take(5,TYPE,'<clinit>'),TYPE);take(5,TYPE,'<init>')
    command_enum=constructor_records(take(5,'Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;','<clinit>'),'Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;')
    if command_enum['SetPushPeripheralStatus']['arguments'][2]!=102:raise ValueError('source peripheral base command changed')
    selected={name:dict(ordinal=enum[name]['arguments'][1],wireId=enum[name]['arguments'][2]) for name in POSE_IDS}
    if {name:r['wireId'] for name,r in selected.items()}!=POSE_IDS:raise ValueError('source pose enum ids changed')
    bindings=cache_pose_bindings(take(5,PRODUCER,'onEvent3BackgroundThread','('+MODEL+')V'))
    if bindings!=[dict(getter='getPActualPose',key='PeripheralPosPitch'),dict(getter='getYActualPose',key='PeripheralPosYaw'),dict(getter='getRActualPose',key='PeripheralPosRoll')]:raise ValueError('source pose cache bindings changed')
    for getter,name in [('getPActualPose','PActualPose'),('getYActualPose','YActualPose'),('getRActualPose','RActualPose'),('getPMotorAngle','PMotorAngle'),('getYMotorAngle','YMotorAngle'),('getRMotorAngle','RMotorAngle')]:
        ops=take(5,MODEL,getter);require(ops,'->'+name+' ','->getIntValue(','1092616192')
        if not any(op=='div-float/2addr' for op,_ in ops):raise ValueError('source pose scaling changed')
    for name in ('getIntValue','getData','setPushRecData'):take(5,MODEL,name)
    for name,desc in [('getSignedInt','(B)S'),('getShort','([B)S'),('getInt','([B)I'),('getLong','([B)J')]:take(5,'Ldji/midware/util/BytesUtil;',name,desc)
    require(take(5,MODEL,'getIntValue'),'Ljava/lang/Short;','Ljava/lang/Long;','->intValue()I')
    for name in ('getShort','getInt','getLong'):require(take(5,'Ldji/midware/util/BytesUtil;',name,{'getShort':'([B)S','getInt':'([B)I','getLong':'([B)J'}[name]),'ByteOrder;->LITTLE_ENDIAN ')
    preview_calls=direct_calls(preview)
    camera_calls=[c for c in preview_calls if 'Camera' in c['className'] or c['method'] in ('executeCameraAction','startVideoRecord','stopVideoRecord')]
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(b):BANKS[b] for b in (3,5)},appCodeExecuted=False,liveUiExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,sdkProgramSendAdded=False,
        scope='Selected source track UI times, point argument paths and ActualPose cache producer; no physical reference or complete firmware workflow proof',methods=list(methods.values()),
        time=dict(sourceUiUnit='seconds',sourceDisplaySuffixes=['s','min'],moveSliderRange=[1,159],stopSliderRange=[0,60],moveSecondsAtProgress=dict(p1=1,p60=60,p61=120,p159=6000),progressAbove60Rule='(truncFloat32(progress)-59)*60',inverseAbove60Rule='integerSeconds/60 truncation +59',inverseIsExact=False,sourceDefaultMoveAndStopSeconds=2,sourceUiRangeIsFirmwareSafeRange=False),
        point=dict(sourceUiAngleDisplay='degrees',cacheKeys=['PeripheralPosYaw','PeripheralPosPitch','PeripheralPosRoll'],previewArgumentViews=preview_args,sendToDeviceStartArgumentViews=send_args,initialSendLoopClearedBeforeFinalLoop=True,firstFinalSendMoveTime=0,sourceTrackRollValue=0,sourcePointAddIgnoresRollArgument=True,selectedJsonMoveTimeUpperClamp=6000,selectedJsonMoveTimeLowerClampPresent=False,selectedJsonStopTimeDirectFloatRead=True,existingJointAnglesEquivalentVerified=False,physicalReferenceFrameVerified=False),
        peripheral=dict(command='04:66',selectedTypes=selected,cacheProducer=bindings,sourceActualPoseDistinctFromMotorAngle=True,sourceGetterDivisor=10,sourceWidths=dict(byte=1,short=2,integer=4,longNarrowedToInt=8),missingSourceMapValueReturnsZero=True,sourceMapRetainsOtherRecords=True,sourceLengthUsesSignedByte=True,sourceUpdateFlag=1,offlineViewRetainsDuplicatesAndUnknowns=True,offlineViewInventsMissingZeros=False,rawBleOffsetsVerified=False),
        preview=dict(directCalls=preview_calls,cameraRelatedDirectCalls=camera_calls,completeCameraIsolationVerified=False,physicalStopVerified=False),
        remaining=['ActualPose physical reference, relation to existing 04:05 fields, target layout/firmware support and route remain unverified.','Source UI time/angle display and argument transforms do not prove motor timing, safe ranges or full camera isolation.','04:66 record widths are selected from record length; no target width is assumed. Other source widths remain opaque in offline view.','No program execution/stop, subscription changes, new SDK features or hardware operation added.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();result=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('%d point/pose fingerprints; no SDK or hardware operations.'%len(result['methods']))
if __name__=='__main__':main()
