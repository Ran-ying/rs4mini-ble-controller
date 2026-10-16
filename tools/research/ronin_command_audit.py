#!/usr/bin/env python3
"""Fingerprint current-App command methods; never execute vendor code or emit frames.

Optional dependency: androguard==4.1.3. Input is the ignored restoration view.
Output contains hashes/enum references, never full instructions or vendor bodies.
"""
import argparse
import hashlib
import json
from pathlib import Path

DERIVED_SHA256 = '4fdbd74a05df63d72a0feb1c907d9395426ec3cdb5d6aeb45e3836d856d66654'
EXTRA = {
    'Ldji/midware/data/packages/P3/RecvPack;',
    'Ldji/midware/data/packages/P3/SendPack;',
    'Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;',
    'Ldji/midware/data/config/P3/DJICmdSetBase;',
    'Ldji/midware/data/config/P3/Ccode;',
}


def audit(path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DERIVED_SHA256:
        raise ValueError('Input must be the pinned classes6 code-restoration view')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    classes = []
    for cls in DEX(raw).get_classes():
        name = cls.get_name()
        if not ((name.startswith('Ldji/midware/data/model/P3/DataGimbal') and '$' not in name) or name in EXTRA):
            continue
        methods = []
        for method in cls.get_methods():
            code = method.get_code()
            if not code:
                continue
            refs = [op.get_output() for op in method.get_instructions()
                    if op.get_name() == 'sget-object' and 'CmdIdGimbal$CmdIdType;->' in op.get_output()]
            methods.append(dict(method=method.get_name(), descriptor=method.get_descriptor(),
                                codeOffset=method.get_code_off(),
                                instructionSha256=hashlib.sha256(code.get_bc().get_raw()).hexdigest(),
                                commandEnums=refs))
        classes.append(dict(className=name, methods=methods))
    return dict(schemaVersion=1, derivedSha256=DERIVED_SHA256, appCodeExecuted=False,
                targetDeviceVerified=False, inventoryComplete=False,
                classCount=len(classes), methodCount=sum(len(c['methods']) for c in classes), classes=classes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dex', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.dex)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('%d classes, %d method fingerprints; no vendor code executed.' % (report['classCount'], report['methodCount']))


if __name__ == '__main__':
    main()
