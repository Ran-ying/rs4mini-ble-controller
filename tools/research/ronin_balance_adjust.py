#!/usr/bin/env python3
"""Read-only BalanceAdjust business-body audit; no DUML, SDK, App or hardware execution."""
import argparse,hashlib,json,re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_subscription_trace import constructor_records
MODEL='Ldji/midware/data/model/P3/'
SET=MODEL+'DataGimbalBalanceAdjust;'
PUSH=MODEL+'DataGimbalGetBalanceAdjustPushInfo;'
VIEW='Lcom/dji/ronin/ui/monitor/state/GimbalAdjustView;'
REQUESTS={'PITCH_TEST':1,'PITCH_ADJUST':2,'ROLL_TEST':4,'ROLL_ADJUST':8,'YAW_TEST':16,'YAW_ADJUST':32,'STOP_ADJUST':64,'OTHER':100}
STATUS={'TEST_NOT_IN_PROCESS':0,'TEST_IN_PROCESS':1,'TEST_FINISHED':10,'TEST_ERROR':11}
RESULT={'DEFAULT':0,'PERFECT':1,'OKAY':10,'BAD':11}


def source_request_body(name):
    if type(name) is not str or name not in REQUESTS:raise ValueError('declared source request name required')
    return bytes((0,1,REQUESTS[name]))


def decimal_pair(value,shift):
    if type(value) is not int or not 0<=value<=255 or type(shift) is not int or shift not in (0,2,4,6):raise ValueError('uint8 and two-bit field position required')
    # Source Integer.valueOf(String), without radix2: "10" becomes decimal10.
    return int(format((value>>shift)&3,'02b'),10)


def source_business_body(body):
    if not isinstance(body,(bytes,bytearray)) or len(body)<6:raise ValueError('complete six-byte candidate business body required')
    body=bytes(body);recognized=body[0]==0
    def field(shift,names):
        value=decimal_pair(body[2],shift)
        return dict(rawTwoBits=(body[2]>>shift)&3,sourceDecimalValue=value,sourceName=next(k for k,v in names.items() if v==value))
    return dict(rawType=body[0],sourceTypeRecognized=recognized,rawLengthByte=body[1],lengthByteValidatedBySource=False,rawPackedResults=body[2],sourceTestStatus=field(0,STATUS) if recognized else None,sourceResults={axis:field(shift,RESULT) for axis,shift in [('pitch',2),('roll',4),('yaw',6)]} if recognized else None,rawAdvice={axis:body[offset] for axis,offset in [('pitch',3),('roll',4),('yaw',5)]} if recognized else None,bodyHex=body.hex(),trailingHex=body[6:].hex(),targetDeviceVerified=False,physicalCompletionVerified=False)


def invoked_owner(text):
    # Argument/return descriptors may mention a class without invoking that class.
    match=re.search(r'(L[^\s,]+;)->([^\s(]+)\(',text)
    return (match.group(1),match.group(2)) if match else None


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
    classes={};methods={};callers=[];typed=[]
    def belongs(owner):return owner in (SET,PUSH) or owner.startswith((SET[:-1]+'$',PUSH[:-1]+'$'))
    def take(bank,owner,name,descriptor=None):
        found=[m for m in classes[bank][owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing or ambiguous balance method '+owner+name)
        m=found[0];methods[(bank,owner,name,m.get_descriptor())]=dict(bank=bank,className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
        return [(i.get_name(),i.get_output()) for i in m.get_instructions()]
    def require(ops,*tokens):
        for token in tokens:
            if not any(token in text for _,text in ops):raise ValueError('missing balance evidence '+token)
    for bank,raw in images:
        current={c.get_name():c for c in DEX(raw).get_classes()}
        if bank in (3,5):classes[bank]=current
        for owner,c in current.items():
            if belongs(owner):continue
            for m in c.get_methods():
                if any(target in m.get_descriptor() for target in (SET,PUSH)):typed.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor()))
                if not m.get_code():continue
                refs=[]
                for i in m.get_instructions():
                    if not i.get_name().startswith('invoke-'):continue
                    target=invoked_owner(i.get_output())
                    if target and belongs(target[0]):refs.append(dict(className=target[0],method=target[1]))
                if refs:
                    callers.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),references=refs))
                    if bank not in classes:classes[bank]=current
                    take(bank,owner,m.get_name(),m.get_descriptor())
    enums={}
    for owner,label,expected,fallback in [(SET[:-1]+'$GimbalAdjustRequest;','requests',REQUESTS,'OTHER'),(SET[:-1]+'$GimbalAdjustTypeId;','types',{'ADJUST_REQUEST':0,'OTHER':100},'OTHER'),(PUSH[:-1]+'$GimbalTestStatus;','status',STATUS,'TEST_NOT_IN_PROCESS'),(PUSH[:-1]+'$GimbalTestResult;','results',RESULT,'DEFAULT'),(PUSH[:-1]+'$GimbalBalanceAdjustAdvice;','advice',None,'OTHER')]:
        values=constructor_records(take(5,owner,'<clinit>'),owner);values={n:r['arguments'][2] for n,r in values.items()}
        if expected is not None and values!=expected:raise ValueError('balance enum values changed '+label)
        enums[label]=values
        require(take(5,owner,'find'),'->'+fallback+' ','->_equals(I)Z')
        take(5,owner,'value');take(5,owner,'_equals');take(5,owner,'<init>')
    for name in ('<init>','getInstance','doPack','setSendData','setGimbalAdjustRequest','start'):take(5,SET,name)
    require(take(5,SET,'setSendData'),'v0, v5, 2','v0, v5','System;->arraycopy(')
    if ('int-to-byte','v5, v5') not in take(5,SET,'setGimbalAdjustRequest'):raise ValueError('request narrowing changed')
    require(take(5,SET,'setGimbalAdjustRequest'),'->ADJUST_REQUEST ','v5, v5','v1, 1','->setSendData(')
    require(take(5,SET,'start'),'->APP ','->GIMBAL ','->receiverId I','->REQUEST ','->YES ','->NO ','->BalanceAdjust ','->repeatTimes I')
    take(5,PUSH,'<clinit>');take(5,PUSH,'<init>');take(5,PUSH,'doPack');take(5,PUSH,'getInstance')
    receive=take(5,PUSH,'setPushRecData')
    require(receive,'v1, v2, +004h','v6, v6, v1','->getBinaryStrFromByte(B)','->substring(I I)','Integer;->valueOf(Ljava/lang/String;)','->mGimbalTestStatus I','->mPitchTestResult I','->mRollTestResult I','->mYawTestResult I','v4, 3','v1, 5','EventBus;->post(')
    for name in ('getGimbalTestStatus','getPitchTestResult','getRollTestResult','getYawTestResult','getPitchAdjustAdvice','getRollAdjustAdvice','getYawAdjustAdvice'):take(5,PUSH,name)
    binary=take(5,'Ldji/midware/util/BytesUtil;','getBinaryStrFromByte')
    for shift in range(1,8):require(binary,'v1, v2, '+str(shift))
    require(binary,'v2, v2, 1','StringBuilder;->append(I)')
    enum='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;'
    binding=constructor_records(take(5,enum,'<clinit>'),enum)['BalanceAdjust']['arguments']
    if binding!=['BalanceAdjust',29,64,0,1,PUSH]:raise ValueError('BalanceAdjust table binding changed')
    ui_names=('sendGimbalAdjustRequest','startTestCurrentAxis','startAdjustCurrentAxis','onGimbalTestError','onGimbalTestFinished','onGimbalTestTimeout','setTimer','disposeTimer','onAttachedToWindow','onDetachedFromWindow','onEvent3MainThread','exit')
    for name in ui_names:take(3,VIEW,name)
    require(take(3,VIEW,'sendGimbalAdjustRequest'),SET+'->getInstance()',SET+'->setGimbalAdjustRequest(',SET+'->start(')
    require(take(3,VIEW,'setTimer'),'v0, 20000','Observable;->timer(')
    require(take(3,VIEW,'onAttachedToWindow'),'MotorEnabled','CacheHelper;->setGimbal(','v2, 0','Ronin_sc_motor_banlance_test_tutorial')
    for name in ('onGimbalTestError','onGimbalTestFinished','onGimbalTestTimeout'):require(take(3,VIEW,name),'->STOP_ADJUST ','->sendGimbalAdjustRequest(')
    detached=take(3,VIEW,'onDetachedFromWindow')
    if any('->sendGimbalAdjustRequest(' in text for _,text in detached):raise ValueError('detach now sends stop')
    require(take(3,VIEW,'exit'),'->ConfigSettingBalanceTestHG701 ')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(k):v for k,v in BANKS.items()},appCodeExecuted=False,liveUiExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,sdkSendAdded=False,sdkReceiveAdded=False,hg724EntryEstablished=False,methods=sorted(methods.values(),key=lambda r:(r['bank'],r['className'],r['method'],r['descriptor'])),directCallers=callers,typedDeclarations=typed,sourceEnums=enums,commandEnumArguments=binding,sourceRequest=dict(command='04:40',bodyHexByName={n:source_request_body(n).hex() for n in REQUESTS},receiverId=0,ackRequested=True,repeatTimes=1,sendEnabledInSdk=False),sourceReceive=dict(command='04:40',sameCommandAsRequest=True,typeByte=0,lengthByteReadButNotValidated=True,packedOffset=2,sourceGuardOnlyLengthGreaterThanOne=True,completeCandidateBytes=6,statusShift=0,pitchShift=2,rollShift=4,yawShift=6,bitPairsParsedAsDecimalStrings=True,adviceOffsets=dict(pitch=3,roll=4,yaw=5),staticSingletonFields=True,unknownTypeLeavesPriorFields=True,physicalCompletionVerified=False),sourceUi=dict(timerMs=20000,attachMayDisableMotors=True,stopOnErrorFinishedTimeout=True,detachSendsStop=False,exitView='ConfigSettingBalanceTestHG701',modelNameOrAnalyticsLabelProvesHg724=False),scope=dict(restoredBanks=sorted(BANKS),unrestoredBanks=[1,7],reflectionNativeOrOtherClassLoadersRuledOut=False),remaining=['No HG724 entry, target firmware acceptance or physical stop/completion evidence.','Business-body offsets are not independently confirmed target BLE payload offsets.','Do not inherit source short-body reads, decimal-pair names or static stale cache as target-device semantics.','Separate from HG724 balance_test/index37 through 04:0F/10.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d fingerprints; %d direct caller methods; no sends.'%(len(r['methods']),len(r['directCallers'])))
if __name__=='__main__':main()
