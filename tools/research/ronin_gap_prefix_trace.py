#!/usr/bin/env python3
"""Eight-bank PREFIX re-audit for 04:0D / 04:2C / 04:0A caller gaps; offline only."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS

ENUM = 'Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;'
MODEL = 'Ldji/midware/data/model/P3/'
ONOFF_HYPOTHESIS = MODEL + 'DataGimbalSetOnOrOff;'
STEP = MODEL + 'DataGimbalSetTutorialStep;'
PUSH = MODEL + 'DataGimbalGetPushTutorialStatus;'
SET_ANGLE = MODEL + 'DataGimbalSetAngle;'
ANGLE_CONTROL = MODEL + 'DataGimbalAngleControl;'
HG724 = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalHG724Abstraction;'
DT501 = 'Ldji/sdksharedlib/hardware/abstractions/monitor/DJIDT501Abstraction;'
OWNERS = {
    '0D': set(),  # hypothesized class tracked separately
    '2C': {STEP, PUSH},
    '0A': {SET_ANGLE, ANGLE_CONTROL},
}
ENUM_NAMES = {
    '0D': 'SetOnOrOff',
    '2C': ('SetTutorialStep', 'GetPushTutorialStatus'),
    '0A': ('SetAngle', 'AngleControl'),
}


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

    bank_rows = []
    defined = {name: [] for name in (ONOFF_HYPOTHESIS, STEP, PUSH, SET_ANGLE, ANGLE_CONTROL, ENUM)}
    external = {key: [] for key in ('0D', '2C', '0A')}
    enum_outside = {key: [] for key in ('0D', '2C', '0A')}
    methods = []
    onoff_enum = None
    class_counts = {}

    for bank, raw in images:
        dex = DEX(raw)
        classes = {c.get_name(): c for c in dex.get_classes()}
        class_counts[bank] = len(classes)
        for name in defined:
            if name in classes:
                defined[name].append(bank)
        method_count = 0
        coded = 0
        instructions = 0
        for owner, cls in classes.items():
            for method in cls.get_methods():
                method_count += 1
                if not method.get_code():
                    continue
                coded += 1
                refs = []
                enum_hits = []
                off = 0
                for instruction in method.get_instructions():
                    op, text = instruction.get_name(), instruction.get_output()
                    instructions += 1
                    if op.startswith('invoke-'):
                        for key, owners in OWNERS.items():
                            for target in owners:
                                if target + '->' in text and owner != target:
                                    refs.append(dict(kind='external-direct-invoke', target=target, operation=op, instructionByteOffset=off))
                    if op in ('sget-object', 'sput-object') and ENUM + '->' in text:
                        match = re.search(re.escape(ENUM) + r'->([A-Za-z0-9_$]+) ', text)
                        if match:
                            name = match.group(1)
                            for key, names in ENUM_NAMES.items():
                                wanted = names if isinstance(names, tuple) else (names,)
                                if name in wanted and owner != ENUM:
                                    enum_hits.append(dict(kind='enum-outside-reference', enumName=name, operation=op, instructionByteOffset=off))
                    if bank == 5 and owner == ENUM and method.get_name() == '<clinit>' and 'SetOnOrOff' in text and op.startswith('const-string'):
                        # capture nearby constructor window once
                        pass
                    off += instruction.get_length()
                if refs or enum_hits:
                    row = dict(
                        segment=bank, className=owner, method=method.get_name(),
                        descriptor=method.get_descriptor(), codeOffset=method.get_code_off(),
                        instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
                        mentionsHg724=HG724 in owner,
                        references=refs, enumOutsideReferences=enum_hits,
                    )
                    methods.append(row)
                    for ref in refs:
                        for key, owners in OWNERS.items():
                            if ref['target'] in owners:
                                external[key].append(dict(segment=bank, className=owner, method=method.get_name(), descriptor=method.get_descriptor(), target=ref['target']))
                    for hit in enum_hits:
                        for key, names in ENUM_NAMES.items():
                            wanted = names if isinstance(names, tuple) else (names,)
                            if hit['enumName'] in wanted:
                                enum_outside[key].append(dict(segment=bank, className=owner, method=method.get_name(), descriptor=method.get_descriptor(), enumName=hit['enumName']))
                if bank == 5 and owner == ENUM and method.get_name() == '<clinit>':
                    rows_ops = []
                    o = 0
                    for instruction in method.get_instructions():
                        rows_ops.append((o, instruction.get_name(), instruction.get_output()))
                        o += instruction.get_length()
                    for idx, (off, op, text) in enumerate(rows_ops):
                        if op.startswith('const-string') and text.endswith('SetOnOrOff'):
                            window = rows_ops[idx:idx + 6]
                            invoke = next((t for _, wop, t in window if wop.startswith('invoke-') and ENUM + '-><init>' in t), '')
                            wire = 13 if any(wop.startswith('const') and ', 13' in t for _, wop, t in window) else None
                            onoff_enum = dict(
                                instructionByteOffset=off,
                                wireCommandId=wire,
                                constructorBindsRequestClass='Ljava/lang/Class;' in invoke,
                                threeArgConstructorWithoutClass='<init>(Ljava/lang/String; I I)V' in invoke,
                                hypothesizedClassDefinedInScannedBanks=False,
                            )
        bank_rows.append(dict(
            segment=bank, derivedSha256=PREFIX_BANKS[bank], classCount=class_counts[bank],
            methodCount=method_count, methodWithCodeCount=coded, instructionCount=instructions,
        ))
        print('bank%02d: %d coded methods, %d instructions' % (bank, coded, instructions), flush=True)

    if onoff_enum is None or onoff_enum['wireCommandId'] != 13:
        raise ValueError('SetOnOrOff enum registration evidence missing or changed')
    onoff_enum['hypothesizedClassDefinedInScannedBanks'] = bool(defined[ONOFF_HYPOTHESIS])
    onoff_enum['hypothesizedClassName'] = ONOFF_HYPOTHESIS

    # Deduplicate external caller rows while preserving order
    def unique(rows):
        seen = set()
        out = []
        for row in rows:
            key = (row['segment'], row['className'], row['method'], row['descriptor'], row.get('target') or row.get('enumName'))
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
        return out

    for key in external:
        external[key] = unique(external[key])
        enum_outside[key] = unique(enum_outside[key])

    angle_external_classes = sorted({r['className'] for r in external['0A']})
    only_dt501 = angle_external_classes == [DT501]

    return dict(
        schemaVersion=1,
        apkSha256=APK_SHA256,
        bankSha256={str(b): p for b, p in PREFIX_BANKS.items()},
        appCodeExecuted=False,
        liveUiExecuted=False,
        targetDeviceVerified=False,
        wholeProtocolRecovered=False,
        wholeAppRecovered=False,
        allScannedBodiesRecovered=False,
        indirectReflectionResolved=False,
        researchToolProvidesSdkInterface=False,
        sdkSendAdded=False,
        sdkReceiveAdded=False,
        scannedBanks=list(PREFIX_BANKS),
        previousSixBankEvidence={
            '0D': 'protocol/research/ronin-command-references.json',
            '2C': 'protocol/research/ronin-tutorial-evidence.json',
            '0A': 'protocol/research/ronin-angles-evidence.json',
        },
        scope='eight PREFIX_BANKS named views; class presence, external invoke, and enum-outside references for 0D/2C/0A',
        banks=bank_rows,
        classDefinitions={
            'DataGimbalSetOnOrOffHypothesized': defined[ONOFF_HYPOTHESIS],
            'DataGimbalSetTutorialStep': defined[STEP],
            'DataGimbalGetPushTutorialStatus': defined[PUSH],
            'DataGimbalSetAngle': defined[SET_ANGLE],
            'DataGimbalAngleControl': defined[ANGLE_CONTROL],
            'CmdIdGimbalCmdIdType': defined[ENUM],
        },
        command0D=dict(
            key='04:0D',
            enumName='SetOnOrOff',
            enumRegistration=onoff_enum,
            externalDirectCallers=[],
            enumOutsideReferences=enum_outside['0D'],
            hypothesizedClassDefined=bool(defined[ONOFF_HYPOTHESIS]),
            hg724BusinessEntryEstablished=False,
            equatedToMotorSpecialCmdOrParam35=False,
            sendOpened=False,
        ),
        command2C=dict(
            key='04:2C',
            modelClass=STEP,
            pushClass=PUSH,
            externalDirectCallers=external['2C'],
            enumOutsideReferences=enum_outside['2C'],
            classesDefinedInBanks=defined[STEP],
            hg724BusinessEntryEstablished=False,
            effectOrRecoveryVerified=False,
            sendOpened=False,
        ),
        command0A=dict(
            key='04:0A',
            setAngleClass=SET_ANGLE,
            angleControlClass=ANGLE_CONTROL,
            externalDirectCallers=external['0A'],
            enumOutsideReferences=enum_outside['0A'],
            externalCallerClasses=angle_external_classes,
            onlyDt501UvcExternalCallersInScan=only_dt501,
            hg724BusinessEntryEstablished=False,
            cameraUvcInCurrentScope=False,
            sendOpened=False,
        ),
        newBanks01And07=dict(
            classDefinitions={
                name: [b for b in banks if b in (1, 7)]
                for name, banks in {
                    'OnOffHypothesis': defined[ONOFF_HYPOTHESIS],
                    'SetTutorialStep': defined[STEP],
                    'SetAngle': defined[SET_ANGLE],
                    'AngleControl': defined[ANGLE_CONTROL],
                }.items()
            },
            externalDirectCallers=[r for key in external for r in external[key] if r['segment'] in (1, 7)],
            enumOutsideReferences=[r for key in enum_outside for r in enum_outside[key] if r['segment'] in (1, 7)],
        ),
        methods=methods,
        remaining=[
            'Eight-bank scan still finds no DataGimbalSetOnOrOff definition and no SetOnOrOff enum-outside references.',
            'Tutorial SetTutorialStep still has no external direct callers across eight banks; prior body narrowing evidence is unchanged and send stays closed.',
            'SetAngle external callers remain DT501 UVC only; AngleControl has no external direct callers; HG724 0A path not established.',
            'Absence of references is not firmware unsupported proof; reflection/native/dynamic paths remain unruled-out.',
        ],
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('apk', 'bank-dir', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    result = scan(a.apk, a.bank_dir)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('0D hypothesized class banks=%s; 2C external=%d; 0A external=%d (DT501-only=%s); no SDK send.' % (
        result['classDefinitions']['DataGimbalSetOnOrOffHypothesized'],
        len(result['command2C']['externalDirectCallers']),
        len(result['command0A']['externalDirectCallers']),
        result['command0A']['onlyDt501UvcExternalCallersInScan'],
    ))


if __name__ == '__main__':
    main()
