import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ronin_angle_context import axis_updates,protocol_gimbal_id,trace,CAP,ROOT

class AngleContextTests(unittest.TestCase):
    def declaration(self):
        return [('sget-object','v0, '+CAP+'->ADJUST_PITCH '+CAP),('const/16','v1, -90'),('invoke-static','v1, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;'),('move-result-object','v1'),('const/16','v2, 90'),('invoke-static','v2, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;'),('move-result-object','v2'),('invoke-virtual','v5, v0, v1, v2, '+ROOT+'->addMinMaxToCapability('+CAP+' Ljava/lang/Number; Ljava/lang/Number;)V')]

    def test_boxed_literal_range(self):
        self.assertEqual(axis_updates(self.declaration()),[dict(key='ADJUST_PITCH',supported=True,minimum=-90,maximum=90)])

    def test_support_false_is_distinct_from_absent(self):
        ops=[('sget-object','v0, '+CAP+'->ADJUST_ROLL '+CAP),('const/4','v1, 0'),('invoke-virtual','v5, v0, v1, '+ROOT+'->addIsSupportedToCapability('+CAP+' Z)V')]
        self.assertEqual(axis_updates(ops),[dict(key='ADJUST_ROLL',supported=False,minimum=0,maximum=0)])
        self.assertEqual(axis_updates([]),[])

    def test_unknown_field_write_cannot_retain_prior_literal(self):
        ops=self.declaration();ops.insert(-1,('iget-object','v1, v3, Lother;->range Ljava/lang/Number;'))
        with self.assertRaisesRegex(ValueError,'unresolved angle range'):axis_updates(ops)

    def test_unknown_wide_write_invalidates_adjacent_register(self):
        ops=self.declaration();ops.insert(-1,('move-wide','v1, v4'))
        with self.assertRaisesRegex(ValueError,'unresolved angle range'):axis_updates(ops)

    def test_branch_and_switch_not_evaluated(self):
        for op in ('if-eqz','goto','packed-switch'):
            with self.assertRaisesRegex(ValueError,'conditional'):axis_updates([(op,'v1, +003h')]+self.declaration())

    def test_unrelated_key_not_mistaken_for_angle_range(self):
        ops=[(o,t.replace('ADJUST_PITCH','PITCH_UP_ENDPOINT')) for o,t in self.declaration()]
        self.assertEqual(axis_updates(ops),[])

    def test_mapping_uses_exact_one_not_truthiness(self):
        self.assertEqual([protocol_gimbal_id(v) for v in (-2147483648,-1,0,1,2,2147483647)],[0,0,0,2,0,0])
        for value in (True,1.0,'1',2147483648):
            with self.assertRaises(ValueError):protocol_gimbal_id(value)

    def test_wrong_apk_before_parser_import(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d)/'sdk')

    def test_wrong_sdk_before_parser_import(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'fixture');q=Path(d)/'sdk';q.write_bytes(b'wrong')
            with patch('ronin_angle_context.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
                with self.assertRaisesRegex(ValueError,'SDK hash mismatch'):trace(p,q)
