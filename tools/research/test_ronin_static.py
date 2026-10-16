import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('ronin_static', Path(__file__).with_name('ronin_static.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def synthetic():
    base, map_offset = 256, 512
    data = bytearray(2048)
    rows = [(0, 1, 0), (1, 1, 112), (2, 1, 116), (3, 1, 120), (4, 1, 132),
            (5, 1, 140), (6, 1, 148), (0x1000, 1, map_offset), (0x1001, 1, 640), (0x2002, 1, 1200)]
    struct.pack_into('<I', data, base + map_offset, len(rows))
    for i, (typ, count, offset) in enumerate(rows):
        struct.pack_into('<HHII', data, base + map_offset + 4 + i * 12, typ, 0, count, offset)
    data[base + 1200:base + 1203] = b'\x01a\0'
    return data


class StaticInspectionTests(unittest.TestCase):
    def test_uleb_bounds_and_uint32_limit(self):
        self.assertEqual(module.uleb(bytes.fromhex('e58e26'), 0), (624485, 3))
        self.assertEqual(module.uleb(bytes.fromhex('ffffffff0f'), 0), (0xffffffff, 5))
        for value in (b'', b'\x80', b'\x80' * 5, bytes.fromhex('ffffffff1f')):
            with self.assertRaises(ValueError):
                module.uleb(value, 0)

    def test_map_requires_valid_unique_sections_and_bounded_entries(self):
        data = synthetic()
        self.assertEqual(module.maps_in(data)[0]['base'], 256)
        struct.pack_into('<H', data, 256 + 512 + 4 + 2, 1)
        self.assertEqual(module.maps_in(data), [])
        self.assertEqual(module.maps_in(synthetic()[:800]), [])

    def test_unverifiable_string_suffix_is_not_reconstructed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = module.recover(synthetic(), Path(directory))
            self.assertEqual(len(result), 1)
            self.assertFalse(result[0]['structurallyReadable'])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_wrong_apk_hash_fails_before_output_or_zip_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apk = root / 'synthetic.apk'
            apk.write_bytes(b'not an APK')
            destination = root / 'output'
            result = subprocess.run([sys.executable, str(Path(module.__file__)), '--apk', str(apk), '--output', str(destination)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(destination.exists())
            self.assertIn(b'APK hash differs', result.stderr)
