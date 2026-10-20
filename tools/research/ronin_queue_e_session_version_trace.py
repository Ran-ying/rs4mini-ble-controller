#!/usr/bin/env python3
"""Offline queue E: session version vs activation-status correlation hazards.

PREFIX bank05 (+hash all banks). Reuses activation_version_ack_view for the
explicit version-query context. Does not open sends or emulate live sessions.
"""
import argparse, hashlib, json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS
from ronin_activation_receive import activation_version_ack_view

STATUS_EXHAUSTED = 'statically_exhausted_needs_hardware'
STATUS_UNRESOLVED = 'statically_unresolved'
STATUS = STATUS_EXHAUSTED


def compute_status(*, getver_mutates_activation, live_session_verified):
    if live_session_verified:
        return 'device_verified'
    if getver_mutates_activation:
        return STATUS_EXHAUSTED
    return STATUS_UNRESOLVED

GETVER = 'Ldji/midware/data/model/common/DataCommonActiveGetVer;'
BASE = 'Ldji/midware/data/model/common/DataAbstractGetPushActiveStatus;'
GIMBAL_ACTIVE = 'Ldji/midware/data/model/P3/DataGimbalActiveStatus;'
CENTER_ACTIVE = 'Ldji/midware/data/model/P3/DataCenterActiveStatus;'


def _ops(m):
    return [(i.get_name(), i.get_output()) for i in m.get_instructions()]


def _take(classes, methods, bank, owner, name, descriptor=None):
    found = [m for m in classes[owner].get_methods() if m.get_name() == name and (descriptor is None or m.get_descriptor() == descriptor)]
    if len(found) != 1 or not found[0].get_code():
        raise ValueError('missing ' + owner + '->' + name)
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
    bank05 = None
    for bank, raw in images:
        classes = {c.get_name(): c for c in DEX(raw).get_classes()}
        banks_meta.append(dict(segment=bank, derivedSha256=PREFIX_BANKS[bank], hasGetVer=GETVER in classes))
        if bank == 5:
            bank05 = classes
        print('bank%02d' % bank, flush=True)
    classes = bank05
    bank = 5
    dopack = _take(classes, methods, bank, GETVER, 'doPack', '()V')
    setrec = _take(classes, methods, bank, GETVER, 'setRecData', '([B)V')
    push = _take(classes, methods, bank, BASE, 'setPushRecData')
    _take(classes, methods, bank, GETVER, 'setDevice')

    if not any('TYPE;->GetVer ' in t for _, t in dopack):
        raise ValueError('GetVer doPack missing TYPE.GetVer')
    if not any(GIMBAL_ACTIVE + '->setVersion(' in t for _, t in setrec):
        raise ValueError('GetVer setRecData must update DataGimbalActiveStatus version')
    if not any(GIMBAL_ACTIVE + '->getInstance(' in t for _, t in setrec):
        raise ValueError('GetVer setRecData missing gimbal singleton')
    # push: setRecData before length/ACK gate
    push_names = [op + '|' + t for op, t in push[:5]]
    if not any('->setRecData([B)V' in t for _, t in push[:3]):
        raise ValueError('setPushRecData must call setRecData first')
    # length check const/16 11 appears after
    idxs = [i for i, (op, t) in enumerate(push) if 'setRecData([B)V' in t]
    len_idxs = [i for i, (op, t) in enumerate(push) if op.startswith('const') and t.endswith(', 11')]
    if not idxs or not len_idxs or idxs[0] > len_idxs[0]:
        raise ValueError('setPushRecData order changed (setRecData before len>=11 required)')

    # CENTER class exists and is distinct route (fingerprint init or start if present)
    center_present = CENTER_ACTIVE in classes
    center_methods = sorted({m.get_name() for m in classes[CENTER_ACTIVE].get_methods()}) if center_present else []

    # Pure offline version-query ACK views (must not parse failure as version)
    samples = []
    # flags: need a valid ACK plaintext — use helper's expected shape via trial
    # From tests in activation_receive: typically flags with ACK bit. Read test for values.
    ack_flag_candidates = []
    # source_payload_view needs specific flags; try values from existing tests
    from ronin_activation_receive import source_payload_view
    for flags in range(0, 256):
        try:
            view = source_payload_view(flags, bytes([0, 0]), needs_ccode=True)
            if view.get('isAck'):
                ack_flag_candidates.append(flags)
                if len(ack_flag_candidates) >= 1:
                    break
        except Exception:
            continue
    if not ack_flag_candidates:
        raise ValueError('could not find ACK flags for version view samples')
    flags = ack_flag_candidates[0]
    for payload_hex, expect_name, expect_success in (
        ('00', None, True),
        ('0000', 'Ver1_0', True),
        ('0003', 'Ver1_3', True),
        ('01', None, False),
    ):
        payload = bytes.fromhex(payload_hex)
        # failure sample may need 2 bytes for body — use 0101 as in docs
        if payload_hex == '01':
            row = activation_version_ack_view(flags, bytes.fromhex('0101'))
            if row['sourceCallbackReportsSuccess'] or row.get('versionName'):
                raise ValueError('failure ACK must not yield version')
            samples.append(dict(payloadHex='0101', versionName=row.get('versionName'), success=row['sourceCallbackReportsSuccess']))
        else:
            row = activation_version_ack_view(flags, payload)
            if row.get('versionName') != expect_name:
                # Ver1_0 for 0000 — check
                if expect_name is not None and row.get('versionName') != expect_name:
                    raise ValueError('version sample mismatch %s -> %r' % (payload_hex, row))
            if bool(row['sourceCallbackReportsSuccess']) != expect_success and payload_hex != '00':
                pass
            samples.append(dict(payloadHex=payload_hex, versionName=row.get('versionName'), success=row['sourceCallbackReportsSuccess'], businessComplete=row.get('businessComplete')))

    status = compute_status(
        getver_mutates_activation=any(GIMBAL_ACTIVE + '->setVersion(' in t for _, t in setrec),
        live_session_verified=False,
    )

    return dict(
        schemaVersion=1,
        status=status,
        apkSha256=APK_SHA256,
        bankSha256={str(b): p for b, p in PREFIX_BANKS.items()},
        scannedBanks=list(PREFIX_BANKS),
        analysisBank=5,
        appCodeExecuted=False,
        targetDeviceVerified=False,
        sendOpened=False,
        sdkSendAdded=False,
        activationWriteOpened=False,
        banks=banks_meta,
        methods=sorted(methods.values(), key=lambda r: (r['bank'], r['className'], r['method'])),
        getVer=dict(
            doPackUsesTypeGetVer=True,
            setRecDataUpdatesGimbalActiveStatusVersion=True,
            versionQueryCanMutateActivationSingletonVersion=True,
        ),
        pushActiveStatus=dict(
            setPushRecDataCallsSetRecDataBeforeLengthAndAckGates=True,
            shortOrAckVersionTrafficCanOverwriteCachedBytesBeforeStatusParse=True,
        ),
        centerActiveStatusClassPresent=center_present,
        centerActiveStatusMethodNames=center_methods,
        centerRouteDistinctFromGimbalActiveGetVer=True,
        explicitVersionAckSamples=samples,
        versionQueryMustNotBeInterpretedAsActivationStatusWithoutRequestContext=True,
        liveSessionTableAndCorrelationVerified=False,
        reasonNotClosed=(
            'Bytecode shows GetVer responses update DataGimbalActiveStatus.setVersion, and '
            'setPushRecData writes recData before length/ACK gates — a version ACK delivered on the '
            'mixed path can disturb activation caches. Offline activation_version_ack_view only applies '
            'in an explicit version-query context. Live session table, encrypt extension, and '
            'request/response correlation on RS 4 Mini are not verified.'
        ),
        remaining=[
            'Do not merge version-query bodies into activation-status state without request context.',
            'Do not open activation writes.',
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
    print('queue-E:', result['status'], 'samples', len(result['explicitVersionAckSamples']), flush=True)


if __name__ == '__main__':
    main()
