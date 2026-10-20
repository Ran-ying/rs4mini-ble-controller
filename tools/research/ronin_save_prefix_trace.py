#!/usr/bin/env python3
"""Eight-bank PREFIX_BANKS save-command reference audit; offline only.

Scans all eight named restored DEX views for SaveUserParams instruction
references. Classifies invoke/allocation/field/enum-registration/string kinds.
Does not execute App/JNI/native code, construct DUML, or open an SDK send path.
"""
import argparse
import hashlib
import json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS

OWNER = 'Ldji/midware/data/model/P3/DataGimbalSaveUserParams;'
ENUM = 'Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;'
ENUM_FIELD = ENUM + '->SaveUserParams ' + ENUM
HG724 = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalHG724Abstraction;'
TOKENS = ('SaveUserParams', 'DataGimbalSaveUserParams')


def classify_reference(op, text, owner):
    """Classify one instruction; allocation/class/string/enum are not direct calls."""
    if not any(token in text for token in TOKENS) and OWNER not in text:
        return None
    if OWNER + '->' in text and op.startswith('invoke-'):
        return 'internal-invoke' if owner == OWNER else 'external-direct-invoke'
    if op == 'new-instance' and OWNER in text:
        return 'allocation'
    if op == 'const-class' and OWNER in text:
        return 'class-literal'
    if op.startswith(('iget', 'iput', 'sget', 'sput')) and OWNER + '->' in text:
        return 'field-reference'
    if op == 'sput-object' and ENUM_FIELD in text:
        return 'enum-registration'
    if ENUM + '->SaveUserParams' in text:
        return 'command-enum-reference'
    if op.startswith('const-string'):
        return 'string-literal-not-proven-reflection'
    return 'other-reference'


def scan(apk, bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest() != APK_SHA256:
        raise ValueError('APK hash mismatch')
    images = []
    for bank, expected in PREFIX_BANKS.items():
        raw = (bank_dir / ('business-%02d-prefix-code-restored.dex' % bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('prefix bank hash mismatch: %02d' % bank)
        images.append((bank, raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX

    rows = []
    methods = []
    source_start = None
    source_do_pack = None
    enum_registration = None
    for bank, raw in images:
        dex = DEX(raw)
        classes = dex.get_classes()
        readable = 0
        total = 0
        instructions = 0
        string_matches = sorted(set(str(s) for s in dex.get_strings() if any(t in str(s) for t in TOKENS)))
        for cls in classes:
            owner = cls.get_name()
            for method in cls.get_methods():
                total += 1
                if not method.get_code():
                    continue
                readable += 1
                references = []
                offset = 0
                rows_ops = []
                for instruction in method.get_instructions():
                    op, text = instruction.get_name(), instruction.get_output()
                    kind = classify_reference(op, text, owner)
                    if kind:
                        references.append(dict(kind=kind, operation=op, instructionByteOffset=offset))
                    rows_ops.append((offset, op, text))
                    offset += instruction.get_length()
                    instructions += 1
                if references:
                    fingerprint = hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest()
                    methods.append(dict(
                        segment=bank, className=owner, method=method.get_name(),
                        descriptor=method.get_descriptor(), codeOffset=method.get_code_off(),
                        instructionSha256=fingerprint, references=references,
                        mentionsHg724Abstraction=any(HG724 in text for _, _, text in rows_ops),
                    ))
                if bank == 5 and owner == OWNER and method.get_name() == 'doPack' and method.get_descriptor() == '()V':
                    source_do_pack = dict(
                        instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
                        operations=[op for _, op, _ in rows_ops],
                        emptyBody=rows_ops == [(0, 'return-void', '')],
                    )
                if bank == 5 and owner == OWNER and method.get_name() == 'start' and method.get_descriptor() == '(Ldji/midware/interfaces/DJIDataCallBack;)V':
                    texts = [text for _, _, text in rows_ops]
                    source_start = dict(
                        instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
                        senderType='APP',
                        receiverType='GIMBAL',
                        cmdType='REQUEST',
                        needAck='YES',
                        businessEncrypt='NO',
                        cmdSet='GIMBAL',
                        cmdIdEnum='SaveUserParams',
                        packsEmptyDoPackBody=True,
                        mentions=[
                            'DeviceType;->APP ', 'DeviceType;->GIMBAL ',
                            'CMDTYPE;->REQUEST ', 'NEEDACK;->YES ',
                            'EncryptType;->NO ', 'CmdSet;->GIMBAL ',
                            ENUM + '->SaveUserParams ',
                        ],
                        allMentionsPresent=all(any(token in text for text in texts) for token in [
                            'DeviceType;->APP ', 'DeviceType;->GIMBAL ',
                            'CMDTYPE;->REQUEST ', 'NEEDACK;->YES ',
                            'EncryptType;->NO ', 'CmdSet;->GIMBAL ',
                            ENUM + '->SaveUserParams ',
                        ]),
                        finalTransportEncryptionVerified=False,
                    )
                if bank == 5 and owner == ENUM and method.get_name() == '<clinit>':
                    for idx, (off, op, text) in enumerate(rows_ops):
                        if op.startswith('const-string') and text.endswith('SaveUserParams'):
                            window = rows_ops[idx:idx + 5]
                            invoke = next((wtext for _, wop, wtext in window if wop.startswith('invoke-') and ENUM + '-><init>' in wtext), '')
                            wire_ops = [wtext for _, wop, wtext in window if wop.startswith('const') and ', 17' in wtext]
                            enum_registration = dict(
                                instructionByteOffset=off,
                                wireCommandId=17 if wire_ops else None,
                                constructorDescriptor='(Ljava/lang/String; I I)V' if '<init>(Ljava/lang/String; I I)V' in invoke else invoke,
                                constructorBindsRequestClass='Ljava/lang/Class;' in invoke,
                                threeArgConstructorWithoutClass='<init>(Ljava/lang/String; I I)V' in invoke,
                                note='Enum registers wire 17 without Class binding; DataGimbalSaveUserParams exists separately.',
                            )
        rows.append(dict(
            segment=bank, derivedSha256=PREFIX_BANKS[bank], classCount=len(classes),
            methodCount=total, methodWithCodeCount=readable, instructionCount=instructions,
            stringTableMatches=string_matches, saveReferenceMethodCount=sum(1 for m in methods if m['segment'] == bank),
        ))
        print('bank%02d: %d methods with code, %d instructions, %d save-reference methods' % (
            bank, readable, instructions, sum(1 for m in methods if m['segment'] == bank)), flush=True)

    if source_do_pack is None or not source_do_pack['emptyBody']:
        raise ValueError('SaveUserParams doPack empty-body evidence missing or changed')
    if source_start is None or not source_start['allMentionsPresent']:
        raise ValueError('SaveUserParams start pack evidence missing or changed')
    if enum_registration is None or enum_registration.get('wireCommandId') != 17:
        raise ValueError('SaveUserParams enum wire registration evidence missing or changed')

    external = [
        dict(segment=m['segment'], className=m['className'], method=m['method'], descriptor=m['descriptor'])
        for m in methods if any(r['kind'] == 'external-direct-invoke' for r in m['references'])
    ]
    allocations_external = [
        dict(segment=m['segment'], className=m['className'], method=m['method'], descriptor=m['descriptor'])
        for m in methods
        if m['className'] != OWNER and any(r['kind'] == 'allocation' for r in m['references'])
    ]
    field_refs = [
        dict(segment=m['segment'], className=m['className'], method=m['method'], descriptor=m['descriptor'], references=m['references'])
        for m in methods if any(r['kind'] == 'field-reference' for r in m['references'])
    ]
    new_bank_hits = [m for m in methods if m['segment'] in (1, 7)]
    kind_counts = {}
    for m in methods:
        for r in m['references']:
            kind_counts[r['kind']] = kind_counts.get(r['kind'], 0) + 1

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
        targetModelCallPathEstablished=False,
        hg724BusinessEntryEstablished=False,
        persistencePathEstablished=False,
        researchToolProvidesSdkInterface=False,
        sdkSendAdded=False,
        sdkReceiveAdded=False,
        saveSettingsOpened=False,
        parameterWriteEquatedToPersistence=False,
        scannedBanks=list(PREFIX_BANKS),
        previousSixBankHistoricalEvidence='protocol/research/ronin-save-callers-evidence.json',
        scope='instruction references across eight PREFIX_BANKS named views; not whole-App, firmware, or reflection proof',
        banks=rows,
        methods=methods,
        externalDirectCallers=external,
        externalAllocations=allocations_external,
        fieldReferenceMethods=field_refs,
        referenceKindCounts=kind_counts,
        newBanks01And07ReferenceMethods=new_bank_hits,
        sourceDoPack=source_do_pack,
        sourceStartPack=source_start,
        enumRegistration=enum_registration,
        remaining=[
            'Eight-bank instruction scan still finds no external direct SaveUserParams callers, including banks 01/07.',
            'Empty doPack plus ACK and enum wire 17 prove the class can build a request; they are not an HG724 business or persistence path.',
            'Enum 3-arg registration without Class binding is not a missing-command proof and not a model support proof.',
            'Reflection, dynamic loading, native, and firmware-side persistence remain unruled-out; do not open saveSettings.',
        ],
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('apk', 'bank-dir', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    result = scan(a.apk, a.bank_dir)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('%d methods contain save references; %d external direct callers; banks 01/07 hits=%d; no SDK send.' % (
        len(result['methods']), len(result['externalDirectCallers']), len(result['newBanks01And07ReferenceMethods'])))


if __name__ == '__main__':
    main()
