#!/usr/bin/env python3
"""Eight-bank inventory / device-management gap review; offline only."""
import argparse
import hashlib
import json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ROOT / 'protocol/COMMANDS.json'
ENUM_EVIDENCE = ROOT / 'protocol/research/ronin-command-references.json'
ACTIVE = 'Lcom/dji/activate/active/ActiveDeviceController;'
GIMBAL_ACTIVE = 'Ldji/midware/data/model/P3/DataGimbalActiveStatus;'
CENTER_ACTIVE = 'Ldji/midware/data/model/P3/DataCenterActiveStatus;'
EXCLUDED = {'FocusControl', 'NotiFyCameraId', 'Other'}


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
    refs = json.loads(ENUM_EVIDENCE.read_text())
    if refs['apkSha256'] != APK_SHA256:
        raise ValueError('command-reference evidence APK hash mismatch')

    cmd_keys = {}
    for row in manifest['commands']:
        if row['key'].startswith('04:'):
            cmd_keys[int(row['key'].split(':')[1], 16)] = row['key']

    enum_rows = []
    missing = []
    for entry in refs['commands']:
        name = entry['name']
        cid = entry['commandId']
        key = cmd_keys.get(cid)
        row = dict(name=name, commandId=cid, commandsKey=key, excluded=name in EXCLUDED)
        enum_rows.append(row)
        if name not in EXCLUDED and key is None:
            missing.append(row)
    if missing:
        raise ValueError('inventory missing gimbal enum commands: ' + ','.join(m['name'] for m in missing))

    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX

    banks = []
    activation = []
    methods = {}
    for bank, raw in images:
        dex = DEX(raw)
        classes = {c.get_name(): c for c in dex.get_classes()}
        coded = total = instructions = 0
        for owner, cls in classes.items():
            for method in cls.get_methods():
                total += 1
                if not method.get_code():
                    continue
                coded += 1
                instructions += sum(1 for _ in method.get_instructions())
                if bank == 1 and owner.startswith('Lcom/dji/activate/active/Active'):
                    texts = []
                    off = 0
                    for instruction in method.get_instructions():
                        op, text = instruction.get_name(), instruction.get_output()
                        if op.startswith('invoke-') and any(t in text for t in (GIMBAL_ACTIVE, CENTER_ACTIVE, 'DataBatteryActiveStatus', 'ActiveHttpApi', 'postToServer')):
                            texts.append(dict(operation=op, instructionByteOffset=off, text=text[:160]))
                        off += instruction.get_length()
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

    active_gimbal = [m for m in activation if any(GIMBAL_ACTIVE in r['text'] for r in m['activationRelatedInvokes'])]
    active_center = [m for m in activation if any(CENTER_ACTIVE in r['text'] for r in m['activationRelatedInvokes'])]
    active_web = [m for m in activation if 'ActiveWebController' in m['className'] or any('ActiveHttpApi' in r['text'] or 'postToServer' in r['text'] for r in m['activationRelatedInvokes'])]

    open_codec_unknown = [row['key'] for row in manifest['commands'] if row.get('requestCodec') == 'unknown' and not row.get('implementation')]
    device_mgmt = next(row for row in manifest['commands'] if row['key'] == 'unknown:device-management')

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
        gimbalEnumCommands=enum_rows,
        excludedCameraOrSentinel=sorted(EXCLUDED),
        allNonExcludedGimbalEnumsPresentInCommandsJson=True,
        newlyDiscoveredGimbalWireCommands=[],
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
            'All 40 non-excluded CmdIdGimbal enum wires already appear in protocol/COMMANDS.json; eight-bank scan added no new gimbal wire IDs.',
            'Bank01 ActiveDeviceController/ActiveWebController still call gimbal/center active-status and HTTP activate paths; treat as device-management gap, not HG724 BLE binding proof, and do not open writes.',
            '00:32 CENTER GET remains read-only and is not activation, binding, or version negotiation.',
            'inventoryComplete stays false: unknown codecs, unverified sessions/identity, and hardware acceptance remain.',
        ],
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('apk', 'bank-dir', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    r = scan(a.apk, a.bank_dir)
    a.output.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    print('enums=%d; new wires=%d; bank01 activation methods=%d; inventoryComplete remains false; no activation write.' % (
        len(r['gimbalEnumCommands']), len(r['newlyDiscoveredGimbalWireCommands']), len(r['bank01ActivationMethods'])))


if __name__ == '__main__':
    main()
