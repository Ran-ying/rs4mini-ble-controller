#!/usr/bin/env python3
"""Offline queue B: reference-frame static bindings (ActualPose / MotorAngle / 04:05 / 04:14).

PREFIX only. Does not claim physical frame identity. No sends / vendor exec / hardware.
"""
import argparse
import hashlib
import json
from pathlib import Path

from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS
from ronin_subscription_trace import constructor_records

STATUS_EXHAUSTED = 'statically_exhausted_needs_hardware'
STATUS = STATUS_EXHAUSTED  # compat for tests expecting exhausted outcome when facts hold
STATUS_UNRESOLVED = 'statically_unresolved'


def compute_status(*, distinct_tags, no_bytecode_equality, physical_verified):
    if physical_verified:
        return 'device_verified'
    if distinct_tags and no_bytecode_equality:
        return STATUS_EXHAUSTED
    return STATUS_UNRESOLVED

PER = 'Ldji/midware/data/model/P3/DataGimbalSetPushPeripheralStatus;'
DTYPE = PER[:-1] + '$DataType;'
ABS = 'Ldji/midware/data/model/P3/DataGimbalAbsAngleControl;'
PUSH05 = 'Ldji/midware/data/model/P3/DataGimbalGetPushParams;'
ROOT = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalAbstraction;'

ACTUAL = ('PActualPose', 'RActualPose', 'YActualPose')
MOTOR = ('PMotorAngle', 'RMotorAngle', 'YMotorAngle')


def _ops(method):
    return [(i.get_name(), i.get_output()) for i in method.get_instructions()]


def _take(classes, methods, bank, owner, name, descriptor=None):
    found = [
        m for m in classes[owner].get_methods()
        if m.get_name() == name and (descriptor is None or m.get_descriptor() == descriptor)
    ]
    if len(found) != 1 or not found[0].get_code():
        raise ValueError('missing ' + owner + '->' + name)
    method = found[0]
    methods[(bank, owner, name, method.get_descriptor())] = dict(
        bank=bank, className=owner, method=name, descriptor=method.get_descriptor(),
        codeOffset=method.get_code_off(),
        instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
    )
    return _ops(method)


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
    bank05 = None
    cross_refs = []  # methods that mention both ActualPose-ish and GetPushParams

    for bank, raw in images:
        dex = DEX(raw)
        classes = {c.get_name(): c for c in dex.get_classes()}
        banks_meta.append(dict(segment=bank, derivedSha256=PREFIX_BANKS[bank]))
        if bank == 5:
            bank05 = classes
        for owner, cls in classes.items():
            for method in cls.get_methods():
                if not method.get_code():
                    continue
                texts = [i.get_output() for i in method.get_instructions()]
                joined = '\n'.join(texts)
                has_pose = any(k in joined for k in ('getPActualPose', 'getYActualPose', 'getRActualPose', 'PActualPose', 'YActualPose'))
                has_push = PUSH05 in joined or 'GimbalGetPushParams' in joined
                has_motor = any(k in joined for k in ('getPMotorAngle', 'getYMotorAngle', 'getRMotorAngle'))
                if has_pose and has_push:
                    cross_refs.append(dict(
                        bank=bank, className=owner, method=method.get_name(),
                        descriptor=method.get_descriptor(), alsoMotorAngle=has_motor,
                    ))
        print('bank%02d' % bank, flush=True)

    classes = bank05
    bank = 5
    clinit = [m for m in classes[DTYPE].get_methods() if m.get_name() == '<clinit>'][0]
    records = constructor_records(_ops(clinit), DTYPE)
    tags = {}
    for name in ACTUAL + MOTOR:
        args = records[name]['arguments']
        tags[name] = dict(ordinal=args[1], wireTag=args[2])
    actual_tags = {tags[n]['wireTag'] for n in ACTUAL}
    motor_tags = {tags[n]['wireTag'] for n in MOTOR}
    if actual_tags & motor_tags:
        raise ValueError('ActualPose and MotorAngle tags overlap')
    if tags['PActualPose']['wireTag'] != 34 or tags['YMotorAngle']['wireTag'] != 18:
        raise ValueError('expected DataType tags changed')

    abs_pack = _take(classes, methods, bank, ABS, 'doPack', '()V')
    abs_texts = [t for _, t in abs_pack]
    if not any('controlMode' in t for t in abs_texts):
        raise ValueError('ABS controlMode missing')
    # controlMode is a boolean flag bit, not a named earth/body reference-frame enum
    has_frame_enum = any(
        k in '\n'.join(abs_texts)
        for k in ('ReferenceFrame', 'Coordinate', 'NED', 'bodyFrame', 'earthFrame')
    )
    if has_frame_enum:
        raise ValueError('unexpected reference-frame token in ABS doPack')

    # getters exist and are distinct methods
    for axis, pose, motor in (
        ('P', 'getPActualPose', 'getPMotorAngle'),
        ('R', 'getRActualPose', 'getRMotorAngle'),
        ('Y', 'getYActualPose', 'getYMotorAngle'),
    ):
        _take(classes, methods, bank, PER, pose)
        _take(classes, methods, bank, PER, motor)

    # rotate absolute uses AbsAngleControl shorts, not peripheral ActualPose
    rotate = _take(classes, methods, bank, ROOT, 'rotate')
    rotate_joined = '\n'.join(t for _, t in rotate)
    if PER in rotate_joined or 'ActualPose' in rotate_joined:
        raise ValueError('rotate unexpectedly references peripheral ActualPose')
    if ABS + '->setPitch' not in rotate_joined:
        raise ValueError('rotate ABS path missing')

    # Dedup cross refs
    seen = set()
    unique_cross = []
    for row in cross_refs:
        key = (row['className'], row['method'], row['descriptor'])
        if key in seen:
            continue
        seen.add(key)
        unique_cross.append(row)

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
        methods=sorted(methods.values(), key=lambda r: (r['bank'], r['className'], r['method'])),
        status=compute_status(
            distinct_tags=actual_tags.isdisjoint(motor_tags),
            no_bytecode_equality=(unique_cross == []),
            physical_verified=False,
        ),
        peripheralDataTypeTags=tags,
        sourceActualPoseDistinctFromMotorAngle=True,
        absAngleControl=dict(
            bodyBytes=8,
            axisOrder=['yaw', 'roll', 'pitch'],
            hasControlModeBooleanBit=True,
            controlModeIsAbsoluteVersusRelativeNotPhysicalFrame=True,
            namedReferenceFrameFieldInDoPack=False,
        ),
        rotateUsesAbsAngleControlNotPeripheralActualPose=True,
        methodsReferencingBothActualPoseAndPushParams04_05=unique_cross,
        bytecodeEqualityBetweenActualPoseAnd0405AttitudeOrJointsProven=False,
        physicalReferenceFrameVerified=False,
        hostJointAnglesMaySubstituteFirmwareTrackAngles=False,
        reasonNotClosed=(
            'PREFIX reconfirms ActualPose tags 34/35/36 are distinct from MotorAngle 16/17/18; '
            '04:14 packs yaw/roll/pitch + controlMode/invalid bits without a named reference-frame field; '
            'rotate does not read peripheral ActualPose. No bytecode proof equates ActualPose to host '
            '04:05 attitude/joint fields. Physical frame, zero, and axis sense need hardware.'
        ),
        remaining=[
            'Do not map getJointAngles()/getAttitude() onto ActualPose or 04:62 road points.',
            'Do not treat controlMode absolute as earth-frame proof.',
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
    print('queue-B:', result['status'], 'crossRefs', len(result['methodsReferencingBothActualPoseAndPushParams04_05']), flush=True)


if __name__ == '__main__':
    main()
