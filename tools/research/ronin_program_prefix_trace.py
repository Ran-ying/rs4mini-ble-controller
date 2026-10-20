#!/usr/bin/env python3
"""Eight-bank PREFIX re-audit for program commands 25/37/62/63; offline only."""
import argparse
import hashlib
import json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS

OWNERS = {
    '25': 'Ldji/midware/data/model/P3/DataGimbalSetDelayTimelapseParams;',
    '37': 'Ldji/midware/data/model/P3/DataRonin2SetTimelapseParams;',
    '62': 'Ldji/midware/data/model/P3/DataGimbalSetTrackStatus;',
    '63': 'Ldji/midware/data/model/P3/DataGimbalSetPanoramaParams;',
}
PANO = OWNERS['63']
TRACK = OWNERS['62']
CAMERA_TOKENS = ('Exposure', 'setExposure', 'mExposure', 'Camera', 'Shutter', 'RecordOrPreview', 'setRecordOrPreview', 'setPictures')


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

    banks = []
    external = {key: [] for key in OWNERS}
    defined = {key: [] for key in OWNERS}
    methods = []
    pano_fields = []
    track_control_apis = []
    start_stop_pairs = {key: {'startMethods': [], 'stopMethods': [], 'utilsStopMethods': []} for key in OWNERS}

    for bank, raw in images:
        dex = DEX(raw)
        classes = {c.get_name(): c for c in dex.get_classes()}
        coded = total = instructions = 0
        for owner, cls in classes.items():
            for key, target in OWNERS.items():
                if owner == target:
                    defined[key].append(bank)
            for method in cls.get_methods():
                total += 1
                if not method.get_code():
                    continue
                coded += 1
                refs = []
                cameraish = []
                off = 0
                for instruction in method.get_instructions():
                    op, text = instruction.get_name(), instruction.get_output()
                    instructions += 1
                    if op.startswith('invoke-'):
                        for key, target in OWNERS.items():
                            if target + '->' in text and owner != target:
                                refs.append(dict(target=target, operation=op, instructionByteOffset=off, invokeText=text[:160]))
                        for token in CAMERA_TOKENS:
                            if token in text:
                                cameraish.append(dict(token=token, operation=op, instructionByteOffset=off))
                    off += instruction.get_length()
                if refs:
                    row = dict(
                        segment=bank, className=owner, method=method.get_name(),
                        descriptor=method.get_descriptor(),
                        instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
                        mentionsHg724='HG724' in owner,
                        cameraOrExposureMentions=cameraish,
                        references=refs,
                    )
                    methods.append(row)
                    for ref in refs:
                        for key, target in OWNERS.items():
                            if ref['target'] == target:
                                external[key].append(dict(
                                    segment=bank, className=owner, method=method.get_name(),
                                    descriptor=method.get_descriptor(), mentionsHg724='HG724' in owner,
                                    hasCameraOrExposureMention=bool(cameraish),
                                ))
                                name = method.get_name()
                                bucket = start_stop_pairs[key]
                                if 'sendToDeviceStart' in name or name == 'startTimeLapse':
                                    bucket['startMethods'].append(row['className'] + '->' + name)
                                if 'sendToDeviceStop' in name or name == 'stopTimeLapse' or name.startswith('stop') and 'Work' in name:
                                    if 'CreateUtils' in owner:
                                        bucket['utilsStopMethods'].append(row['className'] + '->' + name)
                                    else:
                                        bucket['stopMethods'].append(row['className'] + '->' + name)
                if bank == 5 and owner == PANO and method.get_name() == 'doPack':
                    for instruction in method.get_instructions():
                        text = instruction.get_output()
                        if '->m' in text and PANO in text:
                            field = text.split('->', 1)[1].split(' ')[0]
                            if field not in pano_fields:
                                pano_fields.append(field)
                if bank == 5 and owner == TRACK and method.get_name().startswith('set'):
                    track_control_apis.append(method.get_name() + method.get_descriptor())
        banks.append(dict(segment=bank, derivedSha256=PREFIX_BANKS[bank], methodCount=total, methodWithCodeCount=coded, instructionCount=instructions))
        print('bank%02d: %d coded' % (bank, coded), flush=True)

    def unique(rows):
        seen = set(); out = []
        for row in rows:
            key = (row['segment'], row['className'], row['method'], row['descriptor'])
            if key in seen: continue
            seen.add(key); out.append(row)
        return out

    for key in external:
        external[key] = unique(external[key])
        for kind in start_stop_pairs[key]:
            start_stop_pairs[key][kind] = sorted(set(start_stop_pairs[key][kind]))

    if 'mExposure' not in pano_fields:
        raise ValueError('panorama exposure field missing from doPack scan')
    if not any('setRecordOrPreview' in a for a in track_control_apis):
        raise ValueError('track record/preview API missing')

    hg724_hits = [m for m in methods if m['mentionsHg724']]
    pure_gimbal_openable = False  # explicit gate decision for this audit

    commands = {}
    for key, owner in OWNERS.items():
        commands[key] = dict(
            key='04:' + key,
            modelClass=owner,
            definedInBanks=defined[key],
            externalDirectCallers=external[key],
            startStop=start_stop_pairs[key],
            hg724NamedCallerCount=sum(1 for r in external[key] if r['mentionsHg724']),
            callersWithCameraOrExposureMentions=sum(1 for r in external[key] if r['hasCameraOrExposureMention']),
            sendOpened=False,
        )

    return dict(
        schemaVersion=1,
        apkSha256=APK_SHA256,
        bankSha256={str(b): p for b, p in PREFIX_BANKS.items()},
        appCodeExecuted=False,
        liveUiExecuted=False,
        targetDeviceVerified=False,
        wholeProtocolRecovered=False,
        researchToolProvidesSdkInterface=False,
        sdkSendAdded=False,
        sdkReceiveAdded=False,
        scannedBanks=list(PREFIX_BANKS),
        banks=banks,
        methods=methods,
        commands=commands,
        panoramaDoPackFields=pano_fields,
        trackControlApis=sorted(set(track_control_apis)),
        hg724NamedProgramCallers=hg724_hits,
        newBanks01And07External=[m for m in methods if m['segment'] in (1, 7)],
        cameraFieldsInterleavedWithPanorama=True,
        trackRecordPreviewInterleaved=True,
        reliableStopWithCameraIsolationEstablished=False,
        pureGimbalProgramPrimitiveOpenable=pure_gimbal_openable,
        programExecutionOpened=False,
        priorTrackPointResearch='protocol/research/ronin-track-points-evidence.json',
        priorProgramEntryResearch='protocol/research/ronin-program-entry-evidence.json',
        remaining=[
            'Eight-bank scan finds Create* UI start/stop callers only; no HG724-named abstraction invokes program protocol classes.',
            'Panorama doPack still includes mExposure; track APIs include setRecordOrPreview — camera/capture fields are not isolated.',
            'CreateUtils stop*PreviewWork helpers exist but do not establish camera-isolated reliable stop for SDK.',
            'Therefore no pure-gimbal program primitive is opened; ActualPose/MotorAngle separation remains as in track-point research.',
        ],
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('apk', 'bank-dir', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    r = scan(a.apk, a.bank_dir)
    a.output.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    print('program callers 25/37/62/63 = %d/%d/%d/%d; HG724 named=%d; pure openable=%s' % (
        len(r['commands']['25']['externalDirectCallers']),
        len(r['commands']['37']['externalDirectCallers']),
        len(r['commands']['62']['externalDirectCallers']),
        len(r['commands']['63']['externalDirectCallers']),
        len(r['hg724NamedProgramCallers']),
        r['pureGimbalProgramPrimitiveOpenable'],
    ))


if __name__ == '__main__':
    main()
