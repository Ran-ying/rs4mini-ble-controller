#!/usr/bin/env python3
"""Pinned source-program evidence and handwritten business-body checks; no DUML/SDK."""
import argparse,hashlib,json,math,struct
from pathlib import Path
from ronin_save_trace import BANKS
from ronin_static import APK_SHA256
from ronin_subscription_trace import constructor_records
MODEL='Ldji/midware/data/model/P3/'
TRACK=MODEL+'DataGimbalSetTrackStatus;'
DELAY=MODEL+'DataGimbalSetDelayTimelapseParams;'
RONIN=MODEL+'DataRonin2SetTimelapseParams;'
PANO=MODEL+'DataGimbalSetPanoramaParams;'
PANO_STATUS=MODEL+'DataGimbalGetPushPanoramaStatus;'
DELAY_STATUS=MODEL+'DataGimbalGetPushTimelapseStatus;'
EXTERNAL=MODEL+'DataGimbalGetPushExternalStatus;'
OWNERS=(TRACK,DELAY,RONIN,PANO,PANO_STATUS,DELAY_STATUS,EXTERNAL)
COMMANDS={'SetDelayTimelapseParams':37,'SetTimelapseParams':55,'GetPushTimelapseStatus':56,'SetTrack':98,'SetPanorama':99,'GetPushPanorama':100,'GetPushTrackAndTimelapse':107}


def integer(value,lo,hi):
    if type(value) is not int or not lo<=value<=hi:raise ValueError('bounded source integer required')
    return value


def rounded_tenths(value):
    """Finite float32 multiplication then Math.round(float), saturated Java int."""
    if type(value) not in (int,float):raise ValueError('finite source float required')
    try:finite=math.isfinite(value)
    except OverflowError:finite=False
    if not finite:raise ValueError('finite source float required')
    try:
        f=struct.unpack('<f',struct.pack('<f',value))[0]
        scaled=struct.unpack('<f',struct.pack('<f',f*10))[0]
    except (OverflowError,struct.error):raise ValueError('finite float32 multiplication required')
    if not math.isfinite(scaled):raise ValueError('finite float32 multiplication required')
    return max(-2147483648,min(2147483647,math.floor(scaled+0.5)))


def track_body(points,*,tripod,phase,record_or_preview):
    """Points are moveTime,stopTime,yaw,pitch,roll; not a motion API or safe range."""
    if type(tripod) is not bool:raise ValueError('explicit source boolean required')
    phase=integer(phase,0,1);preview=integer(record_or_preview,0,1)
    if not isinstance(points,(list,tuple)) or len(points)>10:raise ValueError('source queue holds at most ten points')
    header=(int(tripod)<<1)|(phase<<2)|(preview<<3)
    if phase==1:return bytes((header,))
    body=bytearray((header,len(points)))
    for row in points:
        if len(row)!=5:raise ValueError('five source point fields required')
        move,stop,yaw,pitch,roll=row
        body.extend(struct.pack('<HHHHH',*(rounded_tenths(v)&65535 for v in (move,stop,roll,pitch,yaw))))
    return bytes(body)


def delay_info_or(info,field,value):
    info=integer(info,0,255)
    shifts={'mode':0,'tripod':1,'phase':2,'preview':3,'externalDevice':7}
    if field not in shifts:raise ValueError('unknown source info field')
    if field=='externalDevice':
        if type(value) is not bool:raise ValueError('explicit source boolean required')
        bit=int(value)
    else:bit=integer(value,-2147483648,2147483647)&1
    return (info|(bit<<shifts[field]))&255


def delay_body(info,points):
    if not isinstance(points,(list,tuple)) or len(points)>6:raise ValueError('source addRoadPosition accepts six points')
    body=bytearray((integer(info,0,255),len(points)))
    for duration,roll,pitch,yaw in points:
        body.extend(struct.pack('<Ihhh',integer(duration,-2147483648,2147483647)&0xffffffff,*(integer(v,-32768,32767) for v in (roll,pitch,yaw))))
    return bytes(body)


def ronin_timelapse_body(info,points,duration):
    """Preserves source's offset2 duration overwrite; does not repair source logic."""
    info=integer(info,0,255);duration=integer(duration,-9223372036854775808,9223372036854775807)
    if not isinstance(points,(list,tuple)) or len(points)>5:raise ValueError('source queue holds at most five points')
    if info&1:return bytes((info,len(points)))
    if not points:raise ValueError('source duration copy exceeds two-byte empty-point allocation')
    body=bytearray((info,len(points)))
    for time,roll,pitch,yaw in points:
        body.extend(struct.pack('<IHHH',integer(time,-9223372036854775808,9223372036854775807)&0xffffffff,*(integer(v,-2147483648,2147483647)&65535 for v in (roll,pitch,yaw))))
    body[2:6]=struct.pack('<I',duration&0xffffffff)
    return bytes(body)


def panorama_body(left,top,right,bottom,horizontal,vertical,exposure,command):
    values=[integer(v,-2147483648,2147483647) for v in (left,top,right,bottom,horizontal,vertical,exposure,command)]
    left,top,right,bottom,horizontal,vertical,exposure,command=values
    return struct.pack('<HHBBBBBB',left&65535,right&65535,top&255,bottom&255,horizontal&255,vertical&255,exposure&255,command&255)


def external_request_body(request_type,command):
    request_type=integer(request_type,0,2)
    if type(command) is not int or command not in (55,98,99):raise ValueError('explicit audited source program tag required')
    return bytes((0,request_type,1,command))


def standalone_status(kind,body):
    if not isinstance(body,(bytes,bytearray)):raise ValueError('source business bytes required')
    if kind=='panorama':
        if len(body)<5:raise ValueError('complete five-byte panorama business body required')
        return dict(sourceStatus=body[0],currentPictures=int.from_bytes(body[1:3],'little'),totalPictures=int.from_bytes(body[3:5],'little'),bodyHex=body.hex())
    if kind=='timelapse':
        if len(body)<4:raise ValueError('complete four-byte timelapse business body required')
        return dict(rawFlags=body[0],sourceStatus=body[0]&3,sourceTakingOrPreview=(body[0]>>3)&1,finishedPoints=body[1],currentRoadPercent=body[2],totalRoadPercent=body[3],unknownFlagBits=body[0]&0xf4,bodyHex=body.hex())
    raise ValueError('explicit source status kind required')


def external_status_records(body):
    """Validated offline view, not the source's unchecked/state-retaining parser."""
    if not isinstance(body,(bytes,bytearray)) or len(body)<2:raise ValueError('complete source success and record header required')
    result=dict(rawSuccessByte=body[0],sourceSuccess=body[0] in (0,1),records=[],bodyHex=body.hex())
    if not result['sourceSuccess']:return result
    offset=1
    while offset<len(body):
        if len(body)-offset<2:raise ValueError('truncated program record header')
        tag,length=body[offset:offset+2]
        if length>=128:raise ValueError('source signed length is outside validated offline subset')
        end=offset+2+length
        if end>len(body):raise ValueError('truncated program record body')
        payload=body[offset+2:end];minimum={98:4,55:4,99:5}.get(tag)
        if minimum is not None and length<minimum:raise ValueError('known record does not contain complete source fields')
        row=dict(rawTag=tag,sourceSignedTag=tag if tag<128 else tag-256,length=length,payloadHex=payload.hex())
        if tag==98:row['sourceValues']=dict(status=payload[0],finishedPoints=payload[1],currentPercent=payload[2],totalPercent=payload[3])
        elif tag==55:row['sourceValues']=dict(rawFlags=payload[0],status=payload[0]&7,recordingOrPreview=(payload[0]>>3)&1,finishedPoints=payload[1],currentRoadPercent=payload[2],totalRoadPercent=payload[3])
        elif tag==99:row['sourceValues']=dict(status=payload[0],currentPictures=int.from_bytes(payload[1:3],'little'),totalPictures=int.from_bytes(payload[3:5],'little'))
        result['records'].append(row);offset=end
    return result


def trace(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    images=[]
    for bank,pin in BANKS.items():
        raw=(bank_dir/('business-%02d-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('restored bank hash mismatch: %02d'%bank)
        images.append((bank,raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    methods={};callers=[];selected={};bank_counts=[]
    def related(owner):return any(owner==o or owner.startswith(o[:-1]+'$') for o in OWNERS)
    for bank,raw in images:
        dex=DEX(raw);count=0
        for cls in dex.get_classes():
            owner=cls.get_name()
            for m in cls.get_methods():
                if not m.get_code():continue
                count+=1;ops=[(o.get_name(),o.get_output()) for o in m.get_instructions()]
                row=dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
                if related(owner) or (bank==5 and owner=='Ldji/midware/util/BytesUtil;' and m.get_name()=='getBytes' and m.get_descriptor() in ('(I)[B','(J)[B','(S)[B')) or (bank==5 and owner=='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;' and m.get_name()=='<clinit>'):
                    key=(owner,m.get_name(),m.get_descriptor())
                    if key in methods:raise ValueError('duplicate selected method across banks')
                    methods[key]=row;selected[key]=ops
                elif not related(owner):
                    refs=[dict(className=o,method=text.split('->',1)[1].split('(',1)[0]) for op,text in ops if op.startswith('invoke-') for o in OWNERS if o+'->' in text]
                    if refs:callers.append(dict(**row,references=refs))
        bank_counts.append(dict(bank=bank,methodsWithCode=count));print('bank%02d scanned'%bank,flush=True)
    def take(owner,name,descriptor=None):
        found=[ops for (o,n,d),ops in selected.items() if o==owner and n==name and (descriptor is None or d==descriptor)]
        if len(found)!=1:raise ValueError('missing or ambiguous program method '+name)
        return found[0]
    def require(ops,token):
        if not any(token in text for _,text in ops):raise ValueError('missing program source token '+token)
    command='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;';records=constructor_records(take(command,'<clinit>'),command)
    bindings={name:records[name]['arguments'] for name in COMMANDS}
    if any(bindings[name][2]!=number for name,number in COMMANDS.items()):raise ValueError('program command numbers changed')
    for owner,name in ((TRACK,'SetTrack'),(DELAY,'SetDelayTimelapseParams'),(RONIN,'SetTimelapseParams'),(PANO,'SetPanorama'),(EXTERNAL,'GetPushTrackAndTimelapse')):
        require(take(owner,'start'),'CmdIdGimbal$CmdIdType;->'+name+' ');require(take(owner,'start'),'DataConfig$NEEDACK;->YES ')
    for owner in (PANO_STATUS,DELAY_STATUS):
        require(take(owner,'isChanged'),'->start()V');require(take(owner,'start'),'DataConfig$CMDTYPE;->ACK ');require(take(owner,'start'),'DataConfig$NEEDACK;->NO ')
    require(take(TRACK,'doPack'),'Ljava/lang/Math;->round(F)I');require(take(TRACK,'doPack'),'->clearPoint()V')
    require(take(TRACK,'addRoadPoint'),'v1, 10');require(take(DELAY,'addRoadPosition'),'v1, 5');require(take(RONIN,'addRoadPosition'),'v1, 5')
    require(take(RONIN,'doPack'),'->mDuration J');require(take(EXTERNAL,'setPushRecData'),'CmdIdGimbal$CmdIdType;->SetTrack ')
    for signature in ('(I)[B','(J)[B','(S)[B'):
        ops=take('Ldji/midware/util/BytesUtil;','getBytes',signature)
        require(ops,'255');require(ops,'8')
        if not any(op=='aput-byte' for op,_ in ops):raise ValueError('source little-endian byte array writes changed')
    time_enum=DELAY_STATUS[:-1]+'$TimeLaps;'
    time_states=constructor_records(take(time_enum,'<clinit>'),time_enum)
    if {n:r['arguments'][2] for n,r in time_states.items()}!={'NONE':0,'PREPARE':1,'PROGRESS':2,'END':3,'ERROR':4}:raise ValueError('source timelapse enums changed')
    require(take(time_enum,'find'),'->NONE ')
    enum=EXTERNAL[:-1]+'$RequestType;';types=constructor_records(take(enum,'<clinit>'),enum)
    request_types={name:row['arguments'][2] for name,row in types.items()}
    if request_types!={'StartContinuePush':0,'StopContinuePush':1,'RequestSinglePush':2}:raise ValueError('source request types changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(k):v for k,v in BANKS.items()},appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,targetModelCallPathEstablished=False,rawBleOffsetsVerified=False,
        scope='Seven generic source classes and nested classes plus direct invoke references in six restored banks; business bodies only',commandEnumArguments=bindings,banks=bank_counts,methods=list(methods.values()),externalDirectCallers=callers,
        track=dict(command='04:62',pointLimit=10,addRoadPointArgumentOrder=['moveTime','stopTime','yaw','pitch','roll'],wirePointOrder=['moveTime','stopTime','roll','pitch','yaw'],pointBytes=10,headerBytes=2,startPhase=0,stopPhase=1,stopBodyBytes=1,scale=10,sourceRounding='Math.round(float32(value)*float32(10)) then low16',clearsPointsOnStartPack=True,clearsPointsOnStopPack=False,otherPhaseIntegersSupportedByOfflineModel=False),
        delay=dict(command='04:25',pointLimit=6,pointBytes=10,pointOrder=['duration:int32-low32','roll:int16','pitch:int16','yaw:int16'],infoSettersUseOrWithoutClearing=True,infoBits=dict(mode=0,tripod=1,phase=2,preview=3,externalDevice=7),clearsPointsAndInfoAfterPack=True),
        roninTimelapse=dict(command='04:37',pointLimit=5,pointBytes=10,modeBitOneProducesTwoBytes=True,pointCountRetainedInModeOne=True,totalDurationOverwritesFirstPointDurationAtOffset=2,totalDurationWidth=4,sourceEmptyModeZeroDurationCopyExceedsAllocation=True,clearsPointsAndInfoAfterPack=True),
        panorama=dict(command='04:63',bodyBytes=10,fields=[dict(name=name,offset=off,width=width) for name,off,width in [('left',0,2),('right',2,2),('top',4,1),('bottom',5,1),('horizontal',6,1),('vertical',7,1),('exposure',8,1),('command',9,1)]],sourceIntegersNarrowedWithoutClamping=True,cameraFieldsPresent=True),
        standaloneStatus=dict(panorama=dict(command='04:64',minimumBusinessBodyBytes=5,statusOffset=0,currentOffset=1,totalOffset=3,counterBytes=2),timelapse=dict(command='04:38',minimumBusinessBodyBytes=4,statusMask=3,previewBit=3,finishedOffset=1,currentOffset=2,totalOffset=3),sourceIsChangedSendsAck=True,automaticAckImplementedInSdk=False,timelapseEnumErrorValue=4,timelapseGetterCannotReturnEnumErrorFour=True),
        externalStatus=dict(command='04:6B',requestTypes=request_types,requestBodyLayout=['zero','requestType','one','programCommand'],sourceDefaultRequestType='StartContinuePush',sourceFirstByteSuccessValues=[0,1],sourceLengthAtMostOneLeavesSuccessUnchanged=True,sourceRecordTagAndLengthUseSignedBytes=True,sourceRecordHeaderBytes=2,sourceRecordLengthsValidated=False,recordMinimumBytes={'62':4,'37':4,'63':5},timelapseStatusMask=7,rawResponseOffsetsVerified=False,sourceSingletonRetainsOtherProgramFields=True),
        remaining=['Generic classes and UI references are not HG724/RS4Mini applicability or physical completion proof.', 'Preview/recording and external-device/camera branches need model and workflow audit; no SDK sends added.', 'Source unsigned narrowing, OR setters, duration overwrite, unchecked response lengths and cache retention are retained as evidence, not silently repaired.', 'No full CFG/model branch/receiver/ACK stripping/stop/recovery proof; banks1/7 and dynamic code remain outside scan.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d program method fingerprints; %d direct caller methods; no sends.'%(len(r['methods']),len(r['externalDirectCallers'])))
if __name__=='__main__':main()
