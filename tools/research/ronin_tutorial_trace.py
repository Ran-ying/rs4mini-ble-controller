#!/usr/bin/env python3
"""Audit tutorial state/step encoding offline, never execute vendor instructions."""
import argparse,hashlib,json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_subscription_trace import constructor_records
MODEL='Ldji/midware/data/model/P3/'
PUSH=MODEL+'DataGimbalGetPushTutorialStatus;'
STEP=MODEL+'DataGimbalSetTutorialStep;'
ENUM=PUSH[:-1]+'$TutorialStatus;'
FLAGS={'getIsUnlock':0,'getIsUpright':1,'getIsFollowFinish':2,'getIsStickFinish':3,'getIsLockDirectionFinish':4,'getIsRecentFinish':5,'getIsSelfieFinish':6,'getIsHandlePushFinish':7,'getIsAppControlFinish':8}
NAMES=('STEP_FINISH','STEP_START','STEP_UNLOCK_GIMBAL','STEP_HOLD_GIMBAL_UPRIGHT','STEP_FOLLOW','STEP_STICK','STEP_LOCK_DIRECTION','STEP_RECENTER','STEP_SELFIE','STEP_PUSH','STEP_APP_CONTROL')


def source_tutorial_body(body):
    if not isinstance(body,(bytes,bytearray)) or len(body)<5:raise ValueError('complete five-byte source body required')
    raw=body[0];word=int.from_bytes(body[1:5],'little')
    return dict(rawStep=raw,knownSourceStepName=NAMES[raw] if raw<len(NAMES) else None,sourceFindResult=NAMES[raw] if raw<len(NAMES) else 'STEP_FINISH',rawCompletionWord=word,sourceSignedCompletionWord=word if word<2147483648 else word-4294967296,unknownCompletionBits=word&0xfffffe00,sourceFlags={name:(word>>shift)&1 for name,shift in FLAGS.items()},bodyHex=body.hex())


def source_step_bit(word,enum_value):
    if type(word) is not int or not 0<=word<=0xffffffff or type(enum_value) is not int or not 0<=enum_value<=10:raise ValueError('source uint32 word and declared enum value required')
    return bool((word>>((enum_value-2)&31))&1)


def source_step_body(value):
    if type(value) is not int or not -2147483648<=value<=2147483647:raise ValueError('source Java int required')
    return bytes((value&255,))


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
    classes=None;callers=[];methods={}
    for bank,raw in images:
        current={c.get_name():c for c in DEX(raw).get_classes()}
        if bank==5:classes=current
        for owner,cls in current.items():
            if owner in (PUSH,STEP,ENUM):continue
            for m in cls.get_methods():
                if not m.get_code():continue
                refs=[dict(className=target,method=o.get_output().split('->',1)[1].split('(',1)[0]) for o in m.get_instructions() if o.get_name().startswith('invoke-') for target in (PUSH,STEP,ENUM) if target+'->' in o.get_output()]
                if refs:callers.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),references=refs))
    def take(owner,name,descriptor=None):
        ms=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(ms)!=1 or not ms[0].get_code():raise ValueError('missing or ambiguous tutorial method '+name)
        m=ms[0];methods[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(ops,token):
        if not any(token in text for _,text in ops):raise ValueError('missing tutorial evidence '+token)
    enum_records=constructor_records(take(ENUM,'<clinit>'),ENUM)
    if {name:row['arguments'][2] for name,row in enum_records.items()}!={name:i for i,name in enumerate(NAMES)}:raise ValueError('tutorial source enums changed')
    find=take(ENUM,'find');require(find,'->STEP_FINISH ');require(find,'->_equals(I)Z')
    take(ENUM,'_equals');take(ENUM,'value');take(PUSH,'getCurStep')
    for name,shift in FLAGS.items():
        ops=take(PUSH,name)
        require(ops,'v2, 1');require(ops,'v3, 4')
        # Fixed source methods: result conversion precedes bit extraction.
        shifted=next((i for i,(op,text) in enumerate(ops) if op.startswith('shr-int')),None)
        if shift==0:
            if shifted is not None:raise ValueError('unlock bit moved')
        elif shift==1:
            if shifted is None or ops[shifted]!=('shr-int/2addr','v0, v2'):raise ValueError('upright bit changed')
        elif shift==4:
            if shifted is None or ops[shifted]!=('shr-int/2addr','v0, v3'):raise ValueError('lock direction bit changed')
        elif shifted is None or ops[shifted]!=('shr-int/lit8','v0, v0, '+str(shift)):raise ValueError('tutorial bit shift changed')
        if ops[-2:]!=[('and-int/2addr','v0, v2'),('return','v0')]:raise ValueError('tutorial flag suffix changed')
    dynamic=take(PUSH,'getStepStatus')
    for token in ('v6, v6, -2','v6, v0, v6','v6, v3'):require(dynamic,token)
    for owner in (PUSH,STEP):
        for name in ('<init>','doPack'):take(owner,name)
    setter=take(STEP,'setCurStep')
    if setter[:2]!=[('int-to-byte','v1, v1'),('iput-byte','v1, v0, '+STEP+'->mCurStep B')]:raise ValueError('step narrowing changed')
    require(take(STEP,'start'),'CmdIdGimbal$CmdIdType;->SetTutorialStep ')
    require(take(STEP,'start'),'DataConfig$NEEDACK;->YES ')
    base='Ldji/midware/data/manager/P3/DataBase;'
    if classes[PUSH].get_superclassname()!=base or any(m.get_name() in ('get','setRecData','setPushRecData','setPushRecPack') for m in classes[PUSH].get_methods()):raise ValueError('tutorial common receive path changed')
    for name in ('setPushRecPack','setPushRecData','setRecData'):take(base,name)
    require(take(base,'get','(I I Ljava/lang/Class; [I)Ljava/lang/Number;'),'BytesUtil;->getInt([B)I')
    require(take('Ldji/midware/util/BytesUtil;','getInt','([B)I'),'ByteOrder;->LITTLE_ENDIAN ')
    take('Ldji/midware/data/packages/P3/RecvPack;','setBuffer')
    command='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;';entries=constructor_records(take(command,'<clinit>'),command)
    binding={name:entries[name]['arguments'] for name in ('GetPushTutorialStatus','SetTutorialStep')}
    if [binding[k][2] for k in binding]!=[43,44] or binding['GetPushTutorialStatus'][-1]!=PUSH:raise ValueError('tutorial command binding changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(k):v for k,v in BANKS.items()},appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,
        minimumBodyBytes=5,currentStepOffset=0,completionWordOffset=1,completionWordBytes=4,completionWordSignedInSource=True,flagShifts=FLAGS,sourceEnums={name:i for i,name in enumerate(NAMES)},sourceUnknownEnumFallback='STEP_FINISH',unknownStepIsCompletionVerified=False,sourceDynamicStepShift='(enumValue - 2) & 31',sourceFinishAndStartSelectBits=[30,31],knownCompletionMask=511,
        sourceSend=dict(command='04:2C',payloadBytes=1,javaIntNarrowedToByte=True,ackRequested=True,hg724CallPathEstablished=False,sendEnabledInSdk=False),commandEnumArguments=binding,externalCallers=callers,methods=list(methods.values()),remaining=['Tutorial flags are not gimbal motion completion or a program-cancellation acknowledgement.', 'Preserve unknown raw step rather than replacing it with STEP_FINISH in SDK.', 'No target model layout, actual notifications or send2C effects established.', 'Banks1/7, residual stubs and dynamic paths remain outside scan.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d tutorial fingerprints; %d external caller methods; no sends.'%(len(r['methods']),len(r['externalCallers'])))

if __name__=='__main__':main()
