#!/usr/bin/env python3
"""Restore pinned APK code-item backups into an ignored, non-executed DEX view.

Default entry point restores business-05/classes6; ronin_code_banks.py reuses
the validated helpers for other structurally corroborated banks. No App code runs.
Header and backup formats are validated; unknown record words remain opaque.
"""
import argparse
import hashlib
import json
import struct
import zipfile
import zlib
from pathlib import Path
from ronin_static import APK_SHA256, maps_in, recover, uleb


def checked(data, offset, length):
    if offset < 0 or length < 0 or offset + length > len(data):
        raise ValueError('truncated/out-of-range backup data')
    return data[offset:offset + length]


def words(data, offset, endian, count):
    return struct.unpack(endian + '%dI' % count, checked(data, offset, count * 4))


def sleb(data, offset):
    value = 0
    for shift in range(0, 35, 7):
        byte = checked(data, offset, 1)[0]
        offset += 1
        value |= (byte & 127) << shift
        if not byte & 128:
            if byte & 64:
                value -= 1 << (shift + 7)
            if not -(1 << 31) <= value < (1 << 31):
                raise ValueError('SLEB128 overflows int32')
            return value, offset
    raise ValueError('unterminated SLEB128')


def code_item_length(data, offset, type_count):
    header = checked(data, offset, 16)
    registers, ins, outs, tries, debug, units = struct.unpack('<4H2I', header)
    if registers < ins:
        raise ValueError('invalid code-item register counts')
    pos = offset + 16 + units * 2
    checked(data, offset, pos - offset)
    if tries:
        if units & 1:
            if checked(data, pos, 2) != b'\0\0':
                raise ValueError('nonzero code-item padding')
            pos += 2
        table = checked(data, pos, tries * 8)
        for i in range(tries):
            start, count, handler = struct.unpack_from('<IHH', table, i * 8)
            if start + count > units:
                raise ValueError('try region outside instructions')
        pos += tries * 8
        handlers_start = pos
        handler_count, pos = uleb(data, pos)
        valid_offsets = set()
        for _ in range(handler_count):
            valid_offsets.add(pos - handlers_start)
            size, pos = sleb(data, pos)
            for _ in range(abs(size)):
                typ, pos = uleb(data, pos)
                address, pos = uleb(data, pos)
                if typ >= type_count or address >= units:
                    raise ValueError('invalid catch type/address')
            if size <= 0:
                address, pos = uleb(data, pos)
                if address >= units:
                    raise ValueError('invalid catch-all address')
        for i in range(tries):
            if struct.unpack_from('<H', table, i * 8 + 6)[0] not in valid_offsets:
                raise ValueError('invalid handler-list offset')
    return pos - offset


def encoded_methods(image):
    """Read class_data_item method slots, not code or runtime classes."""
    method_count = words(image, 88, '<', 1)[0]
    class_count, defs = words(image, 96, '<', 2)
    checked(image, defs, class_count * 32)
    slots = {}
    for i in range(class_count):
        class_data = words(image, defs + i * 32 + 24, '<', 1)[0]
        if not class_data:
            continue
        counts, pos = [], class_data
        for _ in range(4):
            count, pos = uleb(image, pos)
            counts.append(count)
        for _ in range(counts[0] + counts[1]):
            _, pos = uleb(image, pos)
            _, pos = uleb(image, pos)
        for count in counts[2:]:
            method_index = 0
            for _ in range(count):
                delta, pos = uleb(image, pos)
                method_index += delta
                _, pos = uleb(image, pos)
                slot = pos
                code, pos = uleb(image, pos)
                if method_index >= method_count or slot in slots:
                    raise ValueError('invalid/duplicate encoded method')
                slots[slot] = dict(methodIndex=method_index, codeOffset=code)
    return slots


def backup_table(container, base, limit, expected_name=b'classes6.dex.dgc2'):
    """Inspect pinned fdex wrapper; return a single validated dgc2 code bank."""
    allowed = {b'classes.dex.dgc2'} | {('classes%d.dex.dgc2' % i).encode('ascii') for i in range(2,9)}
    if expected_name not in allowed:
        raise ValueError('unsupported pinned backup entry name')
    candidates, cursor = [], base
    while True:
        footer = container.find(b'fdex', cursor, limit)
        if footer < 0:
            break
        cursor = footer + 4
        original_size = words(container, footer - 4, '<', 1)[0]
        start = base + original_size
        if not base < start < footer - 12:
            continue
        count, entry_size, name_size = words(container, start, '<', 3)
        if count != 1 or not 1 <= name_size <= 256 or start + 8 + entry_size != footer:
            continue
        name = checked(container, start + 12, name_size)
        if name != expected_name:
            continue
        size_pos = (start + 12 + name_size + 3) & ~3
        blob_size = words(container, size_pos, '<', 1)[0]
        blob_start = size_pos + 4
        if blob_start + blob_size > footer - 4:
            raise ValueError('backup entry exceeds fdex wrapper')
        total, magic, header, table_size, data_offset, data_size = words(container, blob_start, '>', 6)
        if (magic != 0xabbacddc or header != 24 or not table_size or table_size % 24
                or data_offset != header + table_size or total != data_offset + data_size
                or total > blob_size):
            raise ValueError('invalid dgc2 table header')
        blob = checked(container, blob_start, total)
        rows, seen, end = [], set(), 0
        for i in range(table_size // 24):
            offset, size, opaque, reserved, slot, allocation = words(blob, header + i * 24, '>', 6)
            if (offset != end or size < 16 or allocation != ((size + 3) & ~3)
                    or offset + allocation > data_size or slot in seen):
                raise ValueError('invalid/overlapping dgc2 record')
            seen.add(slot)
            end = offset + allocation
            raw = checked(blob, data_offset + offset, size)
            rows.append(dict(slot=slot, size=size, allocation=allocation, dataOffset=offset,
                             opaqueWord=opaque, reservedWord=reserved, code=raw))
        if end != data_size:
            raise ValueError('unconsumed backup data')
        candidates.append(dict(originalSize=original_size, bankOffset=blob_start,
                               bankSha256=hashlib.sha256(blob).hexdigest(), rows=rows))
    if len(candidates) != 1:
        raise ValueError('expected one unambiguous '+expected_name.decode('ascii')+' bank')
    return candidates[0]


def restore_image(image, bank):
    slots = encoded_methods(image)
    type_count = words(image, 64, '<', 1)[0]
    result, records, spans = bytearray(image), [], []
    for row in bank['rows']:
        if row['slot'] not in slots:
            raise ValueError('backup has no exact encoded-method slot')
        method = slots[row['slot']]
        code, size = method['codeOffset'], row['size']
        if code == 0 or code % 4 or code + size > bank['originalSize']:
            raise ValueError('backup target outside original code region')
        backup = row['code']
        current = checked(image, code, size)
        if (code_item_length(current, 0, type_count) != size
                or code_item_length(backup, 0, type_count) != size
                or current[12:16] != backup[12:16]):
            raise ValueError('backup/current code-item footprint mismatch')
        result[code:code + size] = backup
        spans.append((code, code + size))
        records.append(dict(**method, slot=row['slot'], size=size, dataOffset=row['dataOffset'],
                            beforeSha256=hashlib.sha256(current).hexdigest(),
                            backupSha256=hashlib.sha256(backup).hexdigest()))
    spans.sort()
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        raise ValueError('overlapping method destinations')
    result[12:32] = hashlib.sha1(result[32:]).digest()
    struct.pack_into('<I', result, 8, zlib.adler32(result[12:]) & 0xffffffff)
    return result, records


def restore_apk(apk, output):
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    if digest != APK_SHA256:
        raise ValueError('APK hash differs from inspected Ronin 2.2.2/7096')
    with zipfile.ZipFile(str(apk)) as archive:
        data = archive.read('classes.dex')
    maps = maps_in(data)
    if len(maps) != 8:
        raise ValueError('unexpected hidden DEX map count')
    bank = backup_table(data, maps[5]['base'], maps[6]['base'])
    output.mkdir(parents=True, exist_ok=True)
    recovery = recover(data, output)
    target = output / 'business-05.dex'
    image, records = restore_image(target.read_bytes(), bank)
    name = 'business-05-code-restored.dex'
    (output / name).write_bytes(image)
    report = dict(source='https://www.dji.com/downloads/djiapp/dji-ronin', apkSha256=digest,
                  segment=5, originalSize=bank['originalSize'], bankOffset=bank['bankOffset'],
                  bankSha256=bank['bankSha256'], restoredCodeItems=len(records), records=records,
                  derivedFile=name, derivedSha256=hashlib.sha256(image).hexdigest(),
                  methodBytesBackedByApk=True, appCodeExecuted=False, targetDeviceVerified=False,
                  otherSegmentsRestored=False)
    (output / 'code-restoration.json').write_text(json.dumps(report, indent=2) + '\n')
    return report



# Optional inspection of named restored methods; no app classes are executed.
ANALYSIS_TARGETS = {
    'DJIGimbalHG724Abstraction': {'init', 'setFollowModeSensitivity', 'onEvent3BackgroundThread'},
    'DJIGimbalParamInfoManager$1': {'run'},
    'DJIGimbalParamInfoManager': {'init', 'readToMemory', 'read'},
    'DataGimbalNewResetAndSetMode': {'doPack', 'setGimbalControl', 'start'},
    'DataGimbalSetUserParams': {'doPack', 'setInfo', 'start'},
    'DataGimbalGetUserParams': {'doPack', 'setRecData', 'start'},
    'DataGimbalGetPushType': {'getType'},
    'Ronin2GimbalParamsManager$BaseCommand': {'<clinit>', 'getKeyNameStr'},
    'Ronin2GimbalParamsManager$FollowModeSensitivityVal': {'<clinit>', 'getValue'},
    'DJISDKCacheHWAbstractionLayer': {'addGimbalAbstraction'},
    'DJISDKCacheHWAbstractionLayer$3': {'<clinit>'},
}


def analyze_restored(output, report):
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    from ronin_model_trace import protected_stub
    dex = DEX((output / report['derivedFile']).read_bytes())
    before = DEX((output / 'business-05.dex').read_bytes())
    old = {m.get_method_idx(): m for c in before.get_classes() for m in c.get_methods()}
    backups = {r['methodIndex']: r for r in report['records']}
    methods = []
    for cls in dex.get_classes():
        short = cls.get_name().rsplit('/', 1)[-1].rstrip(';')
        if short not in ANALYSIS_TARGETS:
            continue
        for method in cls.get_methods():
            if method.get_name() not in ANALYSIS_TARGETS[short] or not method.get_code():
                continue
            previous = old[method.get_method_idx()]
            operations = list(method.get_instructions())
            refs = [op.get_output() for op in operations if op.get_name().startswith(('invoke-', 'sget', 'const-string', 'const-class'))
                    and any(token in op.get_output() for token in
                            ('HG724', 'GimbalSetUserParams', 'GimbalParamInfo', 'gimbal_param_infos',
                             'cmd_follow_mode_sensitivity', 'CMD_FOLLOW_MODE_SENSITIVITY',
                             'FollowModeSensitivityVal', 'SetUserParams', 'ResetAndSetMode'))]
            row = dict(className=cls.get_name(), method=method.get_name(), descriptor=method.get_descriptor(),
                       methodIndex=method.get_method_idx(), codeOffset=method.get_code_off(),
                       instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
                       protectedStubBefore=protected_stub([op.get_name() for op in previous.get_instructions()]),
                       protectedStubAfter=protected_stub([op.get_name() for op in operations]), references=refs)
            if method.get_method_idx() in backups:
                row['backup'] = backups[method.get_method_idx()]
            methods.append(row)
    result = dict(apkSha256=report['apkSha256'], derivedSha256=report['derivedSha256'],
                  restoredCodeItems=report['restoredCodeItems'], targetDeviceVerified=False, methods=methods)
    (output / 'restored-method-evidence.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Use ignored work/ output')
    parser.add_argument('--analyze', action='store_true', help='Optional androguard==4.1.3 method fingerprints')
    args = parser.parse_args()
    report = restore_apk(args.apk, args.output)
    if args.analyze:
        analyze_restored(args.output, report)
    print('Offline analysis view: %d exact code-item backups restored. No application code executed.' % report['restoredCodeItems'])


if __name__ == '__main__':
    main()
