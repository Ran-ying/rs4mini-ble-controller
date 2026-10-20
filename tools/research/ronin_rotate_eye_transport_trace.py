#!/usr/bin/env python3
"""PREFIX end-to-end static trace: 04:14 rotate → justSendPauseData/EYE → transport.

Offline only. Does not open sends, run vendor code, or touch hardware.
Separates bytecode-proven facts from items that still need hardware confirmation.
"""
import argparse
import hashlib
import json
from pathlib import Path

from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS
from ronin_subscription_trace import constructor_records

ROOT = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalAbstraction;'
HG724 = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalHG724Abstraction;'
ABS = 'Ldji/midware/data/model/P3/DataGimbalAbsAngleControl;'
SPEED = 'Ldji/midware/data/model/P3/DataGimbalSpeedControl;'
PAUSE = 'Ldji/midware/data/model/P3/DataSingleSendAppStateForStabilization;'
DB = 'Ldji/midware/data/manager/P3/DataBase;'
PACK = 'Ldji/midware/data/packages/P3/SendPack;'
EYE = 'Ldji/midware/data/config/P3/CmdIdEYE$CmdIdType;'
DEVICE = 'Ldji/midware/data/config/P3/DeviceType;'
GIMBAL_CMD = 'Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;'
HELPER = 'Ldji/midware/util/DoubleCameraSupportUtil;'


def _ops(method):
    rows = []
    off = 0
    for instruction in method.get_instructions():
        rows.append((off, instruction.get_name(), instruction.get_output()))
        off += instruction.get_length()
    return rows


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
        bank=bank,
        className=owner,
        method=name,
        descriptor=method.get_descriptor(),
        codeOffset=method.get_code_off(),
        instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
    )
    return _ops(method)


def _clinit_records(classes, owner):
    found = [m for m in classes[owner].get_methods() if m.get_name() == '<clinit>']
    if len(found) != 1 or not found[0].get_code():
        raise ValueError('missing clinit ' + owner)
    ops = [(i.get_name(), i.get_output()) for i in found[0].get_instructions()]
    return constructor_records(ops, owner)


def _require(rows, token):
    if not any(token in text for _, _, text in rows):
        raise ValueError('missing token ' + token)


def _texts(rows):
    return [text for _, _, text in rows]


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
    banks_meta = []
    hg724_rotate = []
    bank05_classes = None

    for bank, raw in images:
        dex = DEX(raw)
        classes = {c.get_name(): c for c in dex.get_classes()}
        coded = sum(1 for c in classes.values() for m in c.get_methods() if m.get_code())
        total = sum(1 for c in classes.values() for _ in c.get_methods())
        banks_meta.append(dict(
            segment=bank,
            derivedSha256=PREFIX_BANKS[bank],
            methodCount=total,
            methodWithCodeCount=coded,
            hasRotateRoot=ROOT in classes,
            hasPauseModel=PAUSE in classes,
            hasAbsAngle=ABS in classes,
        ))
        if HG724 in classes:
            names = {m.get_name() for m in classes[HG724].get_methods()}
            if 'rotate' in names:
                hg724_rotate.append(dict(bank=bank, method='rotate'))
        if bank == 5:
            bank05_classes = classes
        print('bank%02d: methods=%d coded=%d' % (bank, total, coded), flush=True)

    if bank05_classes is None:
        raise ValueError('bank05 missing')
    classes = bank05_classes
    bank = 5

    rotate = _take(classes, methods, bank, ROOT, 'rotate')
    pause_helper = _take(classes, methods, bank, ROOT, 'justSendPauseData', '()V')
    receiver = _take(classes, methods, bank, ROOT, 'getReceiverIdByIndex', '()I')
    pause_dopack = _take(classes, methods, bank, PAUSE, 'doPack', '()V')
    pause_start = _take(classes, methods, bank, PAUSE, 'start', '()V')
    abs_dopack = _take(classes, methods, bank, ABS, 'doPack', '()V')
    db_start_pack = _take(classes, methods, bank, DB, 'start', '(' + PACK + ')V')
    preprocess = _take(classes, methods, bank, DB, 'preprocessPack', '(' + PACK + ')' + PACK)
    mapping = _take(classes, methods, bank, HELPER, 'getGimbalIdInProtocol', '(I)I')

    rotate_texts = _texts(rotate)
    pause_helper_texts = _texts(pause_helper)
    pause_start_texts = _texts(pause_start)

    if sum(1 for text in pause_helper_texts if PAUSE + '->start()V' in text) != 1:
        raise ValueError('justSendPauseData start path changed')
    if not any(PAUSE[:-1] + '$GimbalState;->START ' in t for t in pause_helper_texts):
        raise ValueError('justSendPauseData START state missing')
    if any('DJIDataCallBack' in t for t in pause_helper_texts):
        raise ValueError('justSendPauseData unexpectedly uses callback start')

    _require(pause_start, 'DeviceType;->SINGLE ')
    _require(pause_start, 'CmdSet;->EYE ')
    _require(pause_start, 'CmdIdEYE$CmdIdType;->AppState ')
    _require(pause_start, 'EncryptType;->NO ')
    _require(pause_start, 'NEEDACK;->YES ')
    if not any(op == 'const/4' and t.endswith(', 7') for _, op, t in pause_start):
        raise ValueError('pause start receiverId literal 7 missing')
    if not any(PACK + '->receiverId I' in t for t in pause_start_texts):
        raise ValueError('pause start receiverId field missing')
    if not any(PAUSE + '->start(' + PACK + ')V' in t for t in pause_start_texts):
        raise ValueError('pause start does not delegate to DataBase.start(SendPack)')

    eye = _clinit_records(classes, EYE)
    device = _clinit_records(classes, DEVICE)
    gimbal = _clinit_records(classes, GIMBAL_CMD)
    app_state = eye['AppState']['arguments']
    single = device['SINGLE']['arguments']
    app = device['APP']['arguments']
    abs_cmd = None
    for name, rec in gimbal.items():
        args = rec.get('arguments') or []
        if len(args) >= 3 and args[2] == 20:
            abs_cmd = dict(name=name, ordinal=args[1], wire=args[2], record=rec)
            break
    if abs_cmd is None:
        raise ValueError('CmdIdGimbal wire 20 (04:14) missing')
    if app_state[2] != 98 or single[2] != 17:
        raise ValueError('EYE AppState / DeviceType.SINGLE wire changed')

    # rotate control-flow facts (ABS / 04:14 branch)
    just_pause_sites = [off for off, _, t in rotate if 'justSendPauseData' in t]
    abs_start_sites = [off for off, _, t in rotate if ABS + '->start()V' in t]
    speed_start_sites = [off for off, _, t in rotate if SPEED + '->start()V' in t]
    success_sites = [off for off, _, t in rotate if 'CallbackUtils;->onSuccess' in t]
    fail_sites = [off for off, _, t in rotate if 'onFails' in t or 'onFailure' in t]
    if len(just_pause_sites) != 2:
        raise ValueError('expected justSendPauseData at SPEED and ABS entries')
    if len(abs_start_sites) != 1 or len(speed_start_sites) != 1:
        raise ValueError('expected one SPEED and one ABS start()V in rotate')
    if len(success_sites) != 2:
        raise ValueError('expected onSuccess after each branch start')
    # ABS path: setReceiverId(getReceiverIdByIndex) then start then onSuccess — no wait
    abs_tail = [t for _, _, t in rotate if 'AbsAngleControl' in t or 'getReceiverIdByIndex' in t or 'CallbackUtils;->onSuccess' in t]
    if not any(ABS + '->setReceiverId(I)' in t for t in rotate_texts):
        raise ValueError('ABS setReceiverId missing')
    if not any('getReceiverIdByIndex' in t for t in rotate_texts):
        raise ValueError('getReceiverIdByIndex missing on rotate')

    # index mapping: index==1 → 2 else 0
    map_ops = [(op, t) for _, op, t in mapping]
    if map_ops != [
        ('const/4', 'v0, 1'),
        ('if-eq', 'v1, v0, +004h'),
        ('const/4', 'v1, 0'),
        ('return', 'v1'),
        ('const/4', 'v1, 2'),
        ('return', 'v1'),
    ]:
        raise ValueError('getGimbalIdInProtocol mapping changed')

    _require(preprocess, PACK + '->receiverId I')
    _require(db_start_pack, 'preprocessPack')
    # Encrypt.NO on pause pack is a pack field, not proof of final BLE plaintext
    encrypt_notes = dict(
        pauseStartSetsEncryptTypeNo=any('EncryptType;->NO ' in t for t in pause_start_texts),
        encryptTypeNoDoesNotProveFinalBlePlaintext=True,
        encryptionPathAudited=False,
    )

    pause_body = dict(
        bodyBytes=2,
        byte0='gimbalState.value() narrowed to byte',
        byte1='cameraState.value() narrowed to byte',
        rotateUsesGimbalStateStart=True,
        startEnumName='START',
        startDoesNotProvePhysicalPause=True,
        sourceNoCallbackBodyWhenStartAndCameraNormal='0100',
        note='defaults NORMAL/NORMAL; rotate sets gimbal START before no-callback start; camera left default',
    )
    _require(pause_dopack, 'gimbalState')
    _require(pause_dopack, 'cameraState')

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
        hg724OverridesRotate=hg724_rotate,
        chain=dict(
            entry=dict(
                className=ROOT,
                method='rotate',
                inheritedByHg724WithoutOverride=hg724_rotate == [],
                note='HG724 inherits base rotate; missing HG724-named override is not proof of no inherited business entry',
            ),
            pauseGate=dict(
                helper='justSendPauseData',
                calledBeforeSpeedAndAbsPacks=True,
                sitesCodeUnits=just_pause_sites,
                createsFreshPauseObject=True,
                setsGimbalStateStart=True,
                invokesNoCallbackStart=True,
                waitsForBusinessAckBeforeAngleRequest=False,
            ),
            eyeTransport=dict(
                modelClass=PAUSE,
                senderTypeName='APP',
                senderTypeWire=app[2],
                receiverTypeName='SINGLE',
                receiverTypeWire=single[2],
                receiverIdLiteral=7,
                cmdSetName='EYE',
                cmdIdName='AppState',
                cmdIdWire=app_state[2],
                cmdIdOrdinal=app_state[1],
                needAckYes=True,
                encryptTypeNoOnPack=True,
                delegatesToDataBaseStartSendPack=True,
                notGimbalCommandSet=True,
                notCommand04_62Or04_60=True,
                body=pause_body,
            ),
            angle14=dict(
                key='04:14',
                modelClass=ABS,
                cmdIdName=abs_cmd['name'],
                cmdIdWire=abs_cmd['wire'],
                cmdIdOrdinal=abs_cmd['ordinal'],
                setsReceiverIdFromGetReceiverIdByIndex=True,
                invokesNoCallbackStart=True,
                thenCallbackUtilsOnSuccessImmediately=True,
                onSuccessDoesNotWaitForAckOrMotionComplete=True,
                absStartCodeUnit=abs_start_sites[0],
                onSuccessCodeUnits=success_sites,
            ),
            speed0cParallel=dict(
                key='04:0C',
                note='SPEED branch also calls justSendPauseData then SpeedControl.start then onSuccess; not the 04:14 focus of this trace',
                speedStartCodeUnit=speed_start_sites[0],
            ),
            receiverIndex=dict(
                getReceiverIdByIndexUsesDoubleCameraSupportUtil=True,
                sourceIndexOneMapsToId=2,
                sourceOtherIntIndexesMapToId=0,
                preprocessPackOverridesSendPackReceiverIdUnlessMinusOne=True,
                liveDeviceIndexVerified=False,
                bleAddressVerified=False,
            ),
            returnPath=dict(
                earlyFailuresUseCallbackUtilsOnFailureOrOnFails=True,
                failureSiteCount=len(fail_sites),
                successSiteCount=len(success_sites),
                successMeansHostCallbackFiredAfterStartInvocation=True,
                successDoesNotMeanAckAccepted=True,
                successDoesNotMeanPhysicalMotionComplete=True,
                completionOrAbortNotificationInThisMethod=False,
            ),
            encrypt=encrypt_notes,
        ),
        staticallyEstablished=[
            'Base rotate is the inherited 04:14 entry for HG724; no HG724 rotate override in PREFIX scan.',
            'Both SPEED and ABS branches call justSendPauseData before packing their gimbal command.',
            'justSendPauseData → DataSingleSendAppStateForStabilization with GimbalState.START → no-callback start().',
            'That start builds SendPack: APP→SINGLE id7, CmdSet EYE, CmdId AppState (wire 98), NEEDACK YES, EncryptType NO, then DataBase.start(SendPack).',
            'Pause doPack is 2 bytes: gimbalState byte, cameraState byte; START+default camera yields source body 0100.',
            'ABS path: setReceiverId(getReceiverIdByIndex()) → AbsAngleControl.start() → CallbackUtils.onSuccess; no wait for ACK or motion done.',
            'Index mapping source: index==1 → receiver id 2, else 0; preprocessPack can override pack receiverId when stored id != -1.',
        ],
        needsHardwareOrLiveSession=[
            'Whether RS 4 Mini / direct BLE must emit the EYE/SINGLE/id7 AppState pause message at all.',
            'Live gimbal index and on-wire receiver address for 04:14.',
            'Whether EncryptType.NO remains plaintext on the final BLE path.',
            'ACK acceptance, error ccode, completion, cancel/abort, and physical motion for 04:14.',
            'Resume / un-pause protocol after AppState START, if any.',
            'Dynamic capability map changes after initGimbalCapability.',
            'Reference frame of absolute angles vs host joint/attitude feedback.',
        ],
        remaining=[
            'Do not open 04:14 or EYE AppState sends under current gates.',
            'Do not treat host onSuccess as firmware ACK or physical completion.',
            'Do not treat missing HG724-named rotate as absence of inherited entry.',
            'CameraState field stays recorded as pack layout only; no camera API added.',
        ],
        relatedPriorEvidence=[
            'tools/research/ANGLE_CONTEXT.md',
            'tools/research/STABILIZATION_DEPENDENCY.md',
            'tools/research/MOTION_PREFIX.md',
            'tools/research/ANGLES.md',
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
    print(
        'rotate→EYE→transport: pause sites=%d; abs start@%d; sendOpened=%s'
        % (
            len(result['chain']['pauseGate']['sitesCodeUnits']),
            result['chain']['angle14']['absStartCodeUnit'],
            result['sendOpened'],
        ),
        flush=True,
    )


if __name__ == '__main__':
    main()
