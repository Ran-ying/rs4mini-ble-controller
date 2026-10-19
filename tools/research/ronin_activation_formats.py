#!/usr/bin/env python3
"""Offline activation GET/V13/V14 source views; no frame, callback, SDK or sending."""
import argparse
import hashlib
import json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS
from ronin_activation_trace import ROOT, GIMBAL, VERSION, VERSIONS, source_type_value
from ronin_calibration_transport import branch_target
V13 = 'Ldji/midware/data/model/common/UAVGeneralActivationPushV13;'
V14 = 'Ldji/midware/data/model/common/UAVGeneralActivationPushVerifyV14;'
BASE = 'Ldji/midware/data/manager/P3/DataBase;'
BYTES = 'Ldji/midware/util/BytesUtil;'


def snapshot(body):
    if not isinstance(body, (bytes, bytearray)):
        raise ValueError('explicit business bytes required')
    return bytes(body)


def source_sn_text(raw):
    """GIMBAL source forward-SN rendering, not ordinary ASCII or UTF-8.

    aget-byte sign extends: comparing it with int255 never skips byteFF.
    Nonalphanumerics are appended as signed decimal integers, including zero.
    """
    data = snapshot(raw)
    return ''.join(chr(v) if 48 <= v <= 57 or 65 <= v <= 90 or 97 <= v <= 122
                   else str(v if v < 128 else v - 256) for v in data)


def source_integer_read(body, start, width):
    """Bounded DataBase Integer view; not a validating packet decoder.

    Source zero-padding is shown only here, never used as validated GET data.
    """
    data = snapshot(body)
    if type(start) is not int or type(width) is not int or start < 0 or not 1 <= width <= 32:
        raise ValueError('explicit nonnegative offset and bounded source width required')
    part = data[start:start + width]
    return int.from_bytes((part + bytes(max(0, 4 - len(part))))[:4], 'little', signed=True)


def get_status_view(body, version):
    """Explicit GIMBAL GET business-response context, not push/version-query data."""
    data = snapshot(body)
    if type(version) is not str or version not in VERSIONS:
        raise ValueError('explicit source version name required')
    old = version == 'Ver1_0'
    if len(data) < (18 if old else 9):
        raise ValueError('incomplete GET business body')
    declared = 10 if old else data[8]
    if declared > 16:
        raise ValueError('source SN length exceeds16; source empty-string fallback is not a valid SN')
    start = 8 if old else 9
    if len(data) < start + declared:
        raise ValueError('incomplete declared GET SN')
    sn = data[start:start + declared]
    return dict(rawBusinessHex=data.hex(), sourceVersion=version,
                sourceGetRequestValue=source_type_value('GET', version),
                activeByte=data[0], activeBit=bool(data[0] & 1), unknownActiveBits=data[0] & 254,
                year=int.from_bytes(data[1:3], 'little'), month=data[3], day=data[4],
                hour=data[5], minute=data[6], second=data[7], dateValidityVerified=False,
                snOffset=start, snLength=declared, snRawHex=sn.hex(), sourceSnText=source_sn_text(sn),
                trailingBodyHex=data[start + declared:].hex(), explicitGetContextRequired=True,
                requestAssociationVerified=False, actualSessionVersionVerified=False,
                targetDeviceVerified=False, activationValidityVerified=False)


def v13_push_view(body):
    data = snapshot(body)
    if len(data) < 23 or data[0] != 51:
        raise ValueError('explicit V13 marker51 and minimum23 bytes required')
    declared = data[22]
    copied = min(declared, len(data) - 23)
    return dict(rawBusinessHex=data.hex(), format='sourceV13', marker=data[0],
                safeCommandType=int.from_bytes(data[1:5], 'little', signed=True),
                nonceHex=data[5:21].hex(), activateModuleCount=data[21],
                deviceNumberDeclaredBytes=declared, deviceNumberCopiedBytes=copied,
                deviceNumberRawHex=data[23:23 + copied].hex(),
                declaredDeviceNumberComplete=copied == declared,
                trailingBodyHex=data[23 + copied:].hex(),
                sourceHandlerMayReplyUserInfo=True, automaticReplyEnabled=False,
                senderAndModuleGateVerified=False, targetDeviceVerified=False,
                activationValidityVerified=False)


def v14_push_view(body):
    data = snapshot(body)
    if len(data) < 143 or data[0] != 54:
        raise ValueError('explicit V14 marker54 and minimum143 bytes required')
    declared = data[140] + int.from_bytes(data[141:143], 'little')
    copied = min(declared, len(data) - 143)
    return dict(rawBusinessHex=data.hex(), format='sourceV14', marker=data[0],
                safeCommandType=int.from_bytes(data[1:5], 'little', signed=True),
                deviceNumberDeclaredBytes=data[5], deviceNumberStorageBytes=32,
                deviceNumberRawHex=data[6:38].hex(), deviceNumberDeclaredWithinStorage=data[5] <= 32,
                moduleType=data[38], moduleNoActivateCount=data[39],
                boardNumberDeclaredBytes=data[40], boardNumberRawHex=data[41:73].hex(),
                boardNumberDeclaredWithinStorage=data[40] <= 32,
                timeInfoRawHex=data[73:105].hex(), userIdDeclaredBytes=data[105],
                userIdRawHex=data[106:138].hex(), userIdDeclaredWithinStorage=data[105] <= 32,
                deviceType=data[138], verifyAlgorithmType=data[139],
                verifyCodeDeclaredBytes=data[140], reservedDeclaredBytes=int.from_bytes(data[141:143], 'little'),
                reservedVerifyDeclaredBytes=declared, reservedVerifyCopiedBytes=copied,
                reservedVerifyRawHex=data[143:143 + copied].hex(),
                declaredReservedVerifyComplete=copied == declared,
                trailingBodyHex=data[143 + copied:].hex(), automaticReplyEnabled=False,
                verificationPerformed=False, senderAndModuleGateVerified=False,
                targetDeviceVerified=False, activationValidityVerified=False)


def check_push_reads(rows):
    """Check both length and ACK constants: the same register is reused for byte reads."""
    by = {off: (op, text) for off, op, text in rows}
    expected = {
        12: ('const/16', 'v1, 11'),
        28: ('const/4', 'v1, 1'),
        156: ('invoke-virtual', 'v5, v3, v1, v0, v2, ' + ROOT + '->get(I I Ljava/lang/Class; [I)Ljava/lang/Number;'),
        248: ('invoke-virtual', 'v5, v1, v0, ' + ROOT + '->getRevertSn(I I)Ljava/lang/String;'),
        300: ('invoke-virtual', 'v5, v1, v1, v6, v0, ' + ROOT + '->get(I I Ljava/lang/Class; [I)Ljava/lang/Number;'),
        344: ('const/4', 'v0, 2'),
        346: ('invoke-virtual', 'v5, v0, v6, ' + ROOT + '->getRevertSn(I I)Ljava/lang/String;'),
        362: ('invoke-static', 'v6, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z'),
        368: ('move-result', 'v6'),
        370: ('sput-boolean', 'v6, ' + ROOT + '->isPushActivated Z'),
    }
    if any(by.get(k) != v for k, v in expected.items()):
        raise ValueError('source push width/SN/empty-flag producer changed')
    # No intervening assignment may change v1 before its byte-read reuse.
    writing_prefixes = ('const', 'move', 'iget', 'sget', 'aget', 'new-', 'add-', 'sub-', 'and-', 'or-', 'int-')
    for off, op, text in rows:
        if 28 < off < 300 and op.startswith(writing_prefixes) and text.split(', ')[0] == 'v1':
            raise ValueError('source v1 width register changed before length read')


def trace(apk, bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest() != APK_SHA256:
        raise ValueError('APK hash mismatch')
    images = {}
    for bank, pin in PREFIX_BANKS.items():
        raw = (bank_dir / ('business-%02d-prefix-code-restored.dex' % bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest() != pin:
            raise ValueError('prefix bank hash mismatch: %02d' % bank)
        images[bank] = raw
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes = {c.get_name(): c for c in DEX(images[5]).get_classes()}
    methods = {}

    def take(owner, name, descriptor=None):
        choices = [m for m in classes[owner].get_methods() if m.get_name() == name and
                   (descriptor is None or m.get_descriptor() == descriptor)]
        if len(choices) != 1 or not choices[0].get_code():
            raise ValueError('missing/ambiguous activation format method ' + owner + name)
        m = choices[0]
        methods[(owner, name, m.get_descriptor())] = dict(className=owner, method=name,
            descriptor=m.get_descriptor(), codeOffset=m.get_code_off(),
            instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
        off = 0
        rows = []
        for i in m.get_instructions():
            rows.append((off, i.get_name(), i.get_output())); off += i.get_length()
        return rows

    def require(rows, *tokens):
        for token in tokens:
            if not any(token in text for _, _, text in rows):
                raise ValueError('missing activation format source token ' + token)

    fields = {f.get_name(): f.get_init_value().get_value() for f in classes[V13].get_fields() if f.get_init_value()}
    if fields != dict(CMD_LEN=4, MINI_LEN=0, NONCE_LEN=16):
        raise ValueError('V13 source static fields changed')
    if take(V13, '<clinit>') != [(0,'const/16','v0, 16'),(4,'add-int/lit8','v0, v0, 4'),(8,'add-int/lit8','v0, v0, 3'),(12,'sput','v0, '+V13+'->MINI_LEN I'),(16,'return-void','')]:
        raise ValueError('V13 minimum length initializer changed')
    require(take(ROOT, 'parseActivationV13'), V13+'->CMD_LEN I', V13+'->NONCE_LEN I',
            'v2, v2, 2', '->device_num_length I', 'Math;->min(I I)I', '->arraycopy(')
    require(take(ROOT, 'parseActivationV14'), 'v3, 143', 'v2, 32', 'v4, 38', 'v4, 39',
            'v4, 40', 'v6, 41', 'v6, 73', 'v4, 105', 'v6, 106', 'v2, 138',
            'v2, 139', 'v2, 140', 'v2, 141', 'v4, 142', 'v4, v4, 8',
            '->reserved_length I', '->verify_code_length I', 'v2, v4', 'v2, v3')
    dispatch = take(ROOT, 'handleVer13Parse')
    require(dispatch, 'v1, 51', 'v1, 54', '->handleDeviceInfoRequest(', '->handleActivateVerifyInfo(')
    by = {off: (op, text) for off, op, text in dispatch}
    if branch_target(24, by[24][1]) != 50 or branch_target(32, by[32][1]) != 38:
        raise ValueError('V13/V14 marker dispatch changed')
    require(take(ROOT, 'handleDeviceInfoRequest'), '->parseActivationV13(', '->module_type_ I',
            '->senderType I', '->module_cnt_ I', '->setUserInfo(')
    require(take(ROOT, 'handleActivateVerifyInfo'), '->parseActivationV14(', '->module_type I',
            '->module_type_ I', '->senderType I', 'PublicActivateBean;-><init>(')
    require(take(ROOT, 'setUserInfo'), 'v0, 135', 'v1, 53', 'UTC', 'GeneralActivationUserInfoV13;->toByteBuffer()',
            '->_sendData [B', '->start(')
    check_push_reads(take(ROOT, 'setPushRecData'))
    for name in ('doPack','getActiveStatus','getYear','getMonth','getDay','getHour','getMin','getSecond','getSN',
                 'getRevertSn','getInvertSn','getIsPushActivated','isGetted','isPushSnAvailable','<init>'):
        take(ROOT, name)
    sn = take(ROOT, 'getRevertSn')
    by = {off: (op, text) for off, op, text in sn}
    if by[38][0] != 'aget-byte' or by[42] != ('const/16','v2, 255'):
        raise ValueError('signed SN byte/255 comparison changed')
    require(sn, 'StringBuilder;->append(I)', '->isNumberOrLetter(B)Z')
    require(take(BASE,'get','(I I Ljava/lang/Class; [I)Ljava/lang/Number;'),
            '->readBytes([B I I)', '->getInt([B)I', 'v6, v6, [B')
    require(take(BYTES,'getInt','([B)I'), 'v0, 4', '->fillBytes([B I)', '->LITTLE_ENDIAN ', 'ByteBuffer;->getInt()I')
    take(BYTES,'fillBytes')
    take(BYTES,'getInt','([B I I)I')
    take(BYTES,'isNumberOrLetter')
    # Pin the actual six ASCII interval endpoints, not Python Unicode alphanumeric.
    intervals = take(BYTES,'<clinit>')
    payloads = [i.get_data() for m in classes[BYTES].get_methods() if m.get_name()=='<clinit>'
                for i in m.get_instructions() if i.get_name()=='fill-array-data-payload']
    expected = b''.join(v.to_bytes(4,'little') for v in (48,57,65,90,97,122))
    if payloads != [expected]:
        raise ValueError('source SN ASCII intervals changed')
    require(intervals, '->INTERVAL [I')
    take(V13,'getDeviceNumString')
    for owner in (V13,V14):take(owner,'<init>')
    for name in ('getInstance','start'):take(GIMBAL,name)
    return dict(schemaVersion=1, apkSha256=APK_SHA256,
        bankSha256={str(b):p for b,p in PREFIX_BANKS.items()}, parsedMethodBanks=[5],
        methods=sorted(methods.values(),key=lambda r:(r['className'],r['method'],r['descriptor'])),
        getResponse=dict(contextRequired=True,sourceGetValues={v:source_type_value('GET',v) for v in VERSIONS},
            activeOffset=0,yearOffset=1,yearBytes=2,monthOffset=3,dayOffset=4,hourOffset=5,minuteOffset=6,secondOffset=7,
            oldSnOffset=8,oldSnBytes=10,otherSnLengthOffset=8,otherSnOffset=9,otherSnMaxBytes=16,
            gimbalForwardStringIsSignedDecimalForNonAsciiAlphanumeric=True,sourceComparesSignedByteTo255=True),
        sourcePushQuirks=dict(minimumBytes=11,dispatchIntegerOffset=0,dispatchIntegerRequestedBytes=1,
            integerResultUsesFirstFourLittleEndianBytes=True,oldPushSnOffset=1,oldPushSnBytes=10,
            newPushSnLengthOffset=1,newPushSnLengthRequestedBytes=1,newPushSnOffset=2,
            newPushActivatedFieldDirectlyStoresTextIsEmpty=True,normalByteFieldInterpretationSubstituted=False,unknownNonlegacyBodySetsSourceVersionVer13=True),
        v13=dict(marker=51,minimumBytes=23,safeCommandOffset=1,safeCommandBytes=4,nonceOffset=5,nonceBytes=16,
            moduleCountOffset=21,deviceNumberLengthOffset=22,deviceNumberOffset=23,sourceTruncatesToAvailable=True),
        v14=dict(marker=54,minimumBytes=143,safeCommandOffset=1,safeCommandBytes=4,deviceNumberLengthOffset=5,
            deviceNumberOffset=6,fixedArrayBytes=32,moduleTypeOffset=38,moduleRemainingCountOffset=39,
            boardLengthOffset=40,boardOffset=41,timeInfoOffset=73,userLengthOffset=105,userOffset=106,
            deviceTypeOffset=138,verifyAlgorithmOffset=139,verifyLengthOffset=140,reservedLengthOffset=141,
            reservedLengthBytes=2,reservedVerifyOffset=143,sourceCombinesReservedAndVerify=True,sourceTruncatesToAvailable=True),
        sourceSideEffects=dict(deviceInfoHandlerCallsSetUserInfo=True,userInfoBodyBytes=135,userInfoMarker=53,
            userInfoUsesUtcCalendar=True,userInfoSendsToIncomingSender=True,verifyHandlerChecksSenderAndModule=True,
            moduleGateRuntimeVerified=False,sourceHandlersExecuted=False,automaticReplyAdded=False),
        sdkSendAdded=False,sdkReceiveAdded=False,targetDeviceVerified=False,hg724EntryEstablished=False,
        actualSessionVersionVerified=False,activationValidityVerified=False,vendorCodeExecuted=False,
        wholeProtocolRecovered=False,networkActivationWorkflowComplete=False,
        remaining=['GET/legacy push/V13/V14/version query are separate contexts, not one auto-detected model.',
                   'Source byte-read register reuse, empty-SN boolean and signed SN rendering are retained.',
                   'V13/V14 generic structures do not prove HG724 routing, activation validity, verification or binding.',
                   'No automatic source user-info reply, SDK interface, network action or device activation is provided.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.bank_dir)
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print('%d methods; GET/V13/V14 source formats only, no handlers or sends.'%len(r['methods']))
if __name__=='__main__':main()
