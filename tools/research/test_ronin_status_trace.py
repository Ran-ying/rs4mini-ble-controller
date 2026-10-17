import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_status_trace import field_context,source_values,trace,BANKS,ABNORMAL
class StatusTraceTests(unittest.TestCase):
 def getter(self,boolean=False):
  ops=[('const-class','v0, Ljava/lang/Integer;'),('const/4','v1, 0'),('new-array','v2, v1, [I'),('const/4','v3, 3'),('const/4','v4, 1'),('invoke-virtual','v5, v3, v4, v0, v2, '+ABNORMAL+'->get(I I Ljava/lang/Class; [I)Ljava/lang/Number;'),('move-result-object','v0'),('check-cast','v0, Ljava/lang/Integer;'),('invoke-virtual','v0, Ljava/lang/Integer;->intValue()I'),('move-result','v0'),('shr-int/lit8','v0, v0, 1'),('and-int/2addr','v0, '+('v4' if boolean else 'v3'))]
  return ops+([('if-ne','v0, v4, +003h'),('return','v4'),('return','v1')] if boolean else [('return','v0')])
 def test_numeric_two_bit_field(self):self.assertEqual(field_context(self.getter(),ABNORMAL,False),dict(offset=3,size=1,shift=1,mask=3,boolean=False))
 def test_boolean_is_masked_equals_one(self):self.assertEqual(field_context(self.getter(True),ABNORMAL,True),dict(offset=3,size=1,shift=1,mask=1,boolean=True))
 def test_inverted_or_transformed_boolean_rejected(self):
  ops=self.getter(True);ops[-3]=('if-eq','v0, v4, +003h')
  with self.assertRaises(ValueError):field_context(ops,ABNORMAL,True)
 def test_unknown_class_width_or_prefix_rejected(self):
  for change in [('const-class','v0, Ljava/lang/Short;'),('if-eqz','v1, +003h')]:
   with self.assertRaises(ValueError):field_context([change]+self.getter()[1:],ABNORMAL,False)
 def test_source_numeric_values_preserve_unsigned255(self):
  fields=[dict(sourceGetter='raw',offset=0,shift=0,mask=255,boolean=False),dict(sourceGetter='flag',offset=1,shift=7,mask=1,boolean=True)];self.assertEqual(source_values(b'\xff\x80',fields),dict(raw=255,flag=True))
 def test_short_source_is_not_zero_filled(self):
  with self.assertRaises(ValueError):source_values(b'',[dict(sourceGetter='raw',offset=0,shift=0,mask=255,boolean=False)])
 def test_apk_precheck_before_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))
 def test_bank_prechecks_before_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'fixture')
   for bank in BANKS:(Path(d)/('business-%02d-code-restored.dex'%bank)).write_bytes(b'wrong')
   with patch('ronin_status_trace.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
    with self.assertRaisesRegex(ValueError,'restored bank hash mismatch: 00'):trace(p,Path(d))
