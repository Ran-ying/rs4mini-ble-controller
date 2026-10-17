import tempfile,unittest
from pathlib import Path
from ronin_profiles_trace import trace,preset_read_context,relative_target,axis_mode_value

class ProfileTraceTests(unittest.TestCase):
    def prefix(self,offset=2,width=1):
        return [('const/4','v0, '+str(width)),('const-class','v1, Ljava/lang/Integer;'),('const/4','v2, '+str(offset)),('invoke-virtual','v3, v2, v0, v1, v4, Ldji/midware/data/model/P3/DataGimbalGetPushUserParams;->get(I I Ljava/lang/Class; [I)Ljava/lang/Number;')]

    def test_wrong_apk_rejected_before_optional_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'other')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d)/'sdk',Path(d)/'ui')

    def test_business_context_does_not_claim_ble_offset(self):
        self.assertEqual(preset_read_context(self.prefix()),dict(businessOffset=2,width=1,rawBleOffsetVerified=False))

    def test_swapped_or_changed_context_rejected(self):
        for offset,width in [(1,2),(2,2),(3,1)]:
            with self.assertRaisesRegex(ValueError,'offset/width'):preset_read_context(self.prefix(offset,width))

    def test_unresolved_register_or_branch_is_not_a_context(self):
        operations=self.prefix();operations[0]=('const/4','v8, 1')
        with self.assertRaises(ValueError):preset_read_context(operations)
        with self.assertRaises(ValueError):preset_read_context([('if-eqz','v3, +003h')]+self.prefix())

    def test_branch_offsets_are_hex_code_units(self):
        self.assertEqual(relative_target(0x34,'v3, v4, +014h'),0x48)
        self.assertEqual(relative_target(0x47,'goto, +25h'),0x6c)
        self.assertEqual(relative_target(0x20,'goto, -1ch'),4)

    def test_unresolved_branch_offsets_are_rejected(self):
        for pc,text in [(0,'v0, 14'),(0,'v0, +14'),(-1,'v0, +014h'),(.5,'v0, +014h')]:
            with self.assertRaises(ValueError):relative_target(pc,text)

    def test_axis_enum_shift_is_not_motor_bit_or_ui_index(self):
        self.assertEqual([axis_mode_value(n) for n in ('ThreeAxis','TwoAxis','Roll360','ThreeDRoll360')],[0,8,16,24])
        self.assertNotEqual(axis_mode_value('ThreeDRoll360'),64)
        for name in ('FPV','PF','PTF',2,True):
            with self.assertRaises(ValueError):axis_mode_value(name)
