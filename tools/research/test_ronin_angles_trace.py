import hashlib
import itertools
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ronin_angles_trace import angle14_body,angle0a_control_flag,source_angle_units,source_overtime,trace,BANKS

class AngleTraceTests(unittest.TestCase):
    def body(self,**changes):
        args=dict(yaw=123,roll=0,pitch=0,absolute=True,yaw_invalid=False,roll_invalid=True,pitch_invalid=True,overtime=10)
        args.update(changes);return angle14_body(**args)

    def test_yaw_only_body_has_invalid_roll_pitch(self):
        self.assertEqual(self.body().hex(),'7b00000000000d0a')

    def test_signed_axis_order_and_relative_bit(self):
        self.assertEqual(self.body(yaw=-123,roll=45,pitch=-67,absolute=False,roll_invalid=False,pitch_invalid=False,overtime=255).hex(),'85ff2d00bdff00ff')

    def test_invalid_bits_independent_of_angle_values(self):
        for flags in itertools.product((False,True),repeat=4):
            body=self.body(absolute=flags[0],yaw_invalid=flags[1],roll_invalid=flags[2],pitch_invalid=flags[3])
            self.assertEqual(body[6],sum(int(v)<<i for i,v in enumerate(flags)))

    def test_raw_short_bounds_and_java_byte_narrowing(self):
        self.assertEqual(self.body(yaw=-32768,roll=32767,overtime=-1).hex(),'0080ff7f00000dff')
        self.assertEqual(self.body(overtime=256)[7],0)
        for args in ({'yaw':32768},{'yaw':True},{'absolute':1},{'overtime':2147483648}):
            with self.assertRaises(ValueError):self.body(**args)

    def test_0a_all_source_boolean_combinations_include_byte_narrowing(self):
        for flags in itertools.product((False,True),repeat=6):
            result=angle0a_control_flag(**dict(zip(('permission','reference','absolute','yaw_valid','roll_valid','pitch_valid'),flags)))
            self.assertEqual(result,(int(flags[4])<<5)|(int(flags[5])<<2))
        self.assertEqual(angle0a_control_flag(permission=False,reference=False,absolute=False,yaw_valid=True,roll_valid=True,pitch_valid=True),36)

    def test_source_scaling_truncates_after_float_multiply(self):
        self.assertEqual(source_angle_units(1.29),12)
        self.assertEqual(source_angle_units(-1.29),-12)
        self.assertEqual(source_angle_units(3276.8),-32768)
        self.assertEqual(source_angle_units(1.99999999),20)

    def test_source_time_clamp_and_truncation(self):
        self.assertEqual([source_overtime(v) for v in (-1,.1,1.29,25.5,50)],[1,1,12,255,255])

    def test_finite_and_explicit_numeric_inputs(self):
        for fn in (source_angle_units,source_overtime):
            for value in (True,float('nan'),float('inf'),'1'):
                with self.assertRaises(ValueError):fn(value)

    def test_wrong_apk_before_optional_import(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))

    def test_all_banks_pinned_before_optional_import(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'fixture')
            for bank in BANKS:(Path(d)/('business-%02d-code-restored.dex'%bank)).write_bytes(b'wrong')
            with patch('ronin_angles_trace.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
                with self.assertRaisesRegex(ValueError,'restored bank hash mismatch: 00'):trace(p,Path(d))
