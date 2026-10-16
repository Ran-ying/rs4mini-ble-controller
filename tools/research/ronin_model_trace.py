#!/usr/bin/env python3
"""Static HG724 identity/metadata trace of the pinned Ronin APK. No execution.

Optional Androguard is loaded only after checking the original APK hash.
The output is a research report, never a device-control configuration.
"""
import argparse
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from ronin_static import APK_SHA256, recover

TARGETS = {
    'business-03.dex': {'Lcom/dji/ronin/ui/entry/DeviceSwitchTextView;'},
    'business-05.dex': {
        'Ldji/midware/ble2/RoninBluetoothConst;',
        'Ldji/midware/data/model/P3/DataGimbalGetPushType$DJIGimbalType;',
        'Ldji/midware/data/manager/P3/DJIGimbalParamInfoManager;',
        'Ldji/midware/data/manager/P3/DJIGimbalParamInfoManager$1;',
        'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalHG724Abstraction;',
        'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalHG702Abstraction;',
    },
}
STUB_OPS = {'nop', 'const', 'const/4', 'return', 'return-object', 'return-void', 'return-wide', 'const-wide/16'}


def protected_stub(operations):
    return len(operations) > 4 and operations[0] == 'nop' and all(op in STUB_OPS for op in operations)


def enum_entry(operations, owner, wanted):
    """Narrow constant/register inspection; never calls constructor/app code."""
    registers, entries = {}, []
    for op, text in operations:
        if op.startswith(('if-', 'goto')) or 'switch' in op:
            raise ValueError('unsupported enum control flow')
        if op.startswith('const-string'):
            match = re.fullmatch(r'v(\d+), (.*)', text)
            if not match:
                raise ValueError('unresolved string constant')
            registers[int(match[1])] = match[2]
        elif op in ('const/4', 'const/16', 'const'):
            match = re.fullmatch(r'v(\d+), (-?\d+)', text)
            if not match:
                raise ValueError('unresolved integer constant')
            registers[int(match[1])] = int(match[2])
        elif op.startswith(('move-object', 'move/')):
            a, b = re.findall(r'v(\d+)', text)
            registers[int(a)] = registers.get(int(b))
        elif op.startswith('invoke-direct') and owner + '-><init>(Ljava/lang/String; I I)V' in text:
            args = text.split(', ' + owner)[0]
            regs = [int(r) for r in re.findall(r'v(\d+)', args)]
            if ' ... ' in args:
                regs = list(range(regs[0], regs[-1] + 1))
            if len(regs) != 4:
                raise ValueError('unsupported enum constructor shape')
            label, ordinal, value = [registers.get(r) for r in regs[1:]]
            if label == wanted:
                if type(ordinal) is not int or type(value) is not int:
                    raise ValueError('unresolved enum value')
                entries.append(dict(name=label, ordinal=ordinal, value=value))
        elif op in ('new-instance', 'move-result-object', 'sget-object'):
            destination = re.match(r'v(\d+)', text)
            if destination:
                registers[int(destination[1])] = None
        elif op.startswith(('sput-object', 'invoke-static')) or op == 'return-void':
            pass
        else:
            raise ValueError('unsupported enum instruction: ' + op)
    if len(entries) != 1:
        raise ValueError('expected exactly one target enum entry')
    return entries[0]


def raw_resource_facts(public_xml, resolve):
    """Record raw-table names/paths, without inferring the active model table."""
    result = []
    for item in ET.fromstring(public_xml):
        if item.get('type') != 'raw':
            continue
        resource_id = int(item.get('id'), 16)
        for value in resolve(resource_id):
            if value in ('res/DB.json', 'res/jy.json'):
                result.append(dict(id=resource_id, name=item.get('name'), path=value))
    return result


def inspect_apk(apk, output):
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    if digest != APK_SHA256:
        raise ValueError('APK hash differs from inspected Ronin 2.2.2/7096')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    from androguard.core.axml import ARSCParser
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(apk)) as archive:
        recovery = recover(archive.read('classes.dex'), output)
        resources = ARSCParser(archive.read('resources.arsc'))
        facts = []
        for package in resources.get_packages_names():
            rows = raw_resource_facts(resources.get_public_resources(package),
                                      lambda rid: [value for config, value in resources.get_resolved_res_configs(rid)])
            facts.extend(dict(package=package, **row) for row in rows)
    classes = []
    for filename, targets in TARGETS.items():
        dex = DEX((output / filename).read_bytes())
        found = set()
        for cls in dex.get_classes():
            if cls.get_name() not in targets:
                continue
            found.add(cls.get_name())
            methods = []
            for method in cls.get_methods():
                if not method.get_code():
                    continue
                operations = [(op.get_name(), op.get_output()) for op in method.get_instructions()]
                raw = method.get_code().get_bc().get_raw()
                references = [dict(op=op, operand=text) for op, text in operations
                              if any(token in text for token in ('HG724', 'DJI RS 4 Mini', 'dji rs4 mini-', 'FollowModeSensitivity', 'DeviceTextViewItem;-><init>', 'RoninBluetoothConst;-><init>'))]
                record = dict(name=method.get_name(), descriptor=method.get_descriptor(),
                              codeOffset=method.get_code_off(), instructionSha256=hashlib.sha256(raw).hexdigest(),
                              protectedStubCandidate=protected_stub([op for op, text in operations]), references=references)
                if cls.get_name().endswith('DJIGimbalType;') and method.get_name() == '<clinit>':
                    record['hg724Enum'] = enum_entry(operations, cls.get_name(), 'HG724')
                methods.append(record)
            classes.append(dict(file=filename, name=cls.get_name(), superclass=cls.get_superclassname(), methods=methods))
        if found != targets:
            raise ValueError('required identity/abstraction classes missing')
    return dict(apkSha256=digest, source='https://www.dji.com/downloads/djiapp/dji-ronin',
                targetDeviceVerified=False, wireCommandBranchRecovered=False,
                parameterResourceSelectionRecovered=False, originalProtectedMethodsRestored=False,
                recovery=recovery, classes=classes, rawParameterResources=facts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='Use ignored work/ output')
    args = parser.parse_args()
    report = inspect_apk(args.apk, args.output)
    (args.output / 'model-evidence.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Static identity trace: %d classes; no wire-command branch or parameter selector recovered.' % len(report['classes']))


if __name__ == '__main__':
    main()
