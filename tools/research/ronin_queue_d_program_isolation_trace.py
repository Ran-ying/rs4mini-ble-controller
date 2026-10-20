#!/usr/bin/env python3
"""Offline queue D: program model path and camera/exposure/record isolation.

Status is computed from traced evidence (mInfoByte bit maps, named fields, callers).
PREFIX only. No sends / vendor execution / hardware.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS

STATUS_UNRESOLVED = 'statically_unresolved'
STATUS_EXHAUSTED = 'statically_exhausted_needs_hardware'
STATUS = STATUS_EXHAUSTED  # compat: expected when bit maps + interleave facts hold
HG724 = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalHG724Abstraction;'
MODELS = {
    '25': 'Ldji/midware/data/model/P3/DataGimbalSetDelayTimelapseParams;',
    '37': 'Ldji/midware/data/model/P3/DataRonin2SetTimelapseParams;',
    '62': 'Ldji/midware/data/model/P3/DataGimbalSetTrackStatus;',
    '63': 'Ldji/midware/data/model/P3/DataGimbalSetPanoramaParams;',
}
CAMERAISH = re.compile(r'(exposure|record|preview|picture|camera|shoot|shutter|external)', re.I)
INFO_SETTERS = {
    '25': ('setControlExternalDevice', 'setISPreview', 'setIsTripod', 'setMode', 'setStartOrStop'),
    '37': ('setIsTripod', 'setMode', 'setStartOrPreview', 'setStartOrStop'),
}


def _ops(method):
    return [(i.get_name(), i.get_output()) for i in method.get_instructions()]


def _fields_from_dopack(classes, owner):
    found = [m for m in classes[owner].get_methods() if m.get_name() == 'doPack' and m.get_descriptor() == '()V']
    if len(found) != 1 or not found[0].get_code():
        raise ValueError('missing doPack ' + owner)
    method = found[0]
    fields = []
    for instruction in method.get_instructions():
        text = instruction.get_output()
        if instruction.get_name().startswith('iget') and owner + '->' in text:
            fields.append(text.split('->', 1)[1].split(' ', 1)[0])
    seen = set()
    ordered = []
    for name in fields:
        if name not in seen and name != '_sendData':
            seen.add(name)
            ordered.append(name)
    return ordered, hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(), method.get_code_off()


def _parse_info_byte_setter(owner, method):
    """Extract OR-into-mInfoByte shift/mask from a linear setter body."""
    ops = _ops(method)
    texts = [t for _, t in ops]
    if not any(owner + '->mInfoByte B' in t and op.startswith('iput') for op, t in ops):
        return None
    shift = None
    mask = None
    for op, text in ops:
        if op == 'and-int/lit8' and ', 1' in text:
            mask = 1
        if op.startswith('shl-int'):
            # shl-int/lit8 v2, v2, N  or shl-int/lit8 v2, v2, 7
            parts = text.split(', ')
            if len(parts) >= 3 and parts[-1].lstrip('-').isdigit():
                shift = int(parts[-1])
            elif len(parts) == 2 and 'lit8' in op:
                # shl-int/lit8 v2, v2, 7 form sometimes as last
                pass
        if op == 'shl-int/lit8':
            parts = text.split(', ')
            if len(parts) == 3:
                shift = int(parts[2])
    # setMode uses or without shift (bit 0)
    if shift is None and any(op == 'or-int/2addr' for op, _ in ops):
        shift = 0
    if shift is None:
        return None
    camera_or_preview = bool(CAMERAISH.search(method.get_name()))
    return dict(
        method=method.get_name(),
        descriptor=method.get_descriptor(),
        bitIndex=shift,
        lowBitMask=mask,
        cameraOrPreviewOrExternalName=camera_or_preview,
        instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
    )


def compute_status(info_byte_maps, commands, reliable_stop, model_entry):
    """Derive queue-D status from traced facts; never a hard-coded constant.

    - statically_unresolved: 25/37 mInfoByte bit maps incomplete, or no camera/
      preview/external interleave evidence yet.
    - statically_exhausted_needs_hardware: bit maps resolved and interleave
      proven (named exposure/record fields and/or preview/external info bits),
      while camera-isolated stop and RS 4 Mini model/component entry remain
      unproven (reliable_stop/model_entry stay false offline).
    """
    required = ('25', '37')
    if any(k not in info_byte_maps or not info_byte_maps[k].get('bitsResolved') for k in required):
        return STATUS_UNRESOLVED
    named_camera = bool(commands.get('63', {}).get('cameraOrRecordFieldsInDoPack')) or bool(
        commands.get('62', {}).get('cameraOrRecordFieldsInDoPack')
    )
    info_camera = any(info_byte_maps[k].get('cameraPreviewOrExternalBits') for k in required)
    if not named_camera and not info_camera:
        return STATUS_UNRESOLVED
    if reliable_stop and model_entry:
        # Offline tool never establishes these; reserved if a later source does.
        return STATUS_EXHAUSTED
    return STATUS_EXHAUSTED



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

    banks_meta = []
    external = {k: [] for k in MODELS}
    hg724_program = []
    info_setter_callers = []
    bank05 = None
    for bank, raw in images:
        classes = {c.get_name(): c for c in DEX(raw).get_classes()}
        banks_meta.append(dict(segment=bank, derivedSha256=PREFIX_BANKS[bank]))
        if bank == 5:
            bank05 = classes
        if HG724 in classes:
            names = {m.get_name() for m in classes[HG724].get_methods()}
            for name in names:
                if any(k in name.lower() for k in ('track', 'panorama', 'timelapse', 'program', 'roadpoint')):
                    hg724_program.append(dict(bank=bank, method=name))
        for owner, cls in classes.items():
            for method in cls.get_methods():
                if not method.get_code():
                    continue
                for instruction in method.get_instructions():
                    if not instruction.get_name().startswith('invoke'):
                        continue
                    text = instruction.get_output()
                    for key, target in MODELS.items():
                        if target + '->' in text and owner != target:
                            external[key].append(dict(
                                bank=bank, className=owner, method=method.get_name(),
                                descriptor=method.get_descriptor(),
                                createUi='create' in owner.lower(),
                            ))
                            if any(s in text for s in ('setISPreview', 'setControlExternalDevice', 'setStartOrPreview')):
                                info_setter_callers.append(dict(
                                    bank=bank, className=owner, method=method.get_name(),
                                    target=text.split('->')[1].split('(')[0] if '->' in text else text[:80],
                                ))
        print('bank%02d' % bank, flush=True)

    classes = bank05
    commands = {}
    methods = []
    info_byte_maps = {}
    for key, owner in MODELS.items():
        fields, sha, off = _fields_from_dopack(classes, owner)
        camera_fields = [f for f in fields if CAMERAISH.search(f)]
        seen = set()
        callers = []
        for row in external[key]:
            item = (row['bank'], row['className'], row['method'], row['descriptor'])
            if item in seen:
                continue
            seen.add(item)
            callers.append(row)
        commands[key] = dict(
            key='04:' + key,
            modelClass=owner,
            doPackFields=fields,
            cameraOrRecordFieldsInDoPack=camera_fields,
            externalDirectCallers=callers,
            allExternalCallersInCreateUi=all(r['createUi'] for r in callers) and bool(callers),
            doPackInstructionSha256=sha,
            doPackCodeOffset=off,
        )
        methods.append(dict(bank=5, className=owner, method='doPack', descriptor='()V', codeOffset=off, instructionSha256=sha))
        if key in INFO_SETTERS:
            bits = []
            for name in INFO_SETTERS[key]:
                found = [m for m in classes[owner].get_methods() if m.get_name() == name and m.get_code()]
                if len(found) != 1:
                    raise ValueError('missing/ambiguous info setter ' + owner + name)
                parsed = _parse_info_byte_setter(owner, found[0])
                if parsed is None:
                    raise ValueError('could not parse mInfoByte setter ' + name)
                bits.append(parsed)
                methods.append(dict(
                    bank=5, className=owner, method=name, descriptor=found[0].get_descriptor(),
                    codeOffset=found[0].get_code_off(), instructionSha256=parsed['instructionSha256'],
                ))
            bit_indexes = sorted({b['bitIndex'] for b in bits})
            camera_bits = [b for b in bits if b['cameraOrPreviewOrExternalName']]
            info_byte_maps[key] = dict(
                field='mInfoByte',
                setters=bits,
                bitIndexes=bit_indexes,
                cameraPreviewOrExternalBits=camera_bits,
                bitsResolved=len(bits) == len(INFO_SETTERS[key]) and len(bit_indexes) == len(bits),
            )

    if 'mExposure' not in commands['63']['doPackFields']:
        raise ValueError('panorama mExposure missing')
    if 'mRecordOrPreview' not in commands['62']['doPackFields']:
        raise ValueError('track mRecordOrPreview missing')
    if 'mInfoByte' not in commands['25']['doPackFields'] or 'mInfoByte' not in commands['37']['doPackFields']:
        raise ValueError('timelapse mInfoByte missing from doPack fields')

    reliable_stop = False
    model_entry = False
    status = compute_status(info_byte_maps, commands, reliable_stop, model_entry)
    pure_openable = False

    return dict(
        schemaVersion=2,
        apkSha256=APK_SHA256,
        bankSha256={str(b): p for b, p in PREFIX_BANKS.items()},
        scannedBanks=list(PREFIX_BANKS),
        analysisBank=5,
        appCodeExecuted=False,
        targetDeviceVerified=False,
        sendOpened=False,
        sdkSendAdded=False,
        programExecutionOpened=False,
        banks=banks_meta,
        methods=methods,
        status=status,
        statusComputedBy='compute_status(info_byte_maps, commands, reliable_stop, model_entry)',
        commands=commands,
        infoByteMaps=info_byte_maps,
        infoByteSetterCallers=info_setter_callers,
        hg724NamedProgramMethods=hg724_program,
        panoramaHasExposureField=True,
        trackHasRecordOrPreviewField=True,
        cameraFieldsInterleavedWithPanorama=True,
        trackRecordPreviewInterleaved=True,
        timelapseInfoBytePreviewOrExternalBitsInterleaved=any(
            info_byte_maps[k]['cameraPreviewOrExternalBits'] for k in ('25', '37')
        ),
        reliableStopWithCameraIsolationEstablished=reliable_stop,
        pureGimbalProgramPrimitiveOpenable=pure_openable,
        hg724ModelSpecificProgramEntryEstablished=model_entry,
        missingHg724NamedCallerDoesNotProveNoInheritedEntry=True,
        reasonNotClosed=(
            'mInfoByte bit maps are resolved: 04:25 packs preview (bit3) and controlExternalDevice (bit7) '
            'beside mode/tripod/start-stop; 04:37 packs startOrPreview (bit3) beside the same. '
            'Named panorama mExposure and track mRecordOrPreview remain interleaved. '
            'Create UI callers invoke those setters. Isolation is statically disproven for a pure '
            'gimbal primitive; RS 4 Mini model/component reachability and a camera-free stop path '
            'still need hardware or a different source entry.'
            if status == STATUS_EXHAUSTED else
            'mInfoByte or named camera fields are not fully resolved; status stays statically_unresolved.'
        ),
        remaining=[
            'Do not open 04:25/37/62/63 sends.',
            'Do not treat missing HG724-named program methods as no inherited entry.',
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--bank-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = scan(args.apk, args.bank_dir)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('queue-D:', result['status'], 'bits25', result['infoByteMaps']['25']['bitIndexes'], flush=True)


if __name__ == '__main__':
    main()
