#!/usr/bin/env python3
"""HG724 inherited CENTER activation-info route and generic module gates; offline only."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS
from ronin_activation_trace import ROOT, GIMBAL, QUERY, VERSION, TYPE, nullable_literal_enums
from ronin_registration_trace import nearest_declaration
from ronin_calibration_transport import branch_target
CENTER = 'Ldji/midware/data/model/P3/DataCenterActiveStatus;'
TARGET = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalHG724Abstraction;'
RONIN = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalRonin2Abstraction;'
CALLBACK = RONIN[:-1] + '$8;'
DEVICE_TYPE = 'Ldji/midware/data/config/P3/DeviceType;'
GETTER = 'Ldji/sdksharedlib/hardware/abstractions/Getter;'
GET_DESC = '(Ldji/sdksharedlib/hardware/abstractions/DJISDKCacheHWAbstraction$InnerCallback;)V'
FIELDS = {'module_type_', 'module_cnt_', 'componentTypeMsg'}


def source_module_gate(expected, sender, *, format_name, module_type=None):
    for value in (expected, sender):
        if type(value) is not int or not 0 <= value <= 255:
            raise ValueError('explicit uint8 expected/sender context required')
    if format_name not in ('sourceV13', 'sourceV14'):
        raise ValueError('explicit V13 or V14 handler context required')
    if format_name == 'sourceV14':
        if type(module_type) is not int or not 0 <= module_type <= 255:
            raise ValueError('explicit V14 module type required')
    elif module_type is not None:
        raise ValueError('V13 handler has no parsed module-type gate')
    sender_match = sender == expected
    module_match = module_type == expected if format_name == 'sourceV14' else None
    return dict(sourceSenderMatches=sender_match, sourceModuleMatches=module_match,
                sourceHandlerGatePasses=sender_match and module_match is not False,
                runtimeModuleContextVerified=False, targetDeviceVerified=False,
                handlerExecuted=False, replyEnabled=False)


def source_push_sn_choice(cached_push_sn, decoded_get_sn):
    """Expose source cache-choice quirk; never a proposed SDK cache policy."""
    if any(type(v) is not str for v in (cached_push_sn, decoded_get_sn)):
        raise ValueError('explicit source strings required')
    return decoded_get_sn if not cached_push_sn or (decoded_get_sn and cached_push_sn != decoded_get_sn) else cached_push_sn


def check_module_default(rows):
    by = {off: (op, text) for off, op, text in rows}
    if by.get(6) != ('const/16', 'v0, 8') or by.get(14) != ('iput', 'v0, v3, ' + ROOT + '->module_type_ I'):
        raise ValueError('source module default producer changed')


def check_push_sn_choice(rows):
    by={off:(op,text) for off,op,text in rows}
    for off,target in [(20,52),(32,56),(48,56)]:
        if by.get(off,('',))[0]!='if-nez' or branch_target(off,by[off][1])!=target:
            raise ValueError('source getPushSN cache choice branch changed')
    if by.get(52)!=('iput-object','v0, v2, '+ROOT+'->pushSN Ljava/lang/String;') or by.get(56)!=('iget-object','v0, v2, '+ROOT+'->pushSN Ljava/lang/String;'):
        raise ValueError('source getPushSN cache write/read changed')


def trace(apk, bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest() != APK_SHA256:
        raise ValueError('APK hash mismatch')
    images = []
    for bank, pin in PREFIX_BANKS.items():
        raw = (bank_dir / ('business-%02d-prefix-code-restored.dex' % bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest() != pin:
            raise ValueError('prefix bank hash mismatch: %02d' % bank)
        images.append((bank, raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes = {}
    dexes = {}
    methods = {}
    field_refs = []

    def take(bank, owner, name, descriptor=None):
        ms = [m for m in classes[bank][owner].get_methods() if m.get_name() == name
              and (descriptor is None or m.get_descriptor() == descriptor)]
        if len(ms) != 1 or not ms[0].get_code():
            raise ValueError('missing/ambiguous entry method ' + owner + name)
        m = ms[0]
        methods[(bank, owner, name, m.get_descriptor())] = dict(bank=bank, className=owner,
            method=name, descriptor=m.get_descriptor(), codeOffset=m.get_code_off(),
            instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
        off = 0
        rows = []
        for i in m.get_instructions():
            rows.append((off, i.get_name(), i.get_output())); off += i.get_length()
        return rows

    def ops(rows):return [(op, text) for _, op, text in rows]
    def require(rows, *tokens):
        for token in tokens:
            if not any(token in text for _, _, text in rows):
                raise ValueError('missing activation entry evidence ' + token)

    for bank, raw in images:
        d = DEX(raw)
        current = {c.get_name(): c for c in d.get_classes()}
        if bank == 5:
            classes[bank] = current; dexes[bank] = d
        for owner, c in current.items():
            for m in c.get_methods():
                if not m.get_code():continue
                refs = []
                off = 0
                for i in m.get_instructions():
                    op, text = i.get_name(), i.get_output()
                    match = re.search(r'(L[^\s,]+;)->(module_type_|module_cnt_|componentTypeMsg) ([^\s]+)$', text)
                    if match and op.startswith(('iget', 'iput', 'sget', 'sput')):
                        refs.append(dict(offset=off, operation=op, referenceOwner=match.group(1),
                                         field=match.group(2), fieldType=match.group(3),
                                         writesField=op.startswith(('iput', 'sput'))))
                    off += i.get_length()
                if refs:
                    classes[bank] = current
                    take(bank, owner, m.get_name(), m.get_descriptor())
                    field_refs.append(dict(bank=bank, className=owner, method=m.get_name(),
                                           descriptor=m.get_descriptor(), references=refs))
    cs = classes[5]
    chain = []
    owner = TARGET
    while owner in cs:
        if owner in chain:raise ValueError('cyclic HG724 inheritance')
        chain.append(owner); owner = cs[owner].get_superclassname()
    declarations = {n: dict(superclass=c.get_superclassname(), methods=[dict(method=m.get_name(),
                    descriptor=m.get_descriptor(), accessFlags=m.get_access_flags()) for m in c.get_methods()]) for n, c in cs.items()}
    resolved = nearest_declaration(declarations, TARGET, 'getSerialNumber', GET_DESC)
    if resolved['className'] != RONIN:raise ValueError('HG724 serial getter provider changed')
    getter = take(5, RONIN, 'getSerialNumber', GET_DESC)
    require(getter, CENTER+'->getInstance()', DEVICE_TYPE+'->CENTER ', 'v1, 7',
            CENTER+'->setReceiverId(I)', TYPE+'->GET ', CENTER+'->setType(', CENTER+'->start(')
    # Read the actual Getter annotation, without running reflection/registry code.
    dex = dexes[5]; cm = dex.get_class_manager(); c = cs[RONIN]
    selected = next(m for m in c.get_methods() if m.get_name()=='getSerialNumber' and m.get_descriptor()==GET_DESC)
    directory = cm.get_annotations_directory_item(c.get_annotations_off())
    annotations = []
    for row in directory.get_method_annotations():
        if row.get_method_idx() != selected.get_method_idx():continue
        for entry in cm.get_annotation_set_item(row.get_annotations_off()).get_annotation_off_item():
            a = entry.get_annotation_item().get_annotation()
            if dex.get_cm_type(a.get_type_idx()) != GETTER:continue
            annotations.append({dex.get_cm_string(e.get_name_idx()):e.get_value().get_value() for e in a.get_elements()})
    if annotations != [dict(value='GimbalSerialNumber')]:raise ValueError('serial Getter annotation changed')
    for name in ('<init>','getInstance','doPack','start'):take(5,CENTER,name)
    if cs[CENTER].get_superclassname()!=ROOT or cs[GIMBAL].get_superclassname()!=ROOT:
        raise ValueError('activation model inheritance changed')
    require(take(5,CENTER,'<init>'), 'v0, 7', '->receiverID I', DEVICE_TYPE+'->CENTER ', '->receiverType ')
    require(take(5,CENTER,'doPack'), ROOT+'->doPack()V')
    start=take(5,CENTER,'start')
    require(start, DEVICE_TYPE+'->APP ', CENTER+'->receiverType ', CENTER+'->receiverID I',
            'CmdSet;->COMMON ', 'CmdIdCommon$CmdIdType;->ActiveStatus ', 'NEEDACK;->YES ',
            'EncryptType;->NO ', 'v1, 1000', 'v1, 3')
    devices=nullable_literal_enums(ops(take(5,DEVICE_TYPE,'<clinit>')),DEVICE_TYPE,selected={'CENTER','GIMBAL'})
    if {n:r['arguments'][2] for n,r in devices.items()}!={'CENTER':5,'GIMBAL':4}:
        raise ValueError('CENTER/GIMBAL enum values changed')
    root_init=take(5,ROOT,'<init>');check_module_default(root_init)
    require(root_init, VERSION+'->Ver1_1 ', '->version ', '->pushSN ')
    require(take(5,CENTER,'getInstance'), CENTER+'-><init>()V')
    if ops(take(5,GIMBAL,'<init>')) != [('invoke-direct','v0, '+ROOT+'-><init>()V'),('return-void','')]:
        raise ValueError('GIMBAL constructor overrides require review')
    for name in ('doPack','getSN','getPushSN','setPushRecData','handleDeviceInfoRequest','handleActivateVerifyInfo'):
        take(5,ROOT,name)
    require(take(5,CALLBACK,'onSuccess'), CENTER+'->getPushSN()', 'CallbackUtils;->onSuccess(')
    for name in ('getSenderIndex',):take(5,CENTER,name)
    sn=take(5,ROOT,'getPushSN');require(sn, ROOT+'->getSN()', 'TextUtils;->isEmpty(', 'String;->equals(', ROOT+'->pushSN ')
    # Branches preserve empty/old cache; this is not unconditional fresh GET SN.
    check_push_sn_choice(sn)
    branches=[(off,branch_target(off,text)) for off,op,text in sn if op.startswith('if-')]
    module_writes=[dict(bank=r['bank'],className=r['className'],method=r['method'],descriptor=r['descriptor'],reference=ref)
                   for r in field_refs for ref in r['references'] if ref['field']=='module_type_' and ref['writesField']]
    if len(module_writes)!=1 or module_writes[0]['className']!=ROOT or module_writes[0]['method']!='<init>':
        raise ValueError('new direct module-type writes require review')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(b):p for b,p in PREFIX_BANKS.items()},
        methods=sorted(methods.values(),key=lambda r:(r['bank'],r['className'],r['method'],r['descriptor'])),
        hg724ClassChain=chain,nearestSerialGetter=resolved,getterAnnotation=annotations[0],
        serialQuerySource=dict(modelClass=CENTER,commandSet=0,commandId=50,receiverType=5,receiverId=7,
            packedReceiverByte=229,senderType=2,requestType='GET',initialSourceVersion='Ver1_1',
            initialSourceGetBodyHex='11',actualSessionVersionVerified=False,sourceTimeoutMs=1000,
            sourceRepeatTimes=3,sourceRetryPolicyCopiedToSdk=False,businessEncryptNo=True,
            finalTransportEncryptionVerified=False,callbackUses='getPushSN',freshResultVerified=False),
        sourceGetPushSn=dict(branches=branches,requiresNonemptyCachedPushToReplace=False,
            emptyCacheCanPopulateFromGetSn=True,nonemptyCacheMaySurviveEmptyGetSn=True,
            helperEmulatesSourceOnly=True,sdkCachePolicyAdded=False),
        activationModuleFieldReferences=sorted(field_refs,key=lambda r:(r['bank'],r['className'],r['method'])),
        directModuleTypeWrites=module_writes,
        sourceDefaultModuleGate=dict(expectedModuleType=8,gimbalDeviceType=4,centerDeviceType=5,
            defaultV13GimbalGate=source_module_gate(8,4,format_name='sourceV13'),
            defaultV14GimbalGate=source_module_gate(8,4,format_name='sourceV14',module_type=4),
            defaultV13CenterGate=source_module_gate(8,5,format_name='sourceV13'),
            runtimeNativeOrReflectionMutationRuledOut=False,firmwareUnsupportedProven=False),
        hg724InheritedSerialSourceRouteEstablished=True,actualHg724RegistryVerified=False,
        targetDeviceVerified=False,javaReflectionExecuted=False,vendorCodeExecuted=False,
        sdkSendAdded=False,sdkReceiveAdded=False,activationOrBindingImplemented=False,
        wholeProtocolRecovered=False,
        remaining=['HG724 nearest inherited serial getter routes CENTER/id7, not generic GIMBAL/id0 activation library.',
                   'Source initial version/GET11 and callback cache behavior are not fresh target-device protocol proof.',
                   'Eight-bank direct field writes establish Java default8 only; native/reflection/runtime mutation unruled out.',
                   'V13/V14 generic parsers are not demonstrated GIMBAL/CENTER firmware support or valid activation.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print('%d methods; %d module-field reference methods; inherited HG724 serial=>CENTER/id7, no sends.'%(len(r['methods']),len(r['activationModuleFieldReferences'])))
if __name__=='__main__':main()
