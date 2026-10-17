import tempfile,unittest
from pathlib import Path
from ronin_user_push_trace import trace,getter_context,OWNER
class UserPushTraceTests(unittest.TestCase):
    def example(self):
        return [('const-class','v0, Ljava/lang/Integer;'),('const/4','v1, 0'),('new-array','v1, v1, [I'),('const/16','v2, 59'),('const/4','v3, 2'),('invoke-virtual','v4, v2, v3, v0, v1, '+OWNER+'->get(I I Ljava/lang/Class; [I)Ljava/lang/Number;'),('move-result-object','v0'),('check-cast','v0, Ljava/lang/Integer;'),('invoke-virtual','v0, Ljava/lang/Integer;->intValue()I'),('move-result','v0'),('return','v0')]
    def test_bad_apk_checked_before_optional_imports(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'other')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d)/'dex')
    def test_resolves_offsets_independently_of_register_numbers(self):
        self.assertEqual(getter_context(self.example()),dict(offset=59,size=2))
    def test_transformed_integer_and_branchy_getters_rejected(self):
        ops=self.example();ops.insert(-1,('mul-int/lit8','v0, v0, 10'))
        with self.assertRaises(ValueError):getter_context(ops)
        with self.assertRaises(ValueError):getter_context([('if-eqz','v0, +004h')]+self.example())
    def test_wrong_width_or_integer_class_rejected(self):
        for index,replacement in [(4,('const/4','v3, 4')),(0,('const-class','v0, Ljava/lang/Short;'))]:
            ops=self.example();ops[index]=replacement
            with self.assertRaises(ValueError):getter_context(ops)
