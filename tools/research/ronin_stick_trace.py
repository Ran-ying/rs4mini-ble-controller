#!/usr/bin/env python3
"""Audit handheld stick source layouts without target support or sends."""
import argparse,hashlib,json,re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_subscription_trace import constructor_records
MODEL='Ldji/midware/data/model/P3/'
PUSH=MODEL+'DataGimbalGetPushHandheldStickState;'
SET=MODEL+'DataGimbalSetHandheldStickControlEnabled;'
MOBILE='Ldji/sdksharedlib/hardware/abstractions/handheldcontroller/MobileHandheldControllerAbstraction;'


def short_context(operations):
    registers={}
    for i,(op,text) in enumerate(operations):
        if op in ('const/4','const/16','const'):
            reg,value=text.split(', ',1);registers[reg]=int(value)
        elif op=='const-class':
            reg,value=text.split(', ',1);registers[reg]=value
        elif op=='new-array':registers[text.split(', ')[0]]=None
        elif op=='invoke-virtual' and PUSH+'->get(I I Ljava/lang/Class; [I)' in text:
            regs=re.findall(r'v\d+',text.split(', '+PUSH)[0])
            if len(regs)!=5 or registers.get(regs[3])!='Ljava/lang/Short;' or registers.get(regs[2])!=2:raise ValueError('unresolved signed short getter')
            offset=registers.get(regs[1])
            if type(offset) is not int or offset<0:raise ValueError('unresolved short offset')
            return offset,operations[i+1:]
        else:raise ValueError('unsupported short getter prefix '+op)
    raise ValueError('missing short getter')


def source_stick_body(body):
    if not isinstance(body,(bytes,bytearray)) or len(body)<6:raise ValueError('complete six-byte source body required')
    word=int.from_bytes(body[4:6],'little')
    return dict(sourceStickX=int.from_bytes(body[:2],'little',signed=True),sourceStickY=int.from_bytes(body[2:4],'little',signed=True),rawStateWord=word,unknownStateBits=word&65532,sourceTriggerPressed=bool(word&1),sourceStickControlEnabled=bool(word&2),bodyHex=body.hex())


def source_enable_body(enabled):
    if type(enabled) is not bool:raise ValueError('explicit source boolean required')
    return bytes((int(enabled),))


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
    callers=[];fingerprints={};classes=None
    for bank,raw in images:
        current={c.get_name():c for c in DEX(raw).get_classes()}
        if bank==5:classes=current
        for owner,cls in current.items():
            if owner in (PUSH,SET):continue
            for m in cls.get_methods():
                if not m.get_code():continue
                refs=[o.get_output().split('->',1)[1].split('(',1)[0] for o in m.get_instructions() if o.get_name().startswith('invoke-') and any(x+'->' in o.get_output() for x in (PUSH,SET))]
                if refs:callers.append(dict(bank=bank,className=owner,method=m.get_name(),descriptor=m.get_descriptor(),targetMethods=refs))
    def take(owner,name,descriptor=None):
        ms=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(ms)!=1 or not ms[0].get_code():raise ValueError('missing or ambiguous stick method '+name)
        m=ms[0];fingerprints[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(ops,token):
        if not any(token in text for _,text in ops):raise ValueError('missing stick evidence '+token)
    fields=[]
    for name,expected in [('getStickX',0),('getStickY',2),('isTriggerPressed',4),('isStickGimbalControlEnabled',4)]:
        ops=take(PUSH,name);offset,tail=short_context(ops)
        if offset!=expected:raise ValueError('stick field offset changed')
        require(tail,'Ljava/lang/Short;->shortValue()S')
        fields.append(dict(sourceGetter=name,offset=offset,size=2,signedShort=True))
    for owner in (PUSH,SET):
        for name in ('<init>','doPack','getInstance'):take(owner,name)
    take(SET,'setHandheldStickControlEnabled');start=take(SET,'start')
    for token in ('DeviceType;->APP ','DeviceType;->GIMBAL ','DataConfig$NEEDACK;->YES ','CmdIdGimbal$CmdIdType;->SetHandheldStickControlEnabled '):require(start,token)
    event=take(MOBILE,'onEvent3BackgroundThread','('+PUSH+')V');require(event,'StickGimbalControlEnabled');require(event,'IsTriggerBeingPressed')
    setter_name='setIsInternalAndExternalMicroPhonesEnabled'
    require(take(MOBILE,setter_name),SET+'->setHandheldStickControlEnabled(Z)')
    for name in ('onSuccess','onFailure'):take(MOBILE[:-1]+'$3;',name)
    base='Ldji/midware/data/manager/P3/DataBase;'
    if classes[PUSH].get_superclassname()!=base or any(m.get_name() in ('get','setPushRecData','setRecData','setPushRecPack') for m in classes[PUSH].get_methods()):raise ValueError('push model overrides common body path')
    require(take(base,'get','(I I Ljava/lang/Class; [I)Ljava/lang/Number;'),'BytesUtil;->getShort([B)S')
    require(take('Ldji/midware/util/BytesUtil;','getShort','([B)S'),'ByteOrder;->LITTLE_ENDIAN ')
    for name in ('setPushRecPack','setPushRecData','setRecData'):take(base,name)
    take('Ldji/midware/data/packages/P3/RecvPack;','setBuffer')
    enum='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;';entries=constructor_records(take(enum,'<clinit>'),enum)
    selected={k:entries[k]['arguments'] for k in ('GetPushHandheldStickState','SetHandheldStickControlEnabled')}
    if [selected[k][2] for k in selected]!=[87,88] or selected['GetPushHandheldStickState'][-1]!=PUSH:raise ValueError('stick enum binding changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(k):v for k,v in BANKS.items()},appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,
        fields=fields,minimumBodyBytes=6,signedLittleEndian=True,triggerMask=1,controlEnabledMask=2,unknownStateMask=65532,rawRequestBodyFramingEstablished=True,targetLayoutVerified=False,
        commandEnumArguments=selected,sourceSend=dict(command='04:58',bodyFalseHex='00',bodyTrueHex='01',ackRequested=True,hg724CallPathEstablished=False,sendEnabledInSdk=False),
        externalCallers=callers,sourceSetterMethodName=setter_name,setterNameDoesNotEstablishMicrophoneSemantics=True,
        remaining=['MobileHandheldController caller is not an HG724 model binding.', 'Passive source interpretation only; no target live state, units, center or axis mapping established.', 'Do not send58, subscribe or infer microphone control from mismatched source method name.', 'Banks1/7, residual stubs and dynamic paths remain outside scan.'],methods=list(fingerprints.values()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d stick method fingerprints; %d external callers; no sends.'%(len(r['methods']),len(r['externalCallers'])))

if __name__=='__main__':main()
