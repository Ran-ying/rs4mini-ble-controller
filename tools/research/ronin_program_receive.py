#!/usr/bin/env python3
"""Audit conditional base command-table receive paths; no vendor/SDK execution."""
import argparse,hashlib,json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_subscription_trace import constructor_records
from ronin_program_trace import COMMANDS,EXTERNAL
CONFIG='Ldji/midware/data/config/P3/'
ENUM=CONFIG+'CmdIdGimbal$CmdIdType;'
BASE='Ldji/midware/data/manager/P3/DataBase;'
RECV='Ldji/midware/data/packages/P3/RecvPack;'
TABLE=CONFIG+'DJICmdSetBase;'
GIMBAL=CONFIG+'CmdIdGimbal;'
MANAGER='Ldji/midware/data/manager/P3/DJIPackManagerBase;'


def source_payload_view(flags,payload,*,needs_ccode):
    """Stateless validated byte view; not a DUML frame parser or pooled RecvPack."""
    if type(flags) is not int or not 0<=flags<=255 or type(needs_ccode) is not bool:raise ValueError('explicit flags and source ccode context required')
    if not isinstance(payload,(bytes,bytearray)):raise ValueError('raw payload bytes required')
    if flags&7:raise ValueError('encrypted source payload not interpreted')
    strip=bool(flags&128) and needs_ccode
    if strip and not payload:raise ValueError('missing ACK return-code byte')
    body=bytes(payload[1:] if strip else payload)
    return dict(rawPayloadHex=payload.hex(),flags=flags,isAck=bool(flags&128),returnCode=payload[0] if strip else None,businessOffsetInPayload=int(strip),businessBodyHex=body.hex(),sourceWouldAssignData=bool(body))


def delivery_paths(*,is_block,is_mix,is_ble_ping=False):
    if any(type(v) is not bool for v in (is_block,is_mix,is_ble_ping)):raise ValueError('explicit source booleans required')
    return dict(processorPathEligible=is_block or is_mix,pushPathEligible=not is_block or is_ble_ping)


def program_policy(record):
    args=record['arguments'];descriptor=record['descriptor']
    valid={
        '(Ljava/lang/String; I I)V':3,
        '(Ljava/lang/String; I I Z Ljava/lang/Class;)V':5,
        '(Ljava/lang/String; I I Z Z Ljava/lang/Class;)V':6}
    if descriptor not in valid or len(args)!=valid[descriptor]:raise ValueError('unrecognized source command constructor')
    if type(args[0]) is not str or type(args[2]) is not int or not 0<=args[2]<=255:raise ValueError('explicit byte-sized source command required')
    if len(args)>3 and (type(args[-1]) is not str or not args[-1].startswith('L') or not args[-1].endswith(';')):raise ValueError('unresolved source model class')
    for flag in args[3:-1] if len(args)>3 else []:
        if type(flag) is not int or flag not in (0,1):raise ValueError('unresolved source boolean literal')
    return dict(name=args[0],commandId=args[2],isBlock=True if len(args)==3 else bool(args[3]),isMix=bool(args[4]) if len(args)==6 else False,modelClass=args[-1] if len(args)>3 else None)


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
    classes={};extensions=[];bank_counts=[]
    for bank,raw in images:
        current={c.get_name():c for c in DEX(raw).get_classes()}
        if bank==5:classes=current
        extensions.extend(dict(bank=bank,className=n) for n in current if n.startswith('Lcom/dji/midware/extension/config/'))
        bank_counts.append(dict(bank=bank,classCount=len(current)))
    methods={}
    def take(owner,name,descriptor=None):
        choices=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(choices)!=1 or not choices[0].get_code():raise ValueError('missing or ambiguous receive method '+name)
        m=choices[0];methods[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(ops,*tokens):
        for token in tokens:
            if not any(token in text for _,text in ops):raise ValueError('missing receive source token '+token)
    entries=constructor_records(take(ENUM,'<clinit>'),ENUM)
    policies=[program_policy(entries[name]) for name in COMMANDS]
    if any(p['commandId']!=COMMANDS[p['name']] for p in policies):raise ValueError('program command id changed')
    if take(ENUM,'isNeedCcode')!=[('const/4','v0, 1'),('return','v0')]:raise ValueError('base gimbal ccode rule changed')
    for descriptor in ('(Ljava/lang/String; I I)V','(Ljava/lang/String; I I Z Ljava/lang/Class;)V','(Ljava/lang/String; I I Z Z Ljava/lang/Class;)V'):take(ENUM,'<init>',descriptor)
    for name in ('isBlock','isMix','getDataBase','getDataModel'):take(ENUM,name)
    if classes[GIMBAL].get_superclassname()!=TABLE:raise ValueError('gimbal table inheritance changed')
    require(take(GIMBAL,'getCurCmdIdValues'),ENUM+'->values()')
    require(take(TABLE,'<init>'),'->getCurCmdIdValues()','->value()I','SparseArray;->put(')
    for name in ('isBlock','isMix','isNeedCcode','getDataBase','getDataModel'):
        require(take(TABLE,name),'->mIdCmdSpArray ','DefaultCmdIdForAll;->getInstance()', 'CmdIdInterface;->'+name+'(')
    require(take(RECV,'getInt','(I)I'),'BytesUtil;->getInt(B)S')
    if take('Ldji/midware/util/BytesUtil;','getInt','(B)S')!=[('and-int/lit16','v0, v0, 255'),('int-to-short','v0, v0'),('return','v0')]:raise ValueError('unsigned header byte conversion changed')
    receive=take(RECV,'setBuffer');require(receive,'v5, v5, 7','v4, 11','v4, 12','->ccode I','->data [B')
    require(take(RECV,'isNeedCcode'),'->cmdIdClass()','->isNeedCcode(I)Z')
    manager=take(MANAGER,'setMsg');require(manager,'->isBlock(I)Z','->isMix(I)Z','DataBaseProcessor;->setMsg(','->isBlePing(','->setPushRecPack(')
    take(MANAGER,'isBlePing')
    require(take(BASE,'setPushRecPack'),'Pack;->data [B','->setPushRecData([B)V')
    base_push=take(BASE,'setPushRecData');require(base_push,'->setRecData([B)V','->post()V','->isWantPush()Z','->isRegist Z')
    take(BASE,'setRecData');take(BASE,'isChanged');require(take(BASE,'post'),'ServiceManager;->isAlive()Z','EventBus;->post(')
    external=take(EXTERNAL,'setPushRecData')
    if external[0][0]!='invoke-super' or BASE+'->setPushRecData([B)V' not in external[0][1]:raise ValueError('external status super/decode order changed')
    for name in ('doPack','isSuccess'):take(EXTERNAL,name)
    cmdset=CONFIG+'CmdSet;'
    require(take(cmdset,'<init>','(Ljava/lang/String; I I Ldji/midware/data/config/P3/DJICmdSetBase;)V'),'->getExtraCmdSetInterface(','->cls ')
    require(take(cmdset,'getExtraCmdSetInterface'),'com.dji.midware.extension.config.','Extra','->forName(','->newInstance()')
    take(cmdset,'cmdIdClass')
    for owner in ('Ldji/midware/data/model/P3/DataGimbalGetPushPanoramaStatus;','Ldji/midware/data/model/P3/DataGimbalGetPushTimelapseStatus;'):
        require(take(owner,'isChanged'),'->start()V');require(take(owner,'start'),'CMDTYPE;->ACK ')
    mix=next(p for p in policies if p['commandId']==107)
    if mix['isBlock'] or not mix['isMix'] or mix['modelClass']!=EXTERNAL:raise ValueError('base6B mix policy changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(k):v for k,v in BANKS.items()},appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,javaReflectionExecuted=False,actualCmdSetExtensionSelectionVerified=False,
        scope='Conditional base Gimbal command table, RecvPack payload extraction and selected mixed receive dispatch; not target traffic or all extension classes',banks=bank_counts,baseProgramPolicies=policies,methods=list(methods.values()),
        payloadMapping=dict(sourceBasePathEstablished=True,rawFramePayloadOffset=11,ackFlagBit=7,encryptedFlagMask=7,baseProgramNeedsCcode=True,ackBusinessOffsetInRawPayload=1,requestBusinessOffsetInRawPayload=0,sourceOnlyAssignsDataWhenNonempty=True,sourceParserIsNotFullFrameValidation=True),
        mixed6B=dict(baseBlock=False,baseMix=True,processorAndPushPathsEligible=True,processorCorrelationInternalsVerified=False,pushLookupOrReflectionCanFail=True,returnCodeIsNotBusinessSuccessByte=True,requestBodyFirstByteNotStripped=True),
        eventOrder=dict(derivedCallsBaseBeforeParsing=True,baseMayPostBeforeDerivedFieldsParsed=True,actualSubscriberTimingVerified=False,basePostRequiresChangedWantPushRegisteredAndServiceAlive=True,sourceStoresPayloadReferencePerSenderId=True),
        extensionLookup=dict(className='Lcom/dji/midware/extension/config/CmdIdGimbalExtra;',namespaceMatchesInSixRestoredBanks=extensions,unrestoredBanks=[1,7],dynamicExtensionAbsenceProven=False),
        remaining=['CmdSet constructor can choose a reflection-loaded Extra implementation; six-bank absence is not whole-App absence.', 'DataBaseProcessor matching/callbacks, encryption/decryption and full outer frame validation remain separately scoped.', 'Do not turn ACK ccode=0, business success=1, shared events or base post order into target motion completion.', 'No SDK receive mapping or send allowlist was changed; actual RS4Mini frames and physical effects unverified.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d receive method fingerprints; %d base program policies; no reflection or sends.'%(len(r['methods']),len(r['baseProgramPolicies'])))
if __name__=='__main__':main()
