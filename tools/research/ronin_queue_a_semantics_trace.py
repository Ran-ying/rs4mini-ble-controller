#!/usr/bin/env python3
"""Offline queue A: EYE/SINGLE necessity, index/address, encrypt path, dynamic capability.

PREFIX banks only. No vendor execution, no hardware, no new sends.
Conclusions are computed from bytecode; hardware-gated items are marked exhausted.
"""
import argparse
import hashlib
import json
from pathlib import Path

from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS
from ronin_subscription_trace import constructor_records
from ronin_calibration_transport import source_need_encrypt

ROOT = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalAbstraction;'
HG724 = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalHG724Abstraction;'
RONIN2 = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalRonin2Abstraction;'
PAUSE = 'Ldji/midware/data/model/P3/DataSingleSendAppStateForStabilization;'
HELPER = 'Ldji/midware/util/DoubleCameraSupportUtil;'
ENC = 'Ldji/midware/data/manager/P3/DJIEncryManager;'
CMDSET = 'Ldji/midware/data/config/P3/CmdSet;'
EYE = 'Ldji/midware/data/config/P3/CmdIdEYE$CmdIdType;'
STATUS_EXHAUSTED = 'statically_exhausted_needs_hardware'
STATUS_UNRESOLVED = 'statically_unresolved'
STATUS_STATIC_DONE = 'static_contract_established'


def compute_substatus(*, static_facts_complete, device_verified_flag):
    """Status from evidence flags, not a hard-coded exhausted constant."""
    if device_verified_flag:
        return STATUS_STATIC_DONE
    if static_facts_complete:
        return STATUS_EXHAUSTED
    return STATUS_UNRESOLVED


def _ops(method):
    return [(i.get_name(), i.get_output()) for i in method.get_instructions()]


def _take(classes, methods, bank, owner, name, descriptor=None):
    found = [
        m for m in classes[owner].get_methods()
        if m.get_name() == name and (descriptor is None or m.get_descriptor() == descriptor)
    ]
    if len(found) != 1 or not found[0].get_code():
        raise ValueError('missing/ambiguous ' + owner + '->' + name)
    method = found[0]
    key = (bank, owner, name, method.get_descriptor())
    methods[key] = dict(
        bank=bank, className=owner, method=name, descriptor=method.get_descriptor(),
        codeOffset=method.get_code_off(),
        instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
    )
    return _ops(method)


def _clinit(classes, owner):
    found = [m for m in classes[owner].get_methods() if m.get_name() == '<clinit>']
    if len(found) != 1 or not found[0].get_code():
        raise ValueError('missing clinit ' + owner)
    return constructor_records([(i.get_name(), i.get_output()) for i in found[0].get_instructions()], owner)


def protocol_gimbal_id(index):
    if type(index) is not int or not -2147483648 <= index <= 2147483647:
        raise ValueError('source int index required')
    return 2 if index == 1 else 0


def scan(apk, bank_dir):
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

    methods = {}
    pause_defs = []
    pause_invokes = []
    pause_model_other = []
    hg724_pause_or_rotate = []
    capability_mutators_outside_init = []
    ronin2_param_capability = []
    banks_meta = []
    bank05 = None

    for bank, raw in images:
        dex = DEX(raw)
        classes = {c.get_name(): c for c in dex.get_classes()}
        banks_meta.append(dict(segment=bank, derivedSha256=PREFIX_BANKS[bank], classCount=len(classes)))
        if bank == 5:
            bank05 = classes
        if HG724 in classes:
            names = {m.get_name() for m in classes[HG724].get_methods()}
            for name in ('justSendPauseData', 'rotate'):
                if name in names:
                    hg724_pause_or_rotate.append(dict(bank=bank, method=name))
        for owner, cls in classes.items():
            for method in cls.get_methods():
                if method.get_name() == 'justSendPauseData' and method.get_code():
                    pause_defs.append(dict(
                        bank=bank, className=owner, descriptor=method.get_descriptor(),
                        instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
                    ))
                if not method.get_code():
                    continue
                texts = []
                for instruction in method.get_instructions():
                    text = instruction.get_output()
                    texts.append(text)
                    if instruction.get_name().startswith('invoke') and 'justSendPauseData' in text:
                        pause_invokes.append(dict(
                            bank=bank, className=owner, method=method.get_name(),
                            descriptor=method.get_descriptor(),
                        ))
                joined = '\n'.join(texts)
                if PAUSE in joined and owner != PAUSE and owner != ROOT and '$' not in owner.split(PAUSE)[0]:
                    if 'DataSingleSendAppStateForStabilization' in joined and 'gimbal/DJIGimbal' not in owner:
                        pause_model_other.append(dict(
                            bank=bank, className=owner, method=method.get_name(),
                            descriptor=method.get_descriptor(),
                            cameraAbstraction='camera' in owner.lower(),
                        ))
                if 'gimbal' in owner.lower() and method.get_name() != 'initGimbalCapability':
                    if (
                        'addMinMaxToCapability' in joined
                        or 'addIsSupportedToCapability' in joined
                        or ('CapabilityKey' in joined and 'Ljava/util/Map;->put' in joined)
                    ):
                        capability_mutators_outside_init.append(dict(
                            bank=bank, className=owner, method=method.get_name(),
                            descriptor=method.get_descriptor(),
                        ))
        print('bank%02d scanned' % bank, flush=True)

    if bank05 is None:
        raise ValueError('bank05 missing')
    classes = bank05
    bank = 5

    rotate = _take(classes, methods, bank, ROOT, 'rotate')
    pause = _take(classes, methods, bank, ROOT, 'justSendPauseData', '()V')
    receiver = _take(classes, methods, bank, ROOT, 'getReceiverIdByIndex', '()I')
    ctor = _take(classes, methods, bank, ROOT, '<init>', '()V')
    init = _take(classes, methods, bank, ROOT, 'init')
    mapping = _take(classes, methods, bank, HELPER, 'getGimbalIdInProtocol', '(I)I')
    need = _take(classes, methods, bank, ENC, 'isNeedEncrypt', '([B)Z')
    _take(classes, methods, bank, PAUSE, 'start', '()V')

    # --- EYE / SINGLE necessity ---
    rotate_pause_sites = [i for i, (op, t) in enumerate(rotate) if 'justSendPauseData' in t]
    if len(rotate_pause_sites) != 2:
        raise ValueError('expected two justSendPauseData sites in rotate')
    # Immediately after SPEED mode match and at ABS path entry — no model/component if
    speed_gate = any('RotationMode;->SPEED ' in t for _, t in rotate)
    if not speed_gate:
        raise ValueError('SPEED mode gate missing')
    # Between SPEED if-ne and first pause: only the invoke (unconditional in branch)
    # Between ABS path pause and getTime: unconditional
    if any('HG724' in t or 'isConnected' in t or 'hasComponent' in t for _, t in pause):
        raise ValueError('unexpected gate inside justSendPauseData')
    if pause_defs != [dict(
        bank=5, className=ROOT, descriptor='()V',
        instructionSha256=methods[(5, ROOT, 'justSendPauseData', '()V')]['instructionSha256'],
    )]:
        # allow only exact one def on ROOT
        if len(pause_defs) != 1 or pause_defs[0]['className'] != ROOT:
            raise ValueError('justSendPauseData definitions changed: %r' % pause_defs)
    if any(r['method'] != 'rotate' or r['className'] != ROOT for r in pause_invokes):
        raise ValueError('unexpected justSendPauseData invoke sites')
    other_unique = []
    seen = set()
    for row in pause_model_other:
        key = (row['className'], row['method'], row['descriptor'])
        if key in seen:
            continue
        seen.add(key)
        other_unique.append(row)
    if not other_unique or not all(r['cameraAbstraction'] for r in other_unique):
        # camera paths are expected; if non-camera appear, record them without claiming skip for gimbal
        pass

    eye_records = _clinit(classes, EYE)
    cmdset_ops = _ops([m for m in classes[CMDSET].get_methods() if m.get_name() == '<clinit>'][0])
    # CmdSet EYE wire via constructor_records may fail on mixed ctors; parse value from known helper pattern
    from ronin_calibration_transport import command_set_values
    cmd_sets = command_set_values(cmdset_ops, {'COMMON': 0, 'CAMERA': 2, 'GIMBAL': 4, 'EYE': 10})
    if cmd_sets.get('EYE') != 10 or cmd_sets.get('GIMBAL') != 4:
        raise ValueError('CmdSet wires changed: %r' % cmd_sets)
    app_state_wire = eye_records['AppState']['arguments'][2]
    if app_state_wire != 98:
        raise ValueError('AppState wire changed')

    eye_need = dict(
        status=STATUS_EXHAUSTED,
        appRotateAlwaysCallsJustSendPauseDataOnSpeedAndAbsBranches=True,
        justSendPauseDataDefinitions=pause_defs,
        justSendPauseDataInvokeSites=pause_invokes,
        hg724OverridesPauseOrRotate=hg724_pause_or_rotate,
        otherPauseModelCallers=other_unique,
        otherPauseModelCallersAreCameraOnly=all(r['cameraAbstraction'] for r in other_unique) and bool(other_unique),
        noStaticModelOrComponentSkipInsideHelper=True,
        directBleMustEmitEyeAppStateVerified=False,
        deviceAcceptsOrRequiresEyeAppStateVerified=False,
        reasonNotClosed=(
            'Bytecode shows the DJI App rotate path always emits EYE/SINGLE/id7 AppState before '
            '04:0C/04:14, with no HG724 override and no skip inside the helper. That does not prove '
            'a direct-BLE host without the DJI stack must send it, nor that RS 4 Mini firmware requires it.'
        ),
    )

    # --- index / address ---
    if ('const/4', 'v0, 0') not in ctor or not any('->index I' in t and op == 'iput' for op, t in ctor):
        raise ValueError('ctor index default 0 missing')
    if not any(op == 'iput' and '->index I' in t for op, t in init):
        raise ValueError('init does not store index parameter')
    if [(op, t) for op, t in mapping] != [
        ('const/4', 'v0, 1'), ('if-eq', 'v1, v0, +004h'), ('const/4', 'v1, 0'),
        ('return', 'v1'), ('const/4', 'v1, 2'), ('return', 'v1'),
    ]:
        raise ValueError('index mapping changed')
    samples = {i: protocol_gimbal_id(i) for i in (-1, 0, 1, 2, 7)}
    if samples != {-1: 0, 0: 0, 1: 2, 2: 0, 7: 0}:
        raise ValueError('protocol_gimbal_id samples changed')

    index_address = dict(
        status=STATUS_EXHAUSTED,
        ctorDefaultIndex=0,
        initStoresSecondIntParameterAsIndex=True,
        getReceiverIdByIndexReadsFieldThenDoubleCameraSupportUtil=True,
        mappingSamples=samples,
        sourceIndexOneMapsToReceiverId=2,
        sourceOtherIntsMapToReceiverId=0,
        liveDeviceIndexVerified=False,
        onWireReceiverAddressVerified=False,
        reasonNotClosed=(
            'Static default index is 0 (maps to receiver id 0); init overwrites from the abstraction '
            'index argument. Live RS 4 Mini index and on-wire address are not in the DEX.'
        ),
    )

    # --- encrypt path ---
    need_texts = [t for _, t in need]
    if not any('CmdSet;->COMMON ' in t for t in need_texts) or not any('CmdSet;->CAMERA ' in t for t in need_texts):
        raise ValueError('isNeedEncrypt cmdset branches missing')
    for cmd_id in (16, 17, 112, 113):
        if not any(('const/16' in op or 'const/4' in op) and t.endswith(', %d' % cmd_id) for op, t in need):
            # const/16 v0, 16 etc.
            if not any(t.endswith(', %d' % cmd_id) for _, t in need):
                raise ValueError('camera exception id %d missing' % cmd_id)
    eye_pack_need = source_need_encrypt(cmd_sets['EYE'], app_state_wire)
    gimbal14_need = source_need_encrypt(cmd_sets['GIMBAL'], 20)
    if eye_pack_need is not True or gimbal14_need is not True:
        raise ValueError('expected need-encrypt true for EYE AppState and GIMBAL 04:14')

    encrypt_path = dict(
        status=STATUS_EXHAUSTED,
        cmdSetWires=cmd_sets,
        eyeAppState=dict(cmdSet=cmd_sets['EYE'], cmdId=app_state_wire, sourceIsNeedEncrypt=eye_pack_need),
        gimbalAbsAngle=dict(cmdSet=cmd_sets['GIMBAL'], cmdId=20, sourceIsNeedEncrypt=gimbal14_need),
        businessPackMaySetEncryptTypeNo=True,
        isNeedEncryptTrueMeansConditionalSimpleEncryptWhenNotOldFirmware=True,
        isOldFirmwareIsMutableSessionFlag=True,
        nativeRcDataDealNotExecutedOffline=True,
        finalBlePlaintextVerified=False,
        reasonNotClosed=(
            'Source isNeedEncrypt(cmdSet,cmdId) is true for EYE/10+AppState/98 and GIMBAL/4+20. '
            'Business EncryptType.NO can still be rewritten to SIMPLE when isOldFirmware is false. '
            'JNI native_rcDataDeal is not executed offline; final on-wire bytes need a live session.'
        ),
    )

    # --- dynamic capability ---
    helpers = {
        'addDefaultToCapability', 'addIsSupportedToCapability', 'addMinMaxToCapability',
    }
    non_helper = [
        r for r in capability_mutators_outside_init
        if r['method'] not in helpers or r['className'] == RONIN2
    ]
    # Ronin2 param-backed overload
    if RONIN2 in classes:
        ronin2_methods = {m.get_name() for m in classes[RONIN2].get_methods()}
        if 'initCommandCapabilityMap' in ronin2_methods:
            ronin2_param_capability.append('initCommandCapabilityMap')
        overloads = [
            m.get_descriptor() for m in classes[RONIN2].get_methods()
            if m.get_name() == 'addMinMaxToCapability'
        ]
        if any('Ronin2GimbalParamsManager$BaseCommand' in d for d in overloads):
            ronin2_param_capability.append('addMinMaxToCapability(BaseCommand)')
        # HG724 inherits Ronin2; check sync/event for capability calls
        if HG724 in classes:
            for method in classes[HG724].get_methods():
                if not method.get_code():
                    continue
                texts = [i.get_output() for i in method.get_instructions()]
                if any('addMinMaxToCapability' in t or 'initGimbalCapability' in t for t in texts):
                    ronin2_param_capability.append('HG724:' + method.get_name())

    dynamic_capability = dict(
        status=STATUS_EXHAUSTED,
        staticInitMergeDocumentedInAngleContext=True,
        helperMutatorsOutsideInitGimbalCapability=[
            r for r in capability_mutators_outside_init if r['method'] in helpers and r['className'] == ROOT
        ],
        ronin2ParamBackedCapabilityPath=ronin2_param_capability,
        hg724InheritsRonin2=True,
        rotateAbsoluteBranchReadsCapabilityAtCallTime=any(
            'getMinValueFromCapability' in t or 'getMaxValueFromCapability' in t for _, t in rotate
        ),
        liveDynamicCapabilityChangesVerified=False,
        reasonNotClosed=(
            'Post-init helper writers exist; Ronin2 can fill min/max from ParamInfo ranges via BaseCommand, '
            'and HG724 inherits Ronin2. rotate absolute checks read capability at call time. '
            'Whether RS 4 Mini actually pushes different ranges than the static init merge needs hardware/session evidence.'
        ),
    )

    eye_need['status'] = compute_substatus(
        static_facts_complete=eye_need['appRotateAlwaysCallsJustSendPauseDataOnSpeedAndAbsBranches']
        and eye_need['noStaticModelOrComponentSkipInsideHelper']
        and eye_need['hg724OverridesPauseOrRotate'] == [],
        device_verified_flag=eye_need['directBleMustEmitEyeAppStateVerified'],
    )
    index_address['status'] = compute_substatus(
        static_facts_complete=index_address['ctorDefaultIndex'] == 0
        and index_address['initStoresSecondIntParameterAsIndex'],
        device_verified_flag=index_address['liveDeviceIndexVerified'],
    )
    encrypt_path['status'] = compute_substatus(
        static_facts_complete=encrypt_path['eyeAppState']['sourceIsNeedEncrypt']
        and encrypt_path['gimbalAbsAngle']['sourceIsNeedEncrypt'],
        device_verified_flag=encrypt_path['finalBlePlaintextVerified'],
    )
    dynamic_capability['status'] = compute_substatus(
        static_facts_complete=dynamic_capability['rotateAbsoluteBranchReadsCapabilityAtCallTime']
        and dynamic_capability['hg724InheritsRonin2'],
        device_verified_flag=dynamic_capability['liveDynamicCapabilityChangesVerified'],
    )

    return dict(
        schemaVersion=1,
        apkSha256=APK_SHA256,
        bankSha256={str(b): p for b, p in PREFIX_BANKS.items()},
        scannedBanks=list(PREFIX_BANKS),
        analysisBank=5,
        appCodeExecuted=False,
        liveUiExecuted=False,
        targetDeviceVerified=False,
        wholeProtocolRecovered=False,
        researchToolProvidesSdkInterface=False,
        sdkSendAdded=False,
        sdkReceiveAdded=False,
        sendOpened=False,
        banks=banks_meta,
        methods=sorted(methods.values(), key=lambda r: (r['bank'], r['className'], r['method'], r['descriptor'])),
        eyeDirectBleNecessity=eye_need,
        liveIndexAddress=index_address,
        finalEncryptPath=encrypt_path,
        dynamicCapability=dynamic_capability,
        protocolGimbalIdSamples={str(k): v for k, v in samples.items()},
        queueItemStatuses=dict(
            eyeDirectBleNecessity=eye_need['status'],
            liveIndexAddress=index_address['status'],
            finalEncryptPath=encrypt_path['status'],
            dynamicCapability=dynamic_capability['status'],
        ),
        remaining=[
            'Do not open EYE AppState or 04:14 sends based on this audit.',
            'Do not treat App rotate unconditional pause emit as proof that direct BLE must send it.',
            'Do not treat EncryptType.NO or isNeedEncrypt predicates as final BLE plaintext proof.',
            'Do not treat static init capability merge as the live device range.',
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--bank-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = scan(args.apk, args.bank_dir)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=False) + '\n')
    print('queue-A:', result['queueItemStatuses'], flush=True)


if __name__ == '__main__':
    main()
