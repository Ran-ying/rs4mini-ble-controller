import hashlib
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from ronin_code_restore import backup_table, code_item_length, encoded_methods, restore_image, sleb
from ronin_app_payloads import reset_mode_payload, follow_sensitivity_payload, follow_sensitivity_request, follow_sensitivity_body


def fixture():
    image = bytearray(512)
    image[:8] = b'dex\n039\0'
    struct.pack_into('<I', image, 64, 1)
    struct.pack_into('<I', image, 88, 1)
    struct.pack_into('<II', image, 96, 1, 112)
    struct.pack_into('<I', image, 112 + 24, 144)
    image[144:152] = bytes.fromhex('0000010000018002')
    current = struct.pack('<4H2I', 1, 1, 0, 0, 0, 2) + bytes.fromhex('00000e00')
    backup = current[:16] + bytes.fromhex('12000e00')
    image[256:276] = current
    row = dict(slot=150, size=20, allocation=20, dataOffset=0, code=backup)
    bank = dict(originalSize=512, rows=[row])
    return image, bank


def wrapped_bank(name=b'classes6.dex.dgc2'):
    image, bank = fixture()
    base, original = 16, 512
    start = base + original
    size_pos = (start + 12 + len(name) + 3) & ~3
    blob_start = size_pos + 4
    blob = (struct.pack('>6I', 68, 0xabbacddc, 24, 24, 48, 20)
            + struct.pack('>6I', 0, 20, 123, 0, 150, 20) + bank['rows'][0]['code'])
    footer = blob_start + len(blob) + 4
    raw = bytearray(footer + 4)
    struct.pack_into('<III', raw, start, 1, footer - start - 8, len(name))
    raw[start + 12:start + 12 + len(name)] = name
    struct.pack_into('<I', raw, size_pos, len(blob))
    raw[blob_start:blob_start + len(blob)] = blob
    struct.pack_into('<I', raw, footer - 4, original)
    raw[footer:footer + 4] = b'fdex'
    return raw, base, blob_start


class CodeBackupTests(unittest.TestCase):
    def test_record_maps_exact_code_off_slot_and_preserves_image_size(self):
        image, bank = fixture()
        self.assertEqual(encoded_methods(image)[150], dict(methodIndex=0, codeOffset=256))
        restored, rows = restore_image(image, bank)
        self.assertEqual(restored[256:276], bank['rows'][0]['code'])
        self.assertEqual(image[272:276], bytes.fromhex('00000e00'))
        self.assertEqual(len(restored), len(image))
        self.assertEqual(rows[0]['backupSha256'], hashlib.sha256(bank['rows'][0]['code']).hexdigest())
        self.assertEqual(restored[12:32], hashlib.sha1(restored[32:]).digest())
        self.assertEqual(struct.unpack_from('<I', restored, 8)[0], zlib.adler32(restored[12:]) & 0xffffffff)

    def test_wrapper_mixed_endian_header_and_truncation(self):
        raw, base, blob = wrapped_bank()
        parsed = backup_table(raw, base, len(raw))
        self.assertEqual(parsed['rows'][0]['slot'], 150)
        self.assertEqual(parsed['rows'][0]['size'], 20)
        for candidate in (raw[:-2], raw[:base + 10]):
            with self.assertRaises(ValueError):
                backup_table(candidate, base, len(candidate))
        damaged = raw[:]
        struct.pack_into('>I', damaged, blob + 4, 0)
        with self.assertRaises(ValueError):
            backup_table(damaged, base, len(damaged))

    def test_explicit_bank_name_cannot_select_a_different_segment(self):
        for name in (b'classes.dex.dgc2',b'classes5.dex.dgc2',b'classes8.dex.dgc2'):
            raw,base,blob=wrapped_bank(name)
            self.assertEqual(backup_table(raw,base,len(raw),name)['rows'][0]['slot'],150)
            with self.assertRaises(ValueError):backup_table(raw,base,len(raw))
        with self.assertRaisesRegex(ValueError,'unsupported'):
            backup_table(b'',0,0,b'classes9.dex.dgc2')

    def test_bank_rejects_bad_row_allocation_and_gaps(self):
        raw, base, blob = wrapped_bank()
        for offset, value in ((24, 4), (24 + 4, 15), (24 + 20, 16)):
            damaged = raw[:]
            struct.pack_into('>I', damaged, blob + offset, value)
            with self.assertRaises(ValueError):
                backup_table(damaged, base, len(damaged))

    def test_restore_rejects_unmatched_slot_changed_units_and_overlaps(self):
        image, bank = fixture()
        for row in (dict(bank['rows'][0], slot=151), dict(bank['rows'][0], code=bank['rows'][0]['code'][:12]+b'\x03\0\0\0'+bank['rows'][0]['code'][16:])):
            with self.assertRaises(ValueError):
                restore_image(image, dict(bank, rows=[row]))
        with self.assertRaises(ValueError):
            restore_image(image, dict(bank, rows=bank['rows'] * 2))

    def test_tries_and_handlers_are_bounded(self):
        # One instruction, alignment, one try, one typed handler at address0.
        code = struct.pack('<4H2I', 1, 1, 0, 1, 0, 1) + b'\x0e\0\0\0' + struct.pack('<IHH', 0, 1, 1) + b'\x01\x01\0\0'
        self.assertEqual(code_item_length(code, 0, 1), len(code))
        for candidate in (code[:-1], code[:18]+b'\x01\0'+code[20:], code[:24]+b'\x02\0'+code[26:]):
            with self.assertRaises(ValueError):
                code_item_length(candidate, 0, 1)

    def test_sleb_bounds_and_sign(self):
        self.assertEqual(sleb(b'\x7f', 0), (-1, 1))
        self.assertEqual(sleb(bytes.fromhex('9bf159'), 0), (-624485, 3))
        for raw in (b'', b'\x80', b'\xff'*5, bytes.fromhex('ffffffff0f')):
            with self.assertRaises(ValueError):
                sleb(raw, 0)

    def test_wrong_apk_hash_fails_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);apk=root/'fake.apk';out=root/'out';apk.write_bytes(b'not apk')
            result=subprocess.run([sys.executable,str(Path(__file__).with_name('ronin_code_restore.py')),'--apk',str(apk),'--output',str(out)],capture_output=True)
            self.assertNotEqual(result.returncode,0);self.assertIn(b'APK hash differs',result.stderr);self.assertFalse(out.exists())


class CurrentAppPayloadTests(unittest.TestCase):
    def test_current_reset_has_boolean_flag_not_legacy_axis_enum(self):
        self.assertEqual(reset_mode_payload(254, True).hex(), 'fe01')
        self.assertEqual(reset_mode_payload(254, False).hex(), 'fe00')
        for mode, reset in ((254,4),(254,1),(True,True),(3,False)):
            with self.assertRaises(ValueError):reset_mode_payload(mode,reset)

    def test_follow_sensitivity_source_vectors_and_no_silent_coercion(self):
        self.assertEqual(follow_sensitivity_payload(0).hex(),'960100')
        self.assertEqual(follow_sensitivity_payload(1).hex(),'960101')
        self.assertEqual(follow_sensitivity_request().hex(),'96')
        for value in (-1,2,True,None,'1'):
            with self.assertRaises(ValueError):follow_sensitivity_payload(value)

    def test_high_unsigned_index_unknown_value_and_explicit_body(self):
        self.assertEqual(follow_sensitivity_body(bytes.fromhex('960101')),dict(index=150,size=1,rawValue=1,mode=1))
        self.assertEqual(follow_sensitivity_body(bytes.fromhex('9601ff'))['rawValue'],255)
        self.assertIsNone(follow_sensitivity_body(bytes.fromhex('9601ff'))['mode'])
        for body in (bytes.fromhex('00960101'),bytes.fromhex('9602ff'),bytes.fromhex('9601'),bytes.fromhex('160101')):
            with self.assertRaises(ValueError):follow_sensitivity_body(body)


if __name__ == '__main__':unittest.main()
