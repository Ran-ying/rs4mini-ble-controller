import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


static = load('msdk_static')
payloads = load('msdk_payloads')


def synthetic_class(code=b'\xb1\x04\xac'):
    def utf(text):
        raw = text.encode('ascii')
        return b'\x01' + struct.pack('>H', len(raw)) + raw
    pool = [utf('Example'), b'\x07\x00\x01', utf('java/lang/Object'), b'\x07\x00\x03',
            utf('sample'), utf('()I'), utf('Code')]
    content = struct.pack('>HHI', 1, 1, len(code)) + code + b'\x00\x00\x00\x00'
    method = struct.pack('>HHHHHI', 1, 5, 6, 1, 7, len(content)) + content
    return (bytes.fromhex('cafebabe00000034') + struct.pack('>H', len(pool) + 1)
            + b''.join(pool) + struct.pack('>HHHHHH', 1, 2, 4, 0, 0, 1) + method + b'\x00\x00')


class ClassfileInspectionTests(unittest.TestCase):
    def test_preserves_unreachable_return_tail_without_executing_it(self):
        cls = static.parse_class(synthetic_class())
        self.assertEqual(cls['name'], 'Example')
        code = cls['methods'][0]['code']
        self.assertEqual(code, b'\xb1\x04\xac')
        self.assertEqual([r['opcode'] for r in static.instructions(code, cls['resolve'])], [177, 4, 172])

    def test_classfile_truncation_magic_version_and_extra_data_fail(self):
        raw = synthetic_class()
        for candidate in (b'', raw[:20], raw[:-1], b'\0' + raw[1:], raw[:7] + b'\x35' + raw[8:], raw + b'!'):
            with self.assertRaises(ValueError):
                static.parse_class(candidate)

    def test_pool_cycle_or_out_of_range_reference_fails(self):
        raw = bytearray(synthetic_class())
        class_entry = raw.index(b'\x07\x00\x01', 10)
        for index in (2, 255):
            candidate = raw[:]
            candidate[class_entry + 1:class_entry + 3] = struct.pack('>H', index)
            with self.assertRaises(ValueError):
                static.parse_class(candidate)

    def test_instruction_operand_and_branch_boundaries(self):
        self.assertEqual(static.instructions(b'\x10\xff\xb1', lambda _: None)[0]['literal'], -1)
        self.assertEqual(static.instructions(b'\xa7\x00\x03\xb1', lambda _: None)[0]['targets'], [3])
        for code in (b'\x10', b'\xff', b'\xa7\x00\x02\xb1', b'\xc4\x00\x00\x00', b'\xaa'):
            with self.assertRaises(ValueError):
                static.instructions(code, lambda _: None)

    def test_switch_and_wide_lengths_are_bounded(self):
        switch = b'\xaa\0\0\0' + struct.pack('>iiii', 20, 0, 0, 20) + b'\xb1'
        self.assertEqual(static.instructions(switch, lambda _: None)[0]['targets'], [20, 20])
        lookup = b'\xab\0\0\0' + struct.pack('>iiii', 20, 1, 42, 20) + b'\xb1'
        self.assertEqual(static.instructions(lookup, lambda _: None)[0]['targets'], [20, 20])
        wide = b'\xc4\x84\x00\x01\xff\xff\xb1'
        self.assertEqual([r['offset'] for r in static.instructions(wide, lambda _: None)], [0, 6])
        for code in (switch[:-2], lookup[:12], b'\xc4\x84\x00'):
            with self.assertRaises(ValueError):
                static.instructions(code, lambda _: None)

    def test_enum_extracts_field_name_without_running_string_decryptor(self):
        constants = {1: ['Example', ['<init>', '(Ljava/lang/String;II)V']],
                     2: ['Example', ['SAMPLE', 'LExample;']]}
        cls = dict(name='Example', resolve=constants.__getitem__,
                   methods=[dict(name='<clinit>', code=bytes.fromhex('0304b70001b30002b1'))])
        self.assertEqual(static.enum_values(cls), [dict(name='SAMPLE', ordinal=0, value=1)])
        cls['methods'][0]['code'] = bytes.fromhex('0404b70001b30002b1')
        with self.assertRaises(ValueError):
            static.enum_values(cls)

    def test_enum_control_flow_is_not_interpreted(self):
        cls = dict(name='Example', resolve=lambda _: None, methods=[dict(name='<clinit>', code=b'\xa7\x00\x03\xb1')])
        with self.assertRaisesRegex(ValueError, 'control flow'):
            static.enum_values(cls)

    def test_wrong_jar_hash_fails_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar, output = root / 'fake.jar', root / 'out'
            jar.write_bytes(b'not a jar')
            result = subprocess.run([sys.executable, static.__file__, '--jar', str(jar), '--output', str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'JAR hash differs', result.stderr)
            self.assertFalse(output.exists())


class CandidatePayloadTests(unittest.TestCase):
    def test_reset_raw_enum_and_invalid_sentinel_are_not_axis_api(self):
        self.assertEqual(payloads.reset_mode_payload(254, 1).hex(), 'fe01')
        self.assertEqual(payloads.reset_mode_payload(254, 4).hex(), 'fe04')
        self.assertEqual(payloads.reset_mode_payload(2, None).hex(), '0200')
        self.assertEqual(payloads.reset_mode_payload(0, 255).hex(), '0000')
        for args in ((True, 1), (3, 1), (254, 2), (254, -1), (254, 'pan')):
            with self.assertRaises(ValueError):
                payloads.reset_mode_payload(*args)

    def test_parameter_request_preserves_order_duplicates_and_raw_high_indexes(self):
        self.assertEqual(payloads.ronin_parameter_request([18, 60, 18, 255]).hex(), '123c12ff')
        for indexes in ([], [True], [256], '18'):
            with self.assertRaises(ValueError):
                payloads.ronin_parameter_request(indexes)

    def test_parameter_decode_requires_context_not_self_describing_tlv(self):
        raw = bytes.fromhex('1201001202ffff3c08ffffffffffffffff')
        rows = payloads.ronin_parameter_body(raw, [(18, 1), (18, 2), (60, 8)])
        self.assertEqual([r['rawHex'] for r in rows], ['00', 'ffff', 'ffffffffffffffff'])
        # The legacy method skips a header byte and trusts external metadata;
        # preserve a discrepant header instead of asserting it is a wire width.
        self.assertEqual(payloads.ronin_parameter_body(bytes.fromhex('120900'), [(18, 1)])[0]['headerByte'], 9)
        for body, context in ((b'\0' + raw, [(18, 1), (18, 2), (60, 8)]),
                              (raw[:-1], [(18, 1), (18, 2), (60, 8)]), (raw, []),
                              (bytes.fromhex('120100'), [(19, 1)]),
                              (bytes.fromhex('120100'), [(18, 3)])):
            with self.assertRaises(ValueError):
                payloads.ronin_parameter_body(body, context)

    def test_handle_body_keeps_values_raw_and_camera_tail_uninterpreted(self):
        result = payloads.handle_parameter_body(bytes.fromhex('ff02030405feffff'))
        self.assertEqual(result['dualChannelRaw'], 255)
        self.assertEqual(result['pitchFreeRaw'], 5)
        self.assertEqual(result['uninterpretedTailHex'], 'feffff')
        for raw in (b'', bytes(7), bytes(9)):
            with self.assertRaises(ValueError):
                payloads.handle_parameter_body(raw)


if __name__ == '__main__':
    unittest.main()
