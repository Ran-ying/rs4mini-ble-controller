#!/usr/bin/env python3
"""Eight-bank PREFIX re-audit for 04:14 / 04:0C / 04:4C motion routes; offline only."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS

MODEL = 'Ldji/midware/data/model/P3/'
SPEED = MODEL + 'DataGimbalSpeedControl;'
ABS = MODEL + 'DataGimbalAbsAngleControl;'
RESET = MODEL + 'DataGimbalNewResetAndSetMode;'
ROOT = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalAbstraction;'
HG724 = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalHG724Abstraction;'
CTRL = 'Lcom/dji/ronin/ui/create/follow/RoninGimbalControler;'
FOCUS = 'Lcom/dji/ronin/ui/create/focus/CreateFocusMotorControlView;'
OWNERS = {'0C': SPEED, '14': ABS, '4C': RESET}


def source_speed_body(yaw, roll, pitch, *, permission, multi_control):
    """Current-App SpeedControl doPack: yaw/roll/pitch uint16 LE then flag byte."""
    for name, value in (('yaw', yaw), ('roll', roll), ('pitch', pitch)):
        if type(value) is not int or not -2147483648 <= value <= 2147483647:
            raise ValueError('explicit Java int ' + name + ' required')
    if type(permission) is not bool or type(multi_control) is not bool:
        raise ValueError('explicit booleans required')
    body = bytearray(7)
    for offset, value in ((0, yaw), (2, roll), (4, pitch)):
        body[offset:offset + 2] = struct.pack('<H', value & 0xffff)
    flag = (int(permission) << 7) | int(multi_control)
    body[6] = flag & 0xff
    return bytes(body)


def source_speed_units(value):
    """rotate SPEED path: float-to-int then multiply by 10 (not float32*10)."""
    if type(value) not in (float, int):
        raise ValueError('numeric source speed required')
    number = int(value)  # Java float-to-int toward zero for finite values in checked tests
    return number * 10


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
    methods = {}
    hg724_overrides = []
    per_axis_string_hits = []
    ctrl_send = None
    ctrl_stop = None
    speed_dopack = None
    rotate_speed = None

    def take(bank, classes, owner, name, descriptor=None):
        ms = [m for m in classes[owner].get_methods() if m.get_name() == name and (descriptor is None or m.get_descriptor() == descriptor)]
        if len(ms) != 1 or not ms[0].get_code():
            raise ValueError('missing/ambiguous ' + owner + name)
        m = ms[0]
        key = (bank, owner, name, m.get_descriptor())
        methods[key] = dict(
            bank=bank, className=owner, method=name, descriptor=m.get_descriptor(),
            codeOffset=m.get_code_off(),
            instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest(),
        )
        rows = []
        off = 0
        for i in m.get_instructions():
            rows.append((off, i.get_name(), i.get_output()))
            off += i.get_length()
        return rows

    for bank, raw in images:
        dex = DEX(raw)
        classes = {c.get_name(): c for c in dex.get_classes()}
        coded = 0
        total = 0
        instructions = 0
        for owner, cls in classes.items():
            if HG724 == owner:
                names = {m.get_name() for m in cls.get_methods()}
                for name in ('rotate', 'resetGimbal', 'setGimbalMode'):
                    if name in names:
                        hg724_overrides.append(dict(bank=bank, method=name))
            for method in cls.get_methods():
                total += 1
                if not method.get_code():
                    continue
                coded += 1
                off = 0
                for instruction in method.get_instructions():
                    op, text = instruction.get_name(), instruction.get_output()
                    instructions += 1
                    if op.startswith('invoke-'):
                        for key, target in OWNERS.items():
                            if target + '->' in text and owner != target:
                                external[key].append(dict(
                                    segment=bank, className=owner, method=method.get_name(),
                                    descriptor=method.get_descriptor(), target=target,
                                    cameraOrFocusRelated=('focus' in owner.lower() or 'uvc' in owner.lower() or 'camera' in owner.lower() or 'monitor' in owner.lower() or 'DT501' in owner or owner == FOCUS or 'Uvc' in method.get_name() or 'Camera' in method.get_name()),
                                ))
                    off += instruction.get_length()
        for s in dex.get_strings():
            t = str(s)
            if any(k in t for k in ('ResetYaw', 'ResetPitch', 'ResetRoll', 'recenterAxis', 'AxisReset', 'resetPan', 'resetTilt')):
                per_axis_string_hits.append(dict(segment=bank, string=t))
        if bank == 5 and SPEED in classes:
            rows = take(bank, classes, SPEED, 'doPack', '()V')
            texts = [t for _, _, t in rows]
            required = [
                SPEED + '->yaw I', SPEED + '->roll I', SPEED + '->pitch I',
                'getUnsignedBytes(I)', SPEED + '->isGetPermission Z', SPEED + '->multiControl Z',
                'v0, 7',
            ]
            if not all(any(token in t for t in texts) for token in required):
                raise ValueError('SpeedControl doPack layout changed')
            # offsets: yaw at 0, roll copy dest 2, pitch dest 4, flag index 6
            if not any('v3, 0' in t for t in texts) or not any('v4, 2' in t for t in texts) or not any('v5, 4' in t for t in texts) or not any('v2, 6' in t for t in texts):
                raise ValueError('SpeedControl doPack offsets changed')
            speed_dopack = dict(
                bodyBytes=7, axisOrder=['yaw', 'roll', 'pitch'], axisEncoding='uint16-le-from-int-low16',
                permissionBit=7, multiControlBit=0, instructionSha256=methods[(5, SPEED, 'doPack', '()V')]['instructionSha256'],
            )
            rotate = take(bank, classes, ROOT, 'rotate')
            rotate_texts = [t for _, _, t in rotate]
            if not any('RotationMode;->SPEED ' in t for t in rotate_texts) or not any(SPEED + '->setPitch(I)' in t for t in rotate_texts):
                raise ValueError('rotate SPEED path missing')
            if not any('mul-int/lit8' in (op + ' ' + t) and ', 10' in t for _, op, t in rotate):
                raise ValueError('rotate SPEED float-to-int*10 scaling missing')
            if not any('justSendPauseData' in t for t in rotate_texts):
                raise ValueError('rotate still depends on pause helper')
            rotate_speed = dict(
                scalesWithFloatToIntThenMul10=True,
                float32TimesTenPath=False,
                stillCallsJustSendPauseData=True,
                instructionSha256=methods[(5, ROOT, 'rotate', next(d for (b, o, n, d) in methods if b == 5 and o == ROOT and n == 'rotate'))]['instructionSha256'],
            )
            take(bank, classes, ABS, 'doPack')
            take(bank, classes, RESET, 'doPack')
        if bank == 3 and CTRL in classes:
            send = take(bank, classes, CTRL, 'send', '()V')
            stop = take(bank, classes, CTRL, 'stop', '()V')
            send_texts = [t for _, _, t in send]
            stop_texts = [t for _, _, t in stop]
            ctrl_send = dict(
                setsPermission=any('setPermission(Z)' in t for t in send_texts),
                setsYaw=any('setYaw(I)' in t for t in send_texts),
                setsPitch=any('setPitch(I)' in t for t in send_texts),
                setsRoll=any('setRoll(I)' in t for t in send_texts),
                callsStart=any(SPEED + '->start()V' in t for t in send_texts),
                instructionSha256=methods[(3, CTRL, 'send', '()V')]['instructionSha256'],
            )
            ctrl_stop = dict(
                setsPermission=any('setPermission(Z)' in t for t in stop_texts),
                setsYaw=any('setYaw(I)' in t for t in stop_texts),
                setsPitch=any('setPitch(I)' in t for t in stop_texts),
                setsRoll=any('setRoll(I)' in t for t in stop_texts),
                callsStart=any(SPEED + '->start()V' in t for t in stop_texts),
                zerosAxesBeforeStart=False,
                note='stop() only setPermission+start in scanned body; prior yaw/pitch/roll fields may remain',
                instructionSha256=methods[(3, CTRL, 'stop', '()V')]['instructionSha256'],
            )
            if ctrl_send['setsRoll'] or not (ctrl_send['setsYaw'] and ctrl_send['setsPitch'] and ctrl_send['setsPermission']):
                raise ValueError('RoninGimbalControler.send axis usage changed')
            if ctrl_stop['setsYaw'] or ctrl_stop['setsPitch'] or ctrl_stop['setsRoll']:
                raise ValueError('RoninGimbalControler.stop unexpectedly writes axes')
        banks.append(dict(segment=bank, derivedSha256=PREFIX_BANKS[bank], methodCount=total, methodWithCodeCount=coded, instructionCount=instructions))
        print('bank%02d: %d coded, %d instructions' % (bank, coded, instructions), flush=True)

    def unique(rows):
        seen = set()
        out = []
        for row in rows:
            key = (row['segment'], row['className'], row['method'], row['descriptor'], row['target'])
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
        return out

    for key in external:
        external[key] = unique(external[key])

    if speed_dopack is None or rotate_speed is None or ctrl_send is None or ctrl_stop is None:
        raise ValueError('required SpeedControl / UI evidence missing')

    reset_non_camera = [r for r in external['4C'] if not r['cameraOrFocusRelated']]
    speed_non_flight = [r for r in external['0C'] if 'flightcontroller' not in r['className'].lower()]

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
        methods=sorted(methods.values(), key=lambda r: (r['bank'], r['className'], r['method'], r['descriptor'])),
        hg724OverridesOfRotateOrReset=hg724_overrides,
        perAxisResetStringHits=per_axis_string_hits,
        command0C=dict(
            key='04:0C',
            modelClass=SPEED,
            sourceDoPack=speed_dopack,
            rotateSpeedPath=rotate_speed,
            roninUiController=dict(className=CTRL, send=ctrl_send, stop=ctrl_stop),
            externalDirectCallers=external['0C'],
            nonFlightExternalCallers=speed_non_flight,
            vectors={
                'permissionOnly': source_speed_body(0, 0, 0, permission=True, multi_control=False).hex(),
                'yaw10roll20pitch30': source_speed_body(10, 20, 30, permission=True, multi_control=False).hex(),
                'multiControl': source_speed_body(0, 0, 0, permission=False, multi_control=True).hex(),
            },
            unitScaleExample=dict(inputFloat=1.9, floatToIntThenMul10=source_speed_units(1.9)),
            currentAppSourceLayoutEstablished=True,
            hg724DedicatedEntryEstablished=False,
            eyeOrPauseDependencyResolvedForDirectBle=False,
            releaseSemanticsVerified=False,
            targetDeviceVerified=False,
            sendOpened=False,
            replacesExistingVelocity04_01=False,
        ),
        command14=dict(
            key='04:14',
            modelClass=ABS,
            externalDirectCallers=external['14'],
            onlyBaseRotateCaller=all(r['className'] == ROOT and r['method'] == 'rotate' for r in external['14']) and bool(external['14']),
            hg724OverridesRotate=False,
            eyePauseDependencyResolvedForDirectBle=False,
            liveIndexAddressVerified=False,
            referenceFrameVerified=False,
            completionOrAbortVerified=False,
            sendOpened=False,
        ),
        command4C=dict(
            key='04:4C',
            modelClass=RESET,
            externalDirectCallers=external['4C'],
            nonCameraFocusExternalCallers=reset_non_camera,
            perAxisResetEvidenceFound=False,
            workModeEnumStillNotAxisReset=True,
            priorFe01UiPathsRetained=True,
            sendOpened=False,
            specialControlNotPromoted=True,
        ),
        newBanks01And07=dict(
            externalDirectCallers=[r for key in external for r in external[key] if r['segment'] in (1, 7)],
            hg724Overrides=hg724_overrides,
            perAxisResetStringHits=[h for h in per_axis_string_hits if h['segment'] in (1, 7)],
        ),
        remaining=[
            '04:0C now has current-App yaw/roll/pitch uint16 LE + flag layout and Ronin UI send/stop quirks; still not an HG724-dedicated or hardware-verified native-rate SDK.',
            '04:14 external callers remain base rotate only; EYE/SINGLE pause dependency, live index/address, frame and completion stay open.',
            '04:4C eight-bank callers expand UI/FPV/focus/UVC paths; no per-axis reset evidence; keep FE01 three-axis recenter and do not emit SpecialControl mixes.',
            'Do not replace host 04:01 velocity with 04:0C, and do not open 14/0C sends under current gates.',
        ],
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('apk', 'bank-dir', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    result = scan(a.apk, a.bank_dir)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('0C callers=%d; 14 callers=%d; 4C callers=%d; per-axis strings=%d; no SDK send.' % (
        len(result['command0C']['externalDirectCallers']),
        len(result['command14']['externalDirectCallers']),
        len(result['command4C']['externalDirectCallers']),
        len(result['perAxisResetStringHits']),
    ))


if __name__ == '__main__':
    main()
