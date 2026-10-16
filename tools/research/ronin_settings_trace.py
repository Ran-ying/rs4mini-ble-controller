#!/usr/bin/env python3
"""Trace named Ronin settings in the pinned restored view, without executing it."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256

OWNER = 'Ldji/midware/ronin2/Ronin2GimbalParamsManager$BaseCommand;'
BASE = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/'
METHODS = {
    'setCustomFollowModeEnabled': ('CUSTOM_FOLLOW_SETTING', 1, False),
    'setCustomFollowModePitchEnabled': ('CUSTOM_FOLLOW_SETTING', 2, False),
    'setCustomFollowModeRollEnabled': ('CUSTOM_FOLLOW_SETTING', 4, False),
    'setCustomFollowModeYawEnabled': ('CUSTOM_FOLLOW_SETTING', 8, False),
    'setMotorEnabled': ('MOTOR_SPECIAL_CMD', 1, True),
    'setForbidSelfieEnabled': ('MOTOR_SPECIAL_CMD', 16, False),
    'setForbidVerticalShootingEnabled': ('MOTOR_SPECIAL_CMD', 32, False),
    'setRoll360Enabled': ('MOTOR_SPECIAL_CMD', 64, False),
}


def named_keys(operations):
    registers, result = {}, {}
    for op, text in operations:
        if op.startswith('const-string') or op == 'const-class':
            reg, value = text.split(', ', 1)
            registers[reg] = value
        elif op.startswith('const'):
            reg, value = text.split(', ', 1)
            registers[reg] = int(value)
        elif op in ('new-instance', 'move-result-object'):
            registers[text.split(', ')[0]] = None
        elif op.startswith('invoke-direct') and OWNER + '-><init>' in text:
            argtext = text.split(', ' + OWNER)[0]
            regs = re.findall(r'v\d+', argtext)
            if ' ... ' in argtext:
                regs = ['v%d' % n for n in range(int(regs[0][1:]), int(regs[-1][1:]) + 1)]
            if len(regs) not in (4, 5, 6):
                raise ValueError('unexpected parameter-key constructor shape')
            name = registers.get(regs[1])
            key = registers.get(regs[-2] if len(regs) == 6 else regs[-1])
            getter = registers.get(regs[-1]) if len(regs) == 6 else None
            if not isinstance(name, str) or not isinstance(key, str) or name in result:
                raise ValueError('unresolved/duplicate named key')
            result[name] = dict(name=key, getter=getter)
        elif op in ('invoke-static', 'sput-object', 'return-void'):
            continue
        else:
            raise ValueError('unsupported key enum instruction: ' + op)
    return result


def unique_record(records, name):
    matches = [r for r in records if r.get('name') == name]
    if len(matches) != 1:
        raise ValueError('parameter name must resolve to one source record')
    return {k: matches[0][k] for k in ('name', 'index', 'size', 'typeID', 'minValue', 'maxValue')}


def trace(apk, dex_path):
    if hashlib.sha256(apk.read_bytes()).hexdigest() != APK_SHA256:
        raise ValueError('APK hash mismatch')
    raw = dex_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DERIVED_SHA256:
        raise ValueError('restoration view hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes = {c.get_name(): c for c in DEX(raw).get_classes()}
    enum = next(m for m in classes[OWNER].get_methods() if m.get_name() == '<clinit>')
    keys = named_keys([(o.get_name(), o.get_output()) for o in enum.get_instructions()])
    with zipfile.ZipFile(str(apk)) as archive:
        resource = archive.read('res/DB.json')
    records = json.loads(resource)
    parameters = {k: dict(unique_record(records, keys[k]['name']), getter=keys[k]['getter'])
                  for k in ('CUSTOM_FOLLOW_SETTING', 'MOTOR_SPECIAL_CMD')}
    chain = []
    name = BASE + 'DJIGimbalHG724Abstraction;'
    while name.startswith(BASE):
        cls = classes[name]
        chain.append(dict(className=name, superclass=cls.get_superclassname()))
        name = cls.get_superclassname()
    methods = []
    cls = classes[BASE + 'DJIGimbalRonin2Abstraction;']
    for method in cls.get_methods():
        name = method.get_name()
        if name not in METHODS and name != 'setRonin2CommonUserParam':
            continue
        operations = [(o.get_name(), o.get_output()) for o in method.get_instructions()]
        row = dict(method=name, descriptor=method.get_descriptor(), codeOffset=method.get_code_off(),
                   instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest())
        if name in METHODS:
            key, bit, inverted = METHODS[name]
            refs = [text for op, text in operations if op == 'sget-object' and OWNER + '->' + key + ' ' in text]
            ors = [int(text.rsplit(', ', 1)[1]) for op, text in operations if op == 'or-int/lit8']
            ands = [int(text.rsplit(', ', 1)[1]) for op, text in operations if op == 'and-int/lit8']
            if len(refs) != 2 or ors != [bit] or ands != [~bit]:
                raise ValueError('unexpected setting mask/key operations: ' + name)
            if not any('->setRonin2CommonUserParam(' in text for op, text in operations):
                raise ValueError('missing source setter dispatch')
            derived_inverted = next(op for op, text in operations if op in ('or-int/lit8', 'and-int/lit8')) == 'and-int/lit8'
            if derived_inverted != inverted:
                raise ValueError('unexpected branch polarity: ' + name)
            row.update(key=key, bit=bit, inverted=derived_inverted)
        methods.append(row)
    if len(methods) != 9:
        raise ValueError('missing source methods')
    return dict(schemaVersion=1, apkSha256=APK_SHA256, derivedSha256=DERIVED_SHA256,
                resourcePath='res/DB.json', resourceSha256=hashlib.sha256(resource).hexdigest(),
                baseCommandEnumSha256=hashlib.sha256(enum.get_code().get_bc().get_raw()).hexdigest(),
                appCodeExecuted=False, targetDeviceVerified=False, wholeProtocolRecovered=False,
                inheritanceOnlyDoesNotProveFirmwareSupport=True,
                parameterNamesSafeToInferFromWireIndex=False, chain=chain, parameters=parameters, methods=methods)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--dex', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = trace(args.apk, args.dex)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('Two named parameter records and nine method fingerprints; no vendor code executed.')


if __name__ == '__main__':
    main()
