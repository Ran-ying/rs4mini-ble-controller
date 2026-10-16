#!/usr/bin/env python3
"""Read pinned DJI provided-JAR class bytes. Never loads or executes Java code.

This is a research inspector, not a JVM verifier, decompiler, or BLE SDK.
Return prefixes and unreachable tails are preserved; no bytecode is patched.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

JAR_SHA256 = 'f253d8ef033423132d35c28d5c0da0aade2e660d18f1994c56dec630e3f48f20'
SOURCE = 'https://repo.maven.apache.org/maven2/com/dji/dji-sdk-provided/4.18/dji-sdk-provided-4.18.jar'
# Pinned artifact hash above intentionally checked before opening its ZIP.
MODEL = 'dji/midware/data/model/P3/'
TARGETS = [MODEL + name for name in (
    'DataGimbalNewResetAndSetMode', 'DataGimbalNewResetAndSetMode$ReturnCenterCmd',
    'DataGimbalControl$MODE', 'DataGimbalRoninGetUserParams', 'DataGimbalGetHandleParams',
    'DataGimbalSetHandleParams')] + [
    'dji/midware/data/packages/P3/gfd', 'dji/midware/data/config/P3/CmdIdGimbal$CmdIdType',
    'dji/midware/data/manager/P3/DataBase']


class Reader:
    def __init__(self, data):
        self.data, self.position = data, 0

    def read(self, length):
        if length < 0 or self.position + length > len(self.data):
            raise ValueError('truncated classfile')
        value = self.data[self.position:self.position + length]
        self.position += length
        return value

    def integer(self, width):
        return int.from_bytes(self.read(width), 'big')

    def u1(self):
        return self.integer(1)

    def u2(self):
        return self.integer(2)

    def u4(self):
        return self.integer(4)

    def finish(self):
        if self.position != len(self.data):
            raise ValueError('unexpected trailing classfile data')


def parse_class(raw):
    r = Reader(raw)
    if r.u4() != 0xcafebabe:
        raise ValueError('invalid classfile magic')
    minor, major = r.u2(), r.u2()
    if (minor, major) != (0, 52):
        raise ValueError('only inspected Java 8 classfiles are supported')
    pool = [None] * r.u2()
    i = 1
    while i < len(pool):
        tag = r.u1()
        if tag == 1:
            # Protocol identifiers are ASCII. Non-ASCII MUTF-8 is escaped, not
            # interpreted as an identifier or used to infer encrypted strings.
            value = r.read(r.u2()).decode('ascii', 'backslashreplace')
        elif tag in (3, 4):
            value = r.read(4).hex()
        elif tag in (5, 6):
            value = r.read(8).hex()
        elif tag in (7, 8, 16):
            value = r.u2()
        elif tag in (9, 10, 11, 12, 18):
            value = (r.u2(), r.u2())
        elif tag == 15:
            value = (r.u1(), r.u2())
        else:
            raise ValueError('unsupported constant-pool tag')
        pool[i] = (tag, value)
        i += 2 if tag in (5, 6) else 1
        if i > len(pool):
            raise ValueError('invalid wide constant-pool slot')

    def resolve(index, trail=()):
        if not 0 < index < len(pool) or pool[index] is None or index in trail:
            raise ValueError('invalid/cyclic constant-pool reference')
        tag, value = pool[index]
        if tag in (7, 8, 16):
            return resolve(value, trail + (index,))
        if tag in (9, 10, 11, 12):
            return [resolve(v, trail + (index,)) for v in value]
        return value

    def attributes(reader):
        return [(resolve(reader.u2()), reader.read(reader.u4())) for _ in range(reader.u2())]

    r.u2()  # access flags
    name, parent = resolve(r.u2()), r.u2()
    if parent:
        resolve(parent)
    for _ in range(r.u2()):
        resolve(r.u2())
    fields, methods = [], []
    for group in (fields, methods):
        for _ in range(r.u2()):
            flags, label, descriptor = r.u2(), resolve(r.u2()), resolve(r.u2())
            row = dict(name=label, descriptor=descriptor, flags=flags)
            for key, value in attributes(r):
                if key == 'Code':
                    code_reader = Reader(value)
                    code_reader.u2()  # max stack
                    code_reader.u2()  # max locals
                    code = code_reader.read(code_reader.u4())
                    for _ in range(code_reader.u2()):
                        code_reader.read(8)  # exception table
                    attributes(code_reader)
                    code_reader.finish()
                    row['code'] = code
            group.append(row)
    attributes(r)
    r.finish()
    return dict(name=name, fields=fields, methods=methods, resolve=resolve)


# Only standard instruction boundaries and CP operands are decoded. No operand
# stack, method call, string decryptor, or app logic is executed.
ONE = {16, 18, 21, 22, 23, 24, 25, 54, 55, 56, 57, 58, 169, 188}
TWO = {17, 19, 20, 132, 178, 179, 180, 181, 182, 183, 184, 187, 189, 192, 193, 198, 199} | set(range(153, 169))
CP = {18, 19, 20, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 189, 192, 193, 197}
BRANCH = set(range(153, 169)) | {198, 199, 200, 201}


def instructions(code, resolve):
    r, rows = Reader(code), []
    while r.position < len(code):
        offset, opcode = r.position, r.u1()
        if opcode > 201:
            raise ValueError('reserved/unknown bytecode opcode')
        width = 1 if opcode in ONE else 2 if opcode in TWO else 0
        if opcode in (185, 186, 200, 201):
            width = 4
        elif opcode == 197:
            width = 3
        elif opcode in (170, 171):
            r.read((-r.position) % 4)
            default = int.from_bytes(r.read(4), 'big', signed=True)
            if opcode == 170:
                low, high = struct.unpack('>ii', r.read(8))
                if high < low:
                    raise ValueError('invalid tableswitch range')
                count = high - low + 1
                targets = [int.from_bytes(r.read(4), 'big', signed=True) for _ in range(min(count, len(code) // 4 + 1))]
                if len(targets) != count:
                    raise ValueError('oversize tableswitch')
            else:
                count = int.from_bytes(r.read(4), 'big', signed=True)
                if not 0 <= count <= len(code) // 8:
                    raise ValueError('invalid lookupswitch count')
                targets = [struct.unpack('>ii', r.read(8))[1] for _ in range(count)]
            rows.append(dict(offset=offset, opcode=opcode, targets=[offset + t for t in [default] + targets]))
            continue
        elif opcode == 196:
            modified = r.u1()
            if modified not in {21, 22, 23, 24, 25, 54, 55, 56, 57, 58, 132, 169}:
                raise ValueError('invalid wide opcode')
            r.read(4 if modified == 132 else 2)
            rows.append(dict(offset=offset, opcode=opcode))
            continue
        operands = r.read(width)
        row = dict(offset=offset, opcode=opcode)
        if opcode in CP:
            row['reference'] = resolve(int.from_bytes(operands[:1 if opcode == 18 else 2], 'big'))
        if opcode in BRANCH:
            row['targets'] = [offset + int.from_bytes(operands, 'big', signed=True)]
        if 2 <= opcode <= 8:
            row['literal'] = opcode - 3
        elif opcode in (16, 17):
            row['literal'] = int.from_bytes(operands, 'big', signed=True)
        rows.append(row)
    boundaries = {row['offset'] for row in rows}
    if any(target not in boundaries for row in rows for target in row.get('targets', [])):
        raise ValueError('branch target is not an instruction boundary')
    return rows


def enum_values(cls):
    method = next(m for m in cls['methods'] if m['name'] == '<clinit>')
    rows = instructions(method['code'], cls['resolve'])
    if any(row['opcode'] in BRANCH | {170, 171, 169, 196} for row in rows):
        raise ValueError('unsupported enum control flow')
    result = []
    for i, row in enumerate(rows):
        reference = row.get('reference')
        if row['opcode'] != 183 or reference != [cls['name'], ['<init>', '(Ljava/lang/String;II)V']]:
            continue
        if i < 2 or i + 1 >= len(rows):
            raise ValueError('unresolved enum constructor')
        ordinal, value = rows[i - 2].get('literal'), rows[i - 1].get('literal')
        after = rows[i + 1]
        field = after.get('reference')
        if (ordinal != len(result) or value is None or after['opcode'] != 179
                or not isinstance(field, list) or len(field) != 2 or field[0] != cls['name']):
            raise ValueError('unresolved enum constructor constants/field')
        result.append(dict(name=field[1][0], ordinal=ordinal, value=value))
    if not result:
        raise ValueError('no supported enum constructors')
    return result


def inspect_jar(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != JAR_SHA256:
        raise ValueError('provided JAR hash differs from inspected 4.18 artifact')
    classes = []
    with zipfile.ZipFile(str(path)) as archive:
        for name in TARGETS:
            raw = archive.read(name + '.class')
            cls = parse_class(raw)
            if cls['name'] != name:
                raise ValueError('class identity mismatch')
            methods = []
            for method in cls['methods']:
                code = method.get('code')
                if code is None:
                    continue
                rows = instructions(code, cls['resolve'])
                prefix = next((p.hex() for p in (b'\xb1', b'\x01\xb0', b'\x03\xac') if code.startswith(p)), None)
                methods.append(dict(name=method['name'], descriptor=method['descriptor'],
                                    codeSha256=hashlib.sha256(code).hexdigest(), codeBytes=len(code),
                                    entryReturnPrefixHex=prefix, instructions=rows))
            item = dict(name=name, classSha256=hashlib.sha256(raw).hexdigest(), fields=cls['fields'], methods=methods)
            if name.endswith(('$ReturnCenterCmd', '$MODE')):
                item['enumEntries'] = enum_values(cls)
            classes.append(item)
    return dict(source=SOURCE, jarSha256=digest, targetDeviceVerified=False,
                executableImplementationRecovered=False, classes=classes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Use ignored work/ output')
    args = parser.parse_args()
    report = inspect_jar(args.jar)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'evidence.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Read %d pinned classfiles; preserved return prefixes. No app code executed.' % len(report['classes']))


if __name__ == '__main__':
    main()
