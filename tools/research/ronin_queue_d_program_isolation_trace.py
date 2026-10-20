#!/usr/bin/env python3
"""Offline queue D: program model path and camera/exposure/record isolation.

Re-extracts PREFIX doPack fields and HG724/program gates. Does not open sends.
"""
import argparse, hashlib, json, re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS

STATUS = 'statically_exhausted_needs_hardware'
HG724 = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalHG724Abstraction;'
MODELS = {
    '25': 'Ldji/midware/data/model/P3/DataGimbalSetDelayTimelapseParams;',
    '37': 'Ldji/midware/data/model/P3/DataRonin2SetTimelapseParams;',
    '62': 'Ldji/midware/data/model/P3/DataGimbalSetTrackStatus;',
    '63': 'Ldji/midware/data/model/P3/DataGimbalSetPanoramaParams;',
}
CAMERAISH = re.compile(r'(exposure|record|preview|picture|camera|shoot|shutter)', re.I)


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
    # preserve order unique
    seen = set()
    ordered = []
    for f in fields:
        if f not in seen and f != '_sendData':
            seen.add(f)
            ordered.append(f)
    return ordered, hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(), method.get_code_off()


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
                                cameraName=bool(CAMERAISH.search(owner + method.get_name())),
                            ))
        print('bank%02d' % bank, flush=True)

    classes = bank05
    commands = {}
    methods = []
    for key, owner in MODELS.items():
        fields, sha, off = _fields_from_dopack(classes, owner)
        camera_fields = [f for f in fields if CAMERAISH.search(f)]
        # unique external
        seen = set()
        callers = []
        for row in external[key]:
            k = (row['bank'], row['className'], row['method'], row['descriptor'])
            if k in seen:
                continue
            seen.add(k)
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

    pano = commands['63']
    track = commands['62']
    if 'mExposure' not in pano['doPackFields']:
        raise ValueError('panorama mExposure missing')
    if 'mRecordOrPreview' not in track['doPackFields']:
        raise ValueError('track mRecordOrPreview missing')
    if hg724_program:
        # unexpected named program methods on HG724 — still not proof of isolation
        pass

    pure_openable = False  # never true without camera isolation
    packed_info = {
        '25': 'mInfoByte present; camera/exposure bits not fully decoded in this audit — not treated as camera-free',
        '37': 'mInfoByte present; camera/exposure bits not fully decoded in this audit — not treated as camera-free',
    }
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
        programExecutionOpened=False,
        banks=banks_meta,
        methods=methods,
        status=STATUS,
        commands=commands,
        hg724NamedProgramMethods=hg724_program,
        panoramaHasExposureField=True,
        trackHasRecordOrPreviewField=True,
        timelapsePackedInfoBytesUnresolvedForCameraIsolation=packed_info,
        cameraFieldsInterleavedWithPanorama=True,
        trackRecordPreviewInterleaved=True,
        reliableStopWithCameraIsolationEstablished=False,
        pureGimbalProgramPrimitiveOpenable=pure_openable,
        hg724ModelSpecificProgramEntryEstablished=False,
        missingHg724NamedCallerDoesNotProveNoInheritedEntry=True,
        reasonNotClosed=(
            'PREFIX reconfirms Create UI-only external callers, panorama mExposure and track '
            'mRecordOrPreview interleaved with gimbal program packs, and no HG724-named program '
            'methods. That does not isolate a pure-gimbal primitive or prove model/component gates '
            'for RS 4 Mini. Program execution stays closed.'
        ),
        remaining=[
            'Do not open 04:25/37/62/63 sends.',
            'Do not treat missing HG724-named program methods as no inherited entry.',
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
    print('queue-D:', result['status'], 'pureOpenable', result['pureGimbalProgramPrimitiveOpenable'], flush=True)


if __name__ == '__main__':
    main()
