#!/usr/bin/env python3
"""Conditional COMMON00:32 receive audit. Static bytes only; no SDK or vendor execution."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS
from ronin_activation_trace import COMMON, ROOT, GIMBAL, QUERY, VERSION, VERSIONS, nullable_literal_enums
from ronin_program_receive import BASE, RECV, TABLE, MANAGER, source_payload_view, delivery_paths
from ronin_calibration_ack import check_receive_offsets, CALL, CCODE
from ronin_calibration_transport import branch_target
CONFIG = 'Ldji/midware/data/config/P3/'
COMMON_TABLE = CONFIG + 'CmdIdCommon;'
UTIL = CONFIG + 'DataUtil;'
DEVICE_TYPE = CONFIG + 'DeviceType;'
CMDSET = CONFIG + 'CmdSet;'


def activation_version_ack_view(flags, payload):
    """An explicit version-query context, not arbitrary ActiveStatus traffic.

    Source ccode stripping is conditional on the base COMMON table. Failure and
    short bodies never yield a version; no source singleton/cache is emulated.
    """
    view = source_payload_view(flags, payload, needs_ccode=True)
    if not view['isAck']:
        raise ValueError('ACK required in explicit version-query context')
    body = bytes.fromhex(view['businessBodyHex'])
    success = view['returnCode'] == 0
    raw = body[0] if success and body else None
    name = next((n for n, v in VERSIONS.items() if v == raw), None)
    return dict(view, sourceCallbackReportsSuccess=success,
                businessComplete=bool(body), versionRaw=raw, versionName=name,
                sourceVersionFallback=('OTHER' if raw is not None and name is None else None),
                versionKnown=name is not None, trailingBodyHex=body[1:].hex() if success and body else None,
                explicitQueryContextRequired=True, requestAssociationVerified=False,
                actualSessionVersionVerified=False, targetDeviceVerified=False,
                activationStateDecoded=False)


def common_policy(record):
    if record.get('descriptor') != '(Ljava/lang/String; I I Z Z Ljava/lang/Class;)V':
        raise ValueError('COMMON ActiveStatus constructor changed')
    args = record.get('arguments')
    if args != ['ActiveStatus', 20, 50, 0, 1, None] or record.get('explicitNullArgumentIndexes') != [5]:
        raise ValueError('COMMON ActiveStatus literal binding changed')
    if any(type(args[i]) is not int for i in (1, 2, 3, 4)):
        raise ValueError('literal integer/boolean source arguments required')
    return dict(commandSet=0, commandId=50, isBlock=False, isMix=True,
                modelClass=None, explicitNullClass=True)


def check_common_constructor(rows):
    by = {off: (op, text) for off, op, text in rows}
    expected = {6: ('const/4', 'v1, 1'),
                8: ('iput-boolean', 'v1, v0, ' + COMMON + '->isNeedCcode Z'),
                16: ('iput-boolean', 'v5, v0, ' + COMMON + '->isMix Z'),
                20: ('iput-boolean', 'v4, v0, ' + COMMON + '->isBlock Z'),
                24: ('iput-object', 'v6, v0, ' + COMMON + '->cls Ljava/lang/Class;')}
    if any(by.get(k) != v for k, v in expected.items()):
        raise ValueError('COMMON ccode/block/mix/class constructor producers changed')


def check_push_order(rows):
    by = {off: (op, text) for off, op, text in rows}
    expected = {0: ('invoke-virtual', 'v5, v6, ' + ROOT + '->setRecData([B)V'),
                6: ('if-eqz', 'v6, +10ah'),
                10: ('array-length', 'v0, v6'), 12: ('const/16', 'v1, 11'),
                16: ('if-lt', 'v0, v1, +105h'),
                24: ('iget', 'v0, v0, Ldji/midware/data/packages/P3/Pack;->cmdType I'),
                28: ('const/4', 'v1, 1'), 30: ('if-ne', 'v0, v1, +004h')}
    if any(by.get(k) != v for k, v in expected.items()):
        raise ValueError('activation cache assignment/guard order changed')
    if branch_target(30, by[30][1]) != 38:
        raise ValueError('activation ACK guard branch changed')


def trace(apk, bank_dir):
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
    classes = {}
    methods = {}
    callers = []

    def take(bank, owner, name, descriptor=None):
        ms = [m for m in classes[bank][owner].get_methods() if m.get_name() == name
              and (descriptor is None or m.get_descriptor() == descriptor)]
        if len(ms) != 1 or not ms[0].get_code():
            raise ValueError('missing/ambiguous receive method ' + owner + name)
        m = ms[0]
        methods[(bank, owner, name, m.get_descriptor())] = dict(
            bank=bank, className=owner, method=name, descriptor=m.get_descriptor(),
            codeOffset=m.get_code_off(),
            instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
        offset = 0
        rows = []
        for i in m.get_instructions():
            rows.append((offset, i.get_name(), i.get_output()))
            offset += i.get_length()
        return rows

    def ops(rows):
        return [(op, text) for _, op, text in rows]

    def require(rows, *tokens):
        for token in tokens:
            if not any(token in text for _, _, text in rows):
                raise ValueError('missing activation receive evidence ' + token)

    for bank, raw in images:
        current = {c.get_name(): c for c in DEX(raw).get_classes()}
        if bank == 5:
            classes[bank] = current
        for owner, c in current.items():
            for m in c.get_methods():
                if not m.get_code():
                    continue
                refs = []
                device_literals = set()
                for i in m.get_instructions():
                    text = i.get_output()
                    if i.get_name() == 'sget-object' and DEVICE_TYPE + '->' in text:
                        device_literals.add(text.split('->', 1)[1].split()[0])
                    target = re.search(r'(L[^\s,]+;)->([^\s(]+)\(', text) if i.get_name().startswith('invoke-') else None
                    if target and target.group(1) == QUERY:
                        refs.append(target.group(2))
                if refs:
                    classes[bank] = current
                    take(bank, owner, m.get_name(), m.get_descriptor())
                    callers.append(dict(bank=bank, className=owner, method=m.get_name(),
                                        descriptor=m.get_descriptor(), queryMethods=refs,
                                        deviceTypeLiterals=sorted(device_literals),
                                        literalDataflowToQueryVerified=False))
    binding = nullable_literal_enums(ops(take(5, COMMON, '<clinit>')), COMMON, selected={'ActiveStatus'})['ActiveStatus']
    policy = common_policy(binding)
    check_common_constructor(take(5, COMMON, '<init>', binding['descriptor']))
    for name, field in [('isNeedCcode', 'isNeedCcode Z'), ('isBlock', 'isBlock Z'),
                        ('isMix', 'isMix Z'), ('getDataModel', 'cls Ljava/lang/Class;'),
                        ('getDataBase', 'dataBase Ldji/midware/data/manager/P3/DataBase;')]:
        require(take(5, COMMON, name), COMMON + '->' + field)
    if classes[5][COMMON_TABLE].get_superclassname() != TABLE:
        raise ValueError('COMMON table inheritance changed')
    require(take(5, COMMON_TABLE, 'getCurCmdIdValues'), COMMON + '->values()')
    for name in ('isNeedCcode', 'isMix', 'isBlock', 'getDataModel', 'getDataBase'):
        require(take(5, TABLE, name), 'CmdIdInterface;->' + name + '(')
    require(take(5, RECV, 'isNeedCcode'), CMDSET + '->cmdIdClass()', TABLE + '->isNeedCcode(I)Z')
    check_receive_offsets(take(5, RECV, 'setBuffer'))
    manager = take(5, MANAGER, 'setMsg')
    require(manager, '->isBlock(I)Z', '->isMix(I)Z', '->getDataModel(I)',
            '->getDataBase(I)', 'DataBaseProcessor;->setMsg(', '->getDataModelName(I I I)',
            '->forName(', 'getInstance', '->invoke(', BASE + '->setPushRecPack(')
    refl = take(5, UTIL, 'getDataBaseInstRefl')
    if ops(refl)[:3] != [('const/4', 'v0, 0'), ('if-nez', 'v4, +003h'), ('return-object', 'v0')]:
        raise ValueError('null Class reflection fallback changed')
    require(take(5, COMMON_TABLE, 'getDataModelName', '(I I)Ljava/lang/String;'),
            DEVICE_TYPE + '->toString()', COMMON + '->toString()', UTIL + '->getDataModelName(')
    require(take(5, COMMON_TABLE, 'getDataModelName', '(I I I)Ljava/lang/String;'), COMMON_TABLE + '->getDataModelName(I I)')
    require(take(5, UTIL, 'getDataModelName'), 'dji.midware.data.model.P3.Data', '->ENGLISH ', '->toUpperCase(', '->toLowerCase(')
    # GIMBAL uses the ordinary constructor: name=null, Enum.toString fallback.
    device_ops = ops(take(5, DEVICE_TYPE, '<clinit>'))
    index = next(i for i, (op, text) in enumerate(device_ops) if op == 'sput-object' and DEVICE_TYPE + '->GIMBAL ' in text)
    if device_ops[index-3:index] != [('const-string/jumbo', 'v1, GIMBAL'), ('const/4', 'v3, 4'), ('invoke-direct', 'v0, v1, v3, v3, ' + DEVICE_TYPE + '-><init>(Ljava/lang/String; I I)V')]:
        raise ValueError('GIMBAL device label/value changed')
    require(take(5, DEVICE_TYPE, '<init>', '(Ljava/lang/String; I I)V'), 'v1, 0', '->name Ljava/lang/String;')
    require(take(5, DEVICE_TYPE, 'toString'), 'Ljava/lang/Enum;->toString()')
    if classes[5][GIMBAL].get_superclassname() != ROOT:
        raise ValueError('activation push model inheritance changed')
    require(take(5, BASE, 'setPushRecPack'), 'Pack;->data [B', BASE + '->setPushRecData([B)V')
    check_push_order(take(5, ROOT, 'setPushRecData'))
    require(take(5, BASE, 'setRecData'), '->_recData [B')
    for name in ('getVer', 'setDevice', 'setRecData'):
        take(5, QUERY, name)
    require(take(5, QUERY, 'setRecData'), GIMBAL + '->setVersion(', VERSION + '->find(I)')
    require(take(5, VERSION, 'find'), VERSION + '->OTHER ', VERSION + '->_equals(I)Z')
    call = take(5, CALL, 'call', '()Ljava/lang/Integer;')
    require(call, CCODE + '->OK ', CCODE + '->SUCCEED ', CMDSET + '->CAMERA ', BASE + '->setRecData([B)V')
    by = {off: (op, text) for off, op, text in call}
    if by[48][0] != 'if-nez' or branch_target(48, by[48][1]) != 184 or by[72][0] != 'if-ne' or branch_target(72, by[72][1]) != 102:
        raise ValueError('COMMON/non-CAMERA return-code callback branch changed')
    require(take(5, CMDSET, 'getExtraCmdSetInterface'), '->forName(', '->newInstance()')
    require(take(5, CMDSET, '<init>', '(Ljava/lang/String; I I Ldji/midware/data/config/P3/DJICmdSetBase;)V'), '->getExtraCmdSetInterface(', '->cls ')
    return dict(schemaVersion=1, apkSha256=APK_SHA256,
                bankSha256={str(b): p for b, p in PREFIX_BANKS.items()},
                methods=sorted(methods.values(), key=lambda r: (r['bank'], r['className'], r['method'], r['descriptor'])),
                baseCommonPolicy=dict(policy, needsCcode=True, needsCcodeDerivedFromConstructor=True),
                receiveMapping=dict(ackReturnCodeRawPayloadOffset=0, ackBusinessRawPayloadOffset=1,
                                    requestBusinessRawPayloadOffset=0, sourceCallbackSuccessCcode=0,
                                    cameraOnlyAlternateSuccessCcode=1, actualCmdSetExtensionSelectionVerified=False),
                mixedDelivery=dict(delivery_paths(is_block=False, is_mix=True),
                                   nullClassAlsoYieldsNullBaseInstance=True,
                                   conditionalGimbalReflectionClass='dji.midware.data.model.P3.DataGimbalActiveStatus',
                                   actualReflectionSuccessVerified=False),
                sourcePushOrder=dict(assignsRawCacheBeforeNullLengthAndAckGuards=True,
                                     parsingMinimumBytes=11, shortVersionAckCouldReplaceStatusCache=True,
                                     everyAckGuaranteedToReachPushModel=False, sourceCacheBehaviorCopiedToSdk=False),
                versionQueryCallers=sorted(callers, key=lambda r: (r['bank'], r['className'], r['method'], r['descriptor'])),
                callerScanScope='Exact invoke target owner DataCommonActiveGetVer across all eight banks; device literals are not a dataflow proof.',
                absentGimbalCallerProvesUnsupported=False, requestAssociationVerified=False,
                hg724EntryEstablished=False, actualSessionVersionVerified=False,
                targetDeviceVerified=False, appCodeExecuted=False, javaReflectionExecuted=False,
                sdkSendAdded=False, sdkReceiveAdded=False, wholeProtocolRecovered=False,
                remaining=['Base-table ACK mapping does not verify actual extension/session or target traffic.',
                           'Version query and activation status share command00:32; decode only with explicit request context.',
                           'Failure/short/unknown versions must not become known version0 or overwrite activation status.',
                           'GIMBAL source response support does not prove an HG724 version-query caller, activation/binding or persistence.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('apk', 'bank-dir', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    r = trace(a.apk, a.bank_dir)
    a.output.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    print('%d methods; %d direct query-caller methods; base COMMON mapping only; no sends.' % (len(r['methods']), len(r['versionQueryCallers'])))

if __name__ == '__main__':
    main()
