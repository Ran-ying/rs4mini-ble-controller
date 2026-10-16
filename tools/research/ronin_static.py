#!/usr/bin/env python3
"""Static metadata inspection of the pinned public Ronin APK. Never executes it.

Derived DEX files are analysis artifacts, not original or runnable app releases.
The SDK has no dependency on this utility or on its optional analysis library.
"""
import argparse
import hashlib
import json
import re
import struct
import zipfile
import zlib
from pathlib import Path

APK_SHA256 = '4ef0aa1e351990168a522500728790e22794618b0bcbd4c6277c7375148dc4f4'
MAP_TYPES = set(range(9)) | {0x1000, 0x1001, 0x1002, 0x1003} | set(range(0x2000, 0x2007)) | {0xf000}


def uleb(data, offset):
    value = 0
    for shift in range(0, 35, 7):
        if offset >= len(data):
            raise ValueError('truncated ULEB128')
        byte = data[offset]
        offset += 1
        if shift == 28 and byte > 15:
            raise ValueError('ULEB128 overflows uint32')
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise ValueError('unterminated ULEB128')


def maps_in(data):
    needle = struct.pack('<HHIIHH', 0, 0, 1, 0, 1, 0)
    found, offset = [], 0
    while True:
        pos = data.find(needle, offset)
        if pos < 0:
            return found
        offset = pos + 1
        if pos < 4:
            continue
        count = struct.unpack_from('<I', data, pos - 4)[0]
        if not 10 <= count <= 24 or pos + count * 12 > len(data):
            continue
        rows = [struct.unpack_from('<HHII', data, pos + i * 12) for i in range(count)]
        if any(unused or typ not in MAP_TYPES or item_offset >= len(data) for typ, unused, size, item_offset in rows):
            continue
        items = {typ: (size, item_offset) for typ, unused, size, item_offset in rows}
        required = set(range(7)) | {0x1000, 0x2002}
        if len(items) != count or not required <= items.keys():
            continue
        if items[0x1000][0] != 1:
            continue
        base = pos - 4 - items[0x1000][1]
        if base > 0 and items[0] == (1, 0) and items[1][1] == 112:
            found.append(dict(base=base, mapOffset=items[0x1000][1], items=items))


def recover(data, output):
    records = maps_in(data)
    report = []
    for index, record in enumerate(records):
        base = record['base']
        end = records[index + 1]['base'] if index + 1 < len(records) else len(data)
        chunk = bytearray(data[base:end])
        items = record['items']
        count, string_ids = items[1]
        string_count, pos = items[0x2002]
        if count != string_count or string_ids + count * 4 > len(chunk):
            raise ValueError('invalid string map')
        offsets = []
        for _ in range(count):
            offsets.append(pos)
            _, text_start = uleb(chunk, pos)
            stop = chunk.find(0, text_start)
            if stop < 0:
                raise ValueError('unterminated MUTF-8 string')
            pos = stop + 1
        old = struct.unpack_from('<%dI' % count, chunk, string_ids)
        bad = [i for i, (a, b) in enumerate(zip(old, offsets)) if a != b]
        # Pinned image evidence: only the first 128 KiB are damaged. Require an
        # unchanged suffix to corroborate physical string order before recovery.
        tail = [i for i in range(count) if string_ids + i * 4 >= 0x20000]
        readable = bool(tail) and all(old[i] == offsets[i] for i in tail)
        result = dict(index=index, base=base, size=len(chunk), stringCount=count,
                      unchangedStringIds=count - len(bad), structurallyReadable=readable,
                      lastDamagedStringIdOffset=string_ids + max(bad) * 4 if bad else None)
        if readable:
            if any(string_ids + i * 4 >= 0x20000 for i in bad):
                raise ValueError('damage outside observed prefix')
            chunk[:112] = bytes(112)
            chunk[:8] = b'dex\n039\0'
            struct.pack_into('<6I', chunk, 32, len(chunk), 112, 0x12345678, 0, 0, record['mapOffset'])
            for typ, header_offset in [(1, 56), (2, 64), (3, 72), (4, 80), (5, 88), (6, 96)]:
                struct.pack_into('<II', chunk, header_offset, *items[typ])
            data_start = min(item[1] for typ, item in items.items() if typ >= 0x1000)
            struct.pack_into('<II', chunk, 104, len(chunk) - data_start, data_start)
            struct.pack_into('<%dI' % count, chunk, string_ids, *offsets)
            chunk[12:32] = hashlib.sha1(chunk[32:]).digest()
            struct.pack_into('<I', chunk, 8, zlib.adler32(chunk[12:]) & 0xffffffff)
            name = 'business-%02d.dex' % index
            (output / name).write_bytes(chunk)
            result.update(file=name, derivedSha256=hashlib.sha256(chunk).hexdigest())
        report.append(result)
    return report


def analyze(dex_file):
    # Optional research tooling only; importing/parsing DEX does not run app code.
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    dex = DEX(dex_file.read_bytes())
    enum = 'Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;'
    entries, methods, evidence = [], [], {}
    for cls in dex.get_classes():
        name = cls.get_name()
        if name == enum:
            method = next(m for m in cls.get_methods() if m.get_name() == '<clinit>')
            evidence = dict(className=name, method='<clinit>', codeOffset=method.get_code_off(),
                            instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest())
            registers, offset = {}, 0
            for ins in method.get_instructions():
                op, text = ins.get_name(), ins.get_output()
                if op.startswith(('if-', 'goto')):
                    raise ValueError('unsupported enum control flow')
                if op.startswith('const-string'):
                    match = re.fullmatch(r'v(\d+), (.*)', text)
                    registers[int(match[1])] = match[2]
                elif op in ('const/4', 'const/16', 'const'):
                    match = re.fullmatch(r'v(\d+), (-?\d+)', text)
                    registers[int(match[1])] = int(match[2])
                elif op.startswith('move-object'):
                    a, b = re.findall(r'v(\d+)', text)
                    registers[int(a)] = registers.get(int(b))
                elif op.startswith('invoke-direct') and enum + '-><init>' in text:
                    args = text.split(', ' + enum)[0]
                    regs = [int(r) for r in re.findall(r'v(\d+)', args)]
                    if ' ... ' in args:
                        regs = list(range(regs[0], regs[1] + 1))
                    label, ordinal, value = [registers[r] for r in regs[1:4]]
                    if not isinstance(label, str) or type(ordinal) is not int or type(value) is not int:
                        raise ValueError('unresolved enum constructor')
                    entries.append(dict(name=label, ordinal=ordinal, value=value,
                                        wireValue=0 <= value <= 255, instructionOffset=offset))
                offset += ins.get_length()
        if name.startswith('Ldji/midware/data/model/P3/DataGimbal') or name == 'Ldji/midware/data/model/P3/DataCommonGetVersion;':
            for method in cls.get_methods():
                if method.get_name() not in ('doPack', 'start', 'setRecData', 'getFirmVer', 'getLoader', 'getType'):
                    continue
                ops = [ins.get_name() for ins in method.get_instructions()]
                stub = len(ops) > 4 and ops[0] == 'nop' and all(op in {'nop', 'const', 'const/4', 'return', 'return-object', 'return-void', 'return-wide', 'const-wide/16'} for op in ops)
                methods.append(dict(className=name, method=method.get_name(), descriptor=method.get_descriptor(),
                                    codeOffset=method.get_code_off(), protectedStubCandidate=stub,
                                    instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest() if method.get_code() else None))
    return dict(enumEvidence=evidence, enumEntries=entries, methods=methods)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Use an ignored work/ directory')
    parser.add_argument('--analyze', action='store_true', help='Requires optional androguard==4.1.3')
    args = parser.parse_args()
    digest = hashlib.sha256(args.apk.read_bytes()).hexdigest()
    if digest != APK_SHA256:
        parser.error('APK hash differs from the inspected official 2.2.2/7096 file')
    args.output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(args.apk)) as archive:
        records = recover(archive.read('classes.dex'), args.output)
        resources = []
        for name in ('res/DB.json', 'res/jy.json'):
            raw = archive.read(name)
            values = json.loads(raw)
            indexes = {}
            for row in values:
                indexes.setdefault(row['index'], []).append(row['name'])
            resources.append(dict(path=name, sha256=hashlib.sha256(raw).hexdigest(), entries=len(values),
                                  duplicateIndexes={str(k): v for k, v in indexes.items() if len(v) > 1}))
    report = dict(source='https://www.dji.com/downloads/djiapp/dji-ronin', apkSha256=digest,
                  originalMethodsRestored=False, recoveredMetadata=records, parameterResources=resources)
    if args.analyze:
        report['analysis'] = analyze(args.output / 'business-05.dex')
    (args.output / 'evidence.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Static metadata: %d segments; %d structurally readable. Original protected methods are not restored.' % (len(records), sum(r['structurallyReadable'] for r in records)))


if __name__ == '__main__':
    main()
