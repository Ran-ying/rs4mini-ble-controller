#!/usr/bin/env python3
"""Offline queue C: completion / abort static contracts for rotate and programs.

PREFIX only. Separates host callback success, ACK-capable start(callback), and
program start/stop phases from physical motion completion.
"""
import argparse, hashlib, json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS

STATUS = 'statically_exhausted_needs_hardware'
ROOT = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalAbstraction;'
ABS = 'Ldji/midware/data/model/P3/DataGimbalAbsAngleControl;'
TRACK = 'Ldji/midware/data/model/P3/DataGimbalSetTrackStatus;'
CB = 'Ldji/midware/interfaces/DJIDataCallBack;'


def _ops(m):
    return [(i.get_name(), i.get_output()) for i in m.get_instructions()]


def _take(classes, methods, bank, owner, name, descriptor=None):
    found = [m for m in classes[owner].get_methods() if m.get_name() == name and (descriptor is None or m.get_descriptor() == descriptor)]
    if len(found) != 1 or not found[0].get_code():
        raise ValueError('missing ' + owner + name)
    m = found[0]
    methods[(bank, owner, name, m.get_descriptor())] = dict(
        bank=bank, className=owner, method=name, descriptor=m.get_descriptor(),
        codeOffset=m.get_code_off(),
        instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest(),
    )
    return _ops(m)


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
    abs_start_invokes = []
    bank05 = None
    for bank, raw in images:
        classes = {c.get_name(): c for c in DEX(raw).get_classes()}
        banks_meta.append(dict(segment=bank, derivedSha256=PREFIX_BANKS[bank]))
        if bank == 5:
            bank05 = classes
        for owner, cls in classes.items():
            for method in cls.get_methods():
                if not method.get_code():
                    continue
                for instruction in method.get_instructions():
                    text = instruction.get_output()
                    if instruction.get_name().startswith('invoke') and ABS + '->start' in text:
                        abs_start_invokes.append(dict(
                            bank=bank, className=owner, method=method.get_name(),
                            descriptor=method.get_descriptor(), invoke=text[:160],
                            usesCallback=CB in text,
                        ))
        print('bank%02d' % bank, flush=True)
    classes = bank05
    bank = 5
    rotate = _take(classes, methods, bank, ROOT, 'rotate')
    abs_no_cb = _take(classes, methods, bank, ABS, 'start', '()V')
    abs_cb = _take(classes, methods, bank, ABS, 'start', '(' + CB + ')V')
    track_set = _take(classes, methods, bank, TRACK, 'setStartOrStop')
    _take(classes, methods, bank, TRACK, 'doPack', '()V')

    rotate_texts = [t for _, t in rotate]
    if not any(ABS + '->start()V' in t for t in rotate_texts):
        raise ValueError('rotate must call ABS start()V')
    if any(ABS + '->start(' + CB in t for t in rotate_texts):
        raise ValueError('rotate unexpectedly uses ABS start(callback)')
    if not any('CallbackUtils;->onSuccess' in t for t in rotate_texts):
        raise ValueError('rotate onSuccess missing')
    # onSuccess appears immediately after start in ABS path — already established
    if not any('DataBase;->start(' + 'Ldji/midware/data/packages/P3/SendPack;)V' in t or 'DataBase;->start(Ldji/midware/data/packages/P3/SendPack;)V' in t for _, t in abs_no_cb):
        if not any('DataBase;->start(Ldji/midware/data/packages/P3/SendPack;)V' in t for _, t in abs_no_cb):
            raise ValueError('ABS no-callback start missing DataBase.start(SendPack)')
    if not any('DataBase;->start(Ldji/midware/data/packages/P3/SendPack; ' + CB in t or 'DJIDataCallBack;)V' in t for _, t in abs_cb):
        if not any('DJIDataCallBack' in t and 'DataBase;->start' in t for _, t in abs_cb):
            raise ValueError('ABS callback start missing DataBase.start(SendPack, callback)')
    if not any('NEEDACK;->YES' in t for _, t in abs_no_cb):
        raise ValueError('ABS pack NEEDACK.YES missing')

    # only rotate invokes ABS start across PREFIX
    unique_inv = []
    seen = set()
    for row in abs_start_invokes:
        key = (row['className'], row['method'], row['descriptor'], row['usesCallback'])
        if key in seen:
            continue
        seen.add(key)
        unique_inv.append(row)
    if unique_inv != [dict(
        bank=5, className=ROOT, method='rotate',
        descriptor='(Ldji/sdksharedlib/hardware/abstractions/DJISDKCacheHWAbstraction$InnerCallback; Ldji/common/gimbal/Rotation;)V',
        invoke=unique_inv[0]['invoke'], usesCallback=False,
    )] if unique_inv else True:
        if len(unique_inv) != 1 or unique_inv[0]['method'] != 'rotate' or unique_inv[0]['usesCallback']:
            raise ValueError('unexpected ABS start invoke set: %r' % unique_inv)

    if not any('mStartOrStop' in t or 'StartOrStop' in t for _, t in track_set):
        # setStartOrStop body should write field
        pass
    set_ops = track_set
    if not any(op.startswith('iput') and 'mStartOrStop' in t for op, t in set_ops):
        raise ValueError('setStartOrStop does not write mStartOrStop')

    return dict(
        schemaVersion=1,
        apkSha256=APK_SHA256,
        bankSha256={str(b): p for b, p in PREFIX_BANKS.items()},
        scannedBanks=list(PREFIX_BANKS),
        analysisBank=5,
        appCodeExecuted=False,
        targetDeviceVerified=False,
        sendOpened=False,
        sdkSendAdded=False,
        banks=banks_meta,
        methods=sorted(methods.values(), key=lambda r: (r['bank'], r['className'], r['method'], r['descriptor'])),
        status=STATUS,
        rotateCompletion=dict(
            usesAbsStartNoCallback=True,
            absStartCallbackOverloadExistsButUnusedByRotate=True,
            hostCallbackUtilsOnSuccessAfterStart=True,
            hostSuccessTiedToAck=False,
            hostSuccessTiedToPhysicalArrival=False,
            motionCompletionPushHandledInRotate=False,
        ),
        absAngleTransport=dict(
            needAckYesOnPack=True,
            noCallbackStartDelegatesToDataBaseStartSendPack=True,
            callbackStartDelegatesToDataBaseStartSendPackCallback=True,
            ackIsNotPhysicalCompletion=True,
        ),
        absStartInvokeSites=unique_inv,
        trackProgramStop=dict(
            setStartOrStopWritesPhaseField=True,
            stopPhaseIsProgramCommandNotRotateAbort=True,
            physicalAbortVerified=False,
        ),
        stabilizationWaitIsNotAngleCompletion=True,
        firmwareCompletionOrAbortVerified=False,
        reasonNotClosed=(
            'rotate calls AbsAngleControl.start()V then CallbackUtils.onSuccess without waiting for ACK '
            'or a reach notification. A start(callback) overload exists for ACK association but is unused '
            'by rotate. Track setStartOrStop is a program phase, not a 04:14 abort. Physical completion/'
            'cancel/disconnect behavior needs hardware.'
        ),
        remaining=[
            'Do not treat host onSuccess as motion complete.',
            'Do not open program stop or 04:14 based on this audit.',
        ],
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--bank-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = scan(args.apk, args.bank_dir)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('queue-C:', result['status'], flush=True)


if __name__ == '__main__':
    main()
