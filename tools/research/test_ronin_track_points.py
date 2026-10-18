import hashlib,math,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_track_points import (slider_seconds,seconds_slider,peripheral_records,track_argument_views,cache_pose_bindings,trace,MODEL,PRODUCER,SETTER)

class TrackPointTests(unittest.TestCase):
    def test_piecewise_ui_seconds_boundary(self):
        self.assertEqual([slider_seconds(v) for v in (1,2,59,60,61,62,159)],[1,2,59,60,120,180,6000])
    def test_progress_uses_float32_then_java_truncation(self):
        self.assertEqual(slider_seconds(60.5),60)
        self.assertEqual(slider_seconds(60.999999),120)
    def test_inverse_ui_mapping_is_lossy(self):
        self.assertEqual(seconds_slider(121),61)
        self.assertEqual(slider_seconds(seconds_slider(121)),120)
        self.assertEqual(seconds_slider(6000),159)
    def test_invalid_progress_and_time_do_not_become_safe_firmware_values(self):
        for value in (None,True,'60',0,160,math.inf,math.nan,10**400):
            with self.assertRaises(ValueError):slider_seconds(value)
        for value in (True,1.5,0,6001):
            with self.assertRaises(ValueError):seconds_slider(value)
    def test_pose_and_motor_tag_names_remain_distinct(self):
        r=peripheral_records(bytes.fromhex('0122029cff10029cff24020e01'))
        self.assertEqual([x['sourceType'] for x in r['records']],['PActualPose','PMotorAngle','YActualPose'])
        self.assertEqual([x['sourceDividedFloat32'] for x in r['records']],[-10.0,-10.0,27.0])
    def test_single_byte_source_read_is_signed(self):
        r=peripheral_records(bytes.fromhex('01220180'))['records'][0]
        self.assertEqual(r['sourceInt32'],-128)
        self.assertEqual(struct.pack('<f',r['sourceDividedFloat32']).hex(),'cdcc4cc1')
    def test_short_and_int_widths_are_signed_little_endian(self):
        r=peripheral_records(bytes.fromhex('0122020080230400000080'))['records']
        self.assertEqual([x['sourceInt32'] for x in r],[-32768,-2147483648])
    def test_long_source_value_narrows_to_signed_int32_before_float(self):
        r=peripheral_records(bytes.fromhex('012208ffffffff00000000'))['records'][0]
        self.assertEqual(r['sourceInt32'],-1)
        self.assertEqual(struct.pack('<f',r['sourceDividedFloat32']).hex(),'cdccccbd')
    def test_int_to_float_rounding_precedes_division(self):
        r=peripheral_records(bytes.fromhex('012204ffffff7f'))['records'][0]
        self.assertEqual(r['sourceDividedFloat32'],214748368.0)
    def test_duplicates_unknown_tag_and_unsupported_width_are_preserved(self):
        r=peripheral_records(bytes.fromhex('0122020a0022021400fe01ff2303010203'))['records']
        self.assertEqual([x['rawTag'] for x in r],[34,34,254,35]);self.assertEqual(r[2]['sourceSignedTag'],-2)
        self.assertIsNone(r[2]['sourceType']);self.assertEqual(r[2]['payloadHex'],'ff')
        self.assertIsNone(r[3]['sourceInt32']);self.assertEqual(r[3]['payloadHex'],'010203')
    def test_non_update_source_flag_retains_opaque_body(self):
        r=peripheral_records(bytes.fromhex('0022020a00'))
        self.assertFalse(r['sourceRecordBranchSelected']);self.assertEqual(r['records'],[]);self.assertEqual(r['bodyHex'],'0022020a00')
    def test_missing_fields_never_get_source_default_zero(self):
        self.assertEqual(peripheral_records(b'\1')['records'],[])
        self.assertIsNone(peripheral_records(bytes.fromhex('012200'))['records'][0]['sourceInt32'])
    def test_truncated_records_and_signed_negative_lengths_rejected(self):
        for data in (b'',bytes.fromhex('0122'),bytes.fromhex('01220200'),bytes([1,34,128])+bytes(128)):
            with self.assertRaises(ValueError):peripheral_records(data)
    def track_ops(self,first=0):
        return [('const/4','v1, '+str(first)),('iget','v2, v9, LX$RoadPoint;->stopTime F'),('iget','v3, v9, LX$RoadPoint;->yaw F'),('iget','v4, v9, LX$RoadPoint;->pitch F'),('const/4','v5, 0'),('invoke-virtual/range','v0 ... v5, '+SETTER+'->addRoadPoint(F F F F F)LX;')]
    def test_track_window_preserves_argument_order_and_forced_first_zero(self):
        self.assertEqual(track_argument_views(self.track_ops()),[[0,'stopTime','yaw','pitch',0]])
    def test_unresolved_track_argument_and_wrong_arity_rejected(self):
        with self.assertRaises(ValueError):track_argument_views(self.track_ops(first=1))
        ops=self.track_ops();ops[-1]=(ops[-1][0],ops[-1][1].replace('v5,','v4,'))
        with self.assertRaises(ValueError):track_argument_views(ops)
    def test_string_literal_is_not_track_invocation(self):
        self.assertEqual(track_argument_views([('const-string/jumbo','v0, '+SETTER+'->addRoadPoint(F F F F F)LX;')]),[])
    def binding_ops(self):
        return [('invoke-virtual','v3, '+MODEL+'->getPActualPose()F'),('move-result','v0'),('invoke-static','v0, Ljava/lang/Float;->valueOf(F)Ljava/lang/Float;'),('move-result-object','v0'),('const-string/jumbo','v1, PeripheralPosPitch'),('invoke-virtual','v2, v1, '+PRODUCER+'->convertKeyToPath(Ljava/lang/String;)Ldji/sdksharedlib/keycatalog/DJISDKCacheKey;'),('move-result-object','v1'),('invoke-virtual','v2, v0, v1, '+PRODUCER+'->notifyValueChangeForKeyPath(Ljava/lang/Object; Ldji/sdksharedlib/keycatalog/DJISDKCacheKey;)V')]
    def test_pose_getter_to_cache_key_register_chain(self):
        self.assertEqual(cache_pose_bindings(self.binding_ops()),[dict(getter='getPActualPose',key='PeripheralPosPitch')])
    def test_unrelated_notify_register_and_incomplete_binding_rejected(self):
        ops=self.binding_ops();ops[-1]=(ops[-1][0],ops[-1][1].replace('v2, v0, v1,','v2, v9, v1,'))
        with self.assertRaises(ValueError):cache_pose_bindings(ops)
        with self.assertRaises(ValueError):cache_pose_bindings(self.binding_ops()[:-1])
    def test_duplicate_cache_key_and_string_like_getter_rejected(self):
        with self.assertRaises(ValueError):cache_pose_bindings(self.binding_ops()*2)
        self.assertEqual(cache_pose_bindings([('const-string/jumbo','v0, '+MODEL+'->getPActualPose()F')]),[])
    def test_apk_hash_precedes_optional_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))
    def test_bank_hash_precedes_optional_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'fixture');(Path(d)/'business-03-code-restored.dex').write_bytes(b'wrong')
            with patch('ronin_track_points.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
                with self.assertRaisesRegex(ValueError,'bank hash mismatch'):trace(p,Path(d))

    def test_second_bank_is_validated_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);apk=root/'apk';apk.write_bytes(b'apk');first=b'first-bank';(root/'business-03-code-restored.dex').write_bytes(first);(root/'business-05-code-restored.dex').write_bytes(b'wrong-second')
            with patch('ronin_track_points.APK_SHA256',hashlib.sha256(b'apk').hexdigest()),patch('ronin_track_points.BANKS',{3:hashlib.sha256(first).hexdigest(),5:'wrong-pin'}):
                with self.assertRaisesRegex(ValueError,'bank hash mismatch'):trace(apk,root)
