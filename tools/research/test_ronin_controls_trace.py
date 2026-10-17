import tempfile,unittest
from pathlib import Path
from ronin_controls_trace import trace,handle_setter_context,handle_fallback_comparison,MODEL
from ronin_controls_payloads import fine_tune_payload,handle_patch_payload,handle_reply_body,hg724_reset_payload
class ControlsTraceTests(unittest.TestCase):
    def test_bad_apk_rejected_before_optional_import(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'other')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d)/'sdk',Path(d)/'ui')
    def test_fine_axes_are_not_ordinals_and_values_truncate(self):
        self.assertEqual(fine_tune_payload('pitch',-1.29),bytes.fromhex('f402'));self.assertEqual(fine_tune_payload('roll',1.29),bytes.fromhex('0c00'))
        self.assertEqual(fine_tune_payload('roll',1.999999999),bytes.fromhex('1400'))
    def test_fine_bad_values_and_unproven_yaw_action_rejected(self):
        for axis,value in [('yaw',1),('pitch',True),('pitch',float('nan')),('roll',2.1),('roll',-2.1)]:
            with self.assertRaises(ValueError):fine_tune_payload(axis,value)
    def test_handle_named_patch_uses_full_body_with_source_defaults(self):
        self.assertEqual(handle_patch_payload(panDirection=1),bytes.fromhex('ffff01ffffffffff'));self.assertEqual(handle_patch_payload(dualChannelMode=0,tiltDirection=1),bytes.fromhex('0001ffffffffffff'))
        for patch in ({},{'index':1},{'panDirection':True},{'dualChannelMode':2},{'rotationFocus':1}):
            with self.assertRaises(ValueError):handle_patch_payload(**patch)
    def test_handle_body_preserves_raw_flags_and_extra_bytes(self):
        r=handle_reply_body(bytes([7,1,0,255,3,2,3,254,99]));self.assertEqual(r['values'][0]['rawValue'],7);self.assertEqual(r['values'][3]['rawValue'],255);self.assertFalse(r['values'][5]['sourceBit0']);self.assertTrue(r['values'][6]['sourceBit0']);self.assertEqual(r['bodyHex'],'070100ff030203fe63')
        with self.assertRaises(ValueError):handle_reply_body(bytes(7))
    def test_reset_requires_platform_identity_and_has_special_body(self):
        self.assertEqual(hg724_reset_payload('HG724'),bytes.fromhex('010001'))
        for value in (103,'Ronin2','HG702',True):
            with self.assertRaises(ValueError):hg724_reset_payload(value)

    def test_named_handle_actions_require_fresh_single_field_objects(self):
        owner=MODEL+'DataGimbalSetHandleParams;'
        for setter,field,offset in [('setDualChannelEnable','dualChannelMode',0),('setTiltDirection','tiltDirection',1),('setPanDirection','panDirection',2)]:
            operations=[('new-instance','v0, '+owner),('invoke-direct','v0, '+owner+'-><init>()V'),('invoke-virtual','v0, v1, '+owner+'->'+setter+'(I)'+owner)]
            r=handle_setter_context(operations)
            self.assertEqual((r['field'],r['offset'],r['freshObject']),(field,offset,True))

    def test_handle_singleton_missing_constructor_and_extra_fields_rejected(self):
        owner=MODEL+'DataGimbalSetHandleParams;'
        ops=[('new-instance','v0, '+owner),('invoke-direct','v0, '+owner+'-><init>()V'),('invoke-virtual','v0, v1, '+owner+'->setPanDirection(I)'+owner)]
        variants=[ops[1:],ops[:1]+ops[2:],ops+[('invoke-static',owner+'->getInstance()'+owner)],ops+[('invoke-virtual','v0, v1, '+owner+'->setTiltDirection(I)'+owner)],[(op,text.replace('setPanDirection','setProfile')) for op,text in ops]]
        for variant in variants:
            with self.assertRaises(ValueError):handle_setter_context(variant)

    def test_cache_fallback_identity_is_not_value_equality_or_write_acceptance(self):
        ops=[('invoke-virtual','v3, Lcache;->getData()Ljava/lang/Object;'),('invoke-virtual','v1, v3, Ljava/lang/Class;->cast(Ljava/lang/Object;)Ljava/lang/Object;'),('if-ne','v0, v3, +00bh'),('if-eqz','v3, +022h'),('sget-object','v0, Lerror;->RESULT_FAILED Lerror;'),('invoke-interface','v3, v0, Lcallback;->onSuccess(Ljava/lang/Object;)V'),('invoke-interface','v3, v0, Lcallback;->onFails(Lerror;)V')]
        self.assertEqual(handle_fallback_comparison(ops),'reference-identity-after-Class.cast')
        variants=[[(op.replace('if-ne','if-eq'),text) for op,text in ops],ops+[('invoke-virtual','v0, v3, Ljava/lang/Object;->equals(Ljava/lang/Object;)Z')],ops[1:],ops[:-1],[(op,text.replace('RESULT_FAILED','UNKNOWN')) for op,text in ops]]
        for variant in variants:
            with self.assertRaises(ValueError):handle_fallback_comparison(variant)
