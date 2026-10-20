#!/usr/bin/env python3
"""Eight-bank inventory / device-management gap review with live enum extraction.

Re-extracts CmdIdGimbal registrations from PREFIX bank05 and compares them to
protocol/COMMANDS.json. Does not treat the prior six-bank JSON as discovery proof.
Offline only; no vendor execution or SDK sends.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS
from ronin_subscription_trace import constructor_records
from ronin_command_refs import literal_packet_candidates, gimbal_command_set_value, ENUM as CMD_ENUM, CMDSET

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ROOT / 'protocol/COMMANDS.json'
PRIOR_ENUM_EVIDENCE = ROOT / 'protocol/research/ronin-command-references.json'
GIMBAL_ACTIVE = 'Ldji/midware/data/model/P3/DataGimbalActiveStatus;'
CENTER_ACTIVE = 'Ldji/midware/data/model/P3/DataCenterActiveStatus;'
EXCLUDED = {'FocusControl', 'NotiFyCameraId', 'Other'}
PACK = 'Ldji/midware/data/packages/P3/SendPack;'


def extract_cmdid_gimbal_entries(operations):
    """Parse CmdIdGimbal$CmdIdType <clinit> constructor literals into name/wire rows."""
    records = constructor_records(operations, CMD_ENUM)
    rows = []
    for name, entry in records.items():
        args = entry['arguments']
        if type(name) is not str or len(args) < 3 or type(args[1]) is not int or type(args[2]) is not int:
            raise ValueError('unexpected CmdIdGimbal constructor shape for ' + str(name))
        rows.append(dict(
            name=name,
            ordinal=args[1],
            commandId=args[2],
            constructorDescriptor=entry['descriptor'],
            hasExplicitClassArgument='Ljava/lang/Class;' in entry['descriptor'],
            boundClass=args[-1] if 'Ljava/lang/Class;' in entry['descriptor'] and isinstance(args[-1], str) and args[-1].startswith('L') else None,
            excluded=name in EXCLUDED,
        ))
    return sorted(rows, key=lambda r: (r['commandId'], r['name']))


def commands_json_gimbal_keys(manifest):
    keys = {}
    for row in manifest['commands']:
        if row['key'].startswith('04:'):
            keys[int(row['key'].split(':')[1], 16)] = row['key']
    return keys


def discover_missing_from_commands(extracted, cmd_keys):
    """Wires present in live enum extraction but absent from COMMANDS.json."""
    found = []
    for row in extracted:
        if row['excluded']:
            continue
        if row['commandId'] not in cmd_keys:
            found.append(dict(name=row['name'], commandId=row['commandId'], ordinal=row['ordinal']))
    return found


def orphan_gimbal_literal_candidates(operations, known_ids, gimbal_value=4):
    """Linear SendPack cmdSet=GIMBAL with cmdId outside the extracted enum set."""
    registers = {}
    packets = {}
    pending = None
    found = []
    for offset, (op, text) in enumerate(operations):
        args = text.split(', ')
        if op.startswith(('if-', 'goto', 'return', 'throw')) or 'switch' in op:
            registers.clear(); packets.clear(); pending = None
            continue
        if op.startswith('invoke-'):
            pending = None
            if CMDSET + '->value()I' in text and registers.get(args[0]) == ('gimbal', gimbal_value):
                pending = ('literal', gimbal_value)
            continue
        if op.startswith('move-result'):
            registers.pop(args[0], None)
            if 'wide' in op and re.fullmatch(r'v\d+', args[0]):
                registers.pop('v' + str(int(args[0][1:]) + 1), None)
            if pending is not None and op == 'move-result':
                registers[args[0]] = pending
            pending = None
            continue
        pending = None
        if op == 'iput' and len(args) == 3 and args[2] in (PACK + '->cmdId I', PACK + '->cmdSet I'):
            packet = registers.get(args[1]); value = registers.get(args[0])
            if not packet or packet[0] != 'packet':
                continue
            fields = packets.setdefault(packet[1], {}); key = 'cmdId' if '->cmdId ' in args[2] else 'cmdSet'
            fields.pop(key, None)
            if value and value[0] == 'literal':
                fields[key] = value[1]
            if fields.get('cmdSet') == gimbal_value and type(fields.get('cmdId')) is int and fields['cmdId'] not in known_ids:
                found.append(dict(instructionIndex=offset, packetCreationInstructionIndex=packet[1], commandId=fields['cmdId']))
            continue
        if op.startswith(('move-wide', 'const-wide')):
            registers.pop(args[0], None)
            if re.fullmatch(r'v\d+', args[0]):
                registers.pop('v' + str(int(args[0][1:]) + 1), None)
        elif op.startswith('move') and len(args) == 2:
            source = registers.get(args[1]); registers.pop(args[0], None)
            if source is not None:
                registers[args[0]] = source
        elif op in ('const/4', 'const/16', 'const'):
            registers.pop(args[0], None)
            if len(args) == 2 and re.fullmatch(r'-?\d+', args[1]):
                registers[args[0]] = ('literal', int(args[1]))
        elif op == 'new-instance':
            registers.pop(args[0], None)
            if len(args) == 2 and args[1] == PACK:
                registers[args[0]] = ('packet', offset)
        elif op == 'sget-object':
            registers.pop(args[0], None)
            if CMDSET + '->GIMBAL ' + CMDSET in text:
                registers[args[0]] = ('gimbal', gimbal_value)
        elif op.startswith(('const', 'iget', 'aget', 'sget', 'new', 'check-cast', 'array-length', 'instance-of', 'add-', 'sub-', 'mul-', 'div-', 'and-', 'or-', 'xor-', 'shl-', 'shr-', 'ushr-', 'int-to-', 'long-to-', 'float-to-', 'double-to-', 'neg-', 'not-', 'cmp')):
            registers.pop(args[0], None)
        elif re.fullmatch(r'v\d+', args[0]) and not op.startswith(('iput', 'sput', 'aput', 'monitor-', 'fill-array-data')):
            registers.pop(args[0], None)
    return found


def scan(apk, bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest() != APK_SHA256:
        raise ValueError('APK hash mismatch')
    images = []
    for bank, pin in PREFIX_BANKS.items():
        raw = (bank_dir / ('business-%02d-prefix-code-restored.dex' % bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest() != pin:
            raise ValueError('prefix bank hash mismatch: %02d' % bank)
        images.append((bank, raw))

    manifest = json.loads(COMMANDS.read_text())
    prior = json.loads(PRIOR_ENUM_EVIDENCE.read_text())
    if prior['apkSha256'] != APK_SHA256:
        raise ValueError('prior command-reference evidence APK hash mismatch')
    cmd_keys = commands_json_gimbal_keys(manifest)

    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX

    banks = []
    activation = []
    methods = {}
    orphan_literals = []
    known_enum_packet_hits = 0
    extracted = None
    gimbal_set = None
    enum_fingerprint = None

    for bank, raw in images:
        dex = DEX(raw)
        classes = {c.get_name(): c for c in dex.get_classes()}
        coded = total = instructions = 0
        if bank == 5:
            if CMD_ENUM not in classes or CMDSET not in classes:
                raise ValueError('CmdIdGimbal or CmdSet missing from PREFIX bank05')
            enum_m = next(m for m in classes[CMD_ENUM].get_methods() if m.get_name() == '<clinit>' and m.get_code())
            cmdset_m = next(m for m in classes[CMDSET].get_methods() if m.get_name() == '<clinit>' and m.get_code())
            enum_ops = [(i.get_name(), i.get_output()) for i in enum_m.get_instructions()]
            extracted = extract_cmdid_gimbal_entries(enum_ops)
            gimbal_set = gimbal_command_set_value([(i.get_name(), i.get_output()) for i in cmdset_m.get_instructions()])
            if gimbal_set != 4:
                raise ValueError('gimbal command set changed')
            enum_fingerprint = dict(
                bank=5, className=CMD_ENUM, method='<clinit>', descriptor=enum_m.get_descriptor(),
                codeOffset=enum_m.get_code_off(),
                instructionSha256=hashlib.sha256(enum_m.get_code().get_bc().get_raw()).hexdigest(),
                extractedEntryCount=len(extracted),
            )
        known_ids = {row['commandId'] for row in (extracted or []) if not row['excluded']} if extracted else set()
        for owner, cls in classes.items():
            for method in cls.get_methods():
                total += 1
                if not method.get_code():
                    continue
                coded += 1
                operations = [(i.get_name(), i.get_output()) for i in method.get_instructions()]
                instructions += len(operations)
                if extracted is not None:
                    known_enum_packet_hits += len(literal_packet_candidates(operations, known_ids, gimbal_set))
                    for hit in orphan_gimbal_literal_candidates(operations, known_ids, gimbal_set):
                        orphan_literals.append(dict(segment=bank, className=owner, method=method.get_name(), descriptor=method.get_descriptor(), **hit))
                if bank == 1 and owner.startswith('Lcom/dji/activate/active/Active'):
                    texts = []
                    off = 0
                    for op, text in operations:
                        if op.startswith('invoke-') and any(t in text for t in (GIMBAL_ACTIVE, CENTER_ACTIVE, 'DataBatteryActiveStatus', 'ActiveHttpApi', 'postToServer')):
                            texts.append(dict(operation=op, instructionByteOffset=off, text=text[:160]))
                        # approximate offset advance is not needed for listing; keep invoke text only
                        off += 1
                    if texts:
                        key = (owner, method.get_name(), method.get_descriptor())
                        methods[key] = dict(
                            bank=1, className=owner, method=method.get_name(),
                            descriptor=method.get_descriptor(),
                            instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
                            activationRelatedInvokes=texts,
                        )
                        activation.append(methods[key])
        banks.append(dict(segment=bank, derivedSha256=PREFIX_BANKS[bank], methodCount=total, methodWithCodeCount=coded, instructionCount=instructions))
        print('bank%02d: %d coded' % (bank, coded), flush=True)

    if extracted is None:
        raise ValueError('PREFIX bank05 enum extraction failed')

    newly = discover_missing_from_commands(extracted, cmd_keys)
    prior_by_name = {row['name']: row['commandId'] for row in prior['commands']}
    prior_diff = []
    for row in extracted:
        if row['excluded']:
            continue
        old = prior_by_name.get(row['name'])
        if old is None:
            prior_diff.append(dict(name=row['name'], commandId=row['commandId'], versusPrior='absent-from-prior-table'))
        elif old != row['commandId']:
            prior_diff.append(dict(name=row['name'], commandId=row['commandId'], priorCommandId=old, versusPrior='wire-mismatch'))
    for name, cid in prior_by_name.items():
        if name in EXCLUDED:
            continue
        if not any(r['name'] == name for r in extracted):
            prior_diff.append(dict(name=name, priorCommandId=cid, versusPrior='missing-from-live-extraction'))

    non_excluded = [r for r in extracted if not r['excluded']]
    registered = []
    for row in non_excluded:
        registered.append(dict(
            name=row['name'], commandId=row['commandId'], ordinal=row['ordinal'],
            commandsKey=cmd_keys.get(row['commandId']),
            presentInCommandsJson=row['commandId'] in cmd_keys,
        ))

    active_gimbal = [m for m in activation if any(GIMBAL_ACTIVE in r['text'] for r in m['activationRelatedInvokes'])]
    active_center = [m for m in activation if any(CENTER_ACTIVE in r['text'] for r in m['activationRelatedInvokes'])]
    active_web = [m for m in activation if 'ActiveWebController' in m['className'] or any('ActiveHttpApi' in r['text'] or 'postToServer' in r['text'] for r in m['activationRelatedInvokes'])]
    open_codec_unknown = [row['key'] for row in manifest['commands'] if row.get('requestCodec') == 'unknown' and not row.get('implementation')]
    device_mgmt = next(row for row in manifest['commands'] if row['key'] == 'unknown:device-management')

    return dict(
        schemaVersion=2,
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
        extraction=dict(
            source='PREFIX bank05 CmdIdGimbal$CmdIdType <clinit> via constructor_records',
            gimbalCommandSet=gimbal_set,
            enumClinit=enum_fingerprint,
            extractedEntryCount=len(extracted),
            nonExcludedEntryCount=len(non_excluded),
            excludedNames=sorted(EXCLUDED),
        ),
        gimbalEnumCommands=extracted,
        nonExcludedEnumsRegisteredInCommandsJson=registered,
        allNonExcludedLiveEnumsPresentInCommandsJson=len(newly) == 0,
        newlyDiscoveredGimbalWireCommands=newly,
        priorTableComparison=dict(
            priorEvidence=str(PRIOR_ENUM_EVIDENCE.relative_to(ROOT)),
            differences=prior_diff,
            priorTableIsNotDiscoverySource=True,
        ),
        eightBankPacketScan=dict(
            knownEnumLiteralCandidateHits=known_enum_packet_hits,
            orphanGimbalLiteralCandidatesOutsideExtractedEnum=orphan_literals,
            literalResolutionComplete=False,
            literalCandidatesProveSend=False,
            scope='linear SendPack syntax with branch resets; not full CFG/reflection/native proof',
        ),
        inventoryCompleteClaimed=False,
        inventoryCompleteRemainsFalse=True,
        commandsJsonEntryCount=len(manifest['commands']),
        openUnknownRequestKeys=open_codec_unknown,
        deviceManagementGapKey=device_mgmt['key'],
        bank01ActivationMethods=sorted(activation, key=lambda r: (r['className'], r['method'])),
        bank01ActiveGimbalRelatedMethods=[dict(className=m['className'], method=m['method'], descriptor=m['descriptor']) for m in active_gimbal],
        bank01ActiveCenterRelatedMethods=[dict(className=m['className'], method=m['method'], descriptor=m['descriptor']) for m in active_center],
        bank01ActiveWebOrHttpRelatedMethods=[dict(className=m['className'], method=m['method'], descriptor=m['descriptor']) for m in active_web],
        centerReadOnlyGetAlreadySeparated=True,
        activationOrBindingWriteOpened=False,
        sessionVersionNegotiated=False,
        deviceIdentityVerified=False,
        statusRequestAssociationFullyVerified=False,
        remaining=[
            'Live PREFIX bank05 enum extraction is the discovery source; the prior six-bank JSON is comparison-only.',
            'newlyDiscoveredGimbalWireCommands lists live non-excluded wires absent from COMMANDS.json (empty means coverage of the extracted set, not whole-firmware completeness).',
            'Orphan gimbal SendPack literals outside the extracted enum remain syntactic candidates only; banks may still hide reflection/native/dynamic paths.',
            'Bank01 ActiveDeviceController/ActiveWebController remain a device-management gap; do not open activation writes. inventoryComplete stays false.',
        ],
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('apk', 'bank-dir', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    r = scan(a.apk, a.bank_dir)
    a.output.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    print('extracted=%d non-excluded; newlyDiscovered=%d; orphanLiterals=%d; inventoryComplete remains false.' % (
        r['extraction']['nonExcludedEntryCount'], len(r['newlyDiscoveredGimbalWireCommands']),
        len(r['eightBankPacketScan']['orphanGimbalLiteralCandidatesOutsideExtractedEnum'])))


if __name__ == '__main__':
    main()
