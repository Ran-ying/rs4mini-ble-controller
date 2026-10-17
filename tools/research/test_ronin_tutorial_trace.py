import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_tutorial_trace import source_tutorial_body,source_step_body,source_step_bit,trace,BANKS,NAMES,FLAGS
class TutorialTraceTests(unittest.TestCase):
 def test_all_declared_steps_remain_distinct(self):
  for value,name in enumerate(NAMES):
   r=source_tutorial_body(bytes((value,0,0,0,0)));self.assertEqual(r['rawStep'],value);self.assertEqual(r['knownSourceStepName'],name);self.assertEqual(r['sourceFindResult'],name)
 def test_unknown_source_fallback_does_not_erase_unknown_raw_step(self):
  for value in (11,127,255):
   r=source_tutorial_body(bytes((value,0,0,0,0)));self.assertEqual(r['rawStep'],value);self.assertIsNone(r['knownSourceStepName']);self.assertEqual(r['sourceFindResult'],'STEP_FINISH')
 def test_full_unsigned_word_signed_view_and_unknown_bits_preserved(self):
  r=source_tutorial_body(bytes.fromhex('ffffffffffaa'));self.assertEqual(r['rawCompletionWord'],4294967295);self.assertEqual(r['sourceSignedCompletionWord'],-1);self.assertEqual(r['unknownCompletionBits'],4294966784);self.assertEqual(r['bodyHex'],'ffffffffffaa');self.assertTrue(all(type(v) is int and v==1 for v in r['sourceFlags'].values()))
 def test_finish_and_start_use_java_wrapped_negative_shift_counts(self):
  self.assertTrue(source_step_bit(1<<30,0));self.assertFalse(source_step_bit(1<<30,1));self.assertTrue(source_step_bit(1<<31,1));self.assertFalse(source_step_bit(1<<31,0))
 def test_each_normal_step_maps_to_one_numeric_source_flag(self):
  for value in range(2,11):
   word=1<<(value-2);r=source_tutorial_body(b'\x01'+word.to_bytes(4,'little'));self.assertTrue(source_step_bit(word,value));self.assertEqual(sum(r['sourceFlags'].values()),1);self.assertEqual(next(k for k,v in r['sourceFlags'].items() if v),next(k for k,shift in FLAGS.items() if shift==value-2))
 def test_java_int_narrowing_is_not_axis_enum_or_request_validation(self):
  for value,expected in ((-1,255),(0,0),(10,10),(256,0),(257,1),(-2147483648,0),(2147483647,255)):self.assertEqual(source_step_body(value),bytes((expected,)))
  for value in (True,1.0,2147483648):
   with self.assertRaises(ValueError):source_step_body(value)
 def test_short_and_invalid_words_are_rejected(self):
  for value in (bytes(4),[],None):
   with self.assertRaises(ValueError):source_tutorial_body(value)
  for word,step in ((True,2),(-1,2),(4294967296,2),(0,11),(0,True)):
   with self.assertRaises(ValueError):source_step_bit(word,step)
 def test_apk_precheck_before_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))
 def test_bank_prechecks_before_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'fixture')
   for bank in BANKS:(Path(d)/('business-%02d-code-restored.dex'%bank)).write_bytes(b'wrong')
   with patch('ronin_tutorial_trace.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
    with self.assertRaisesRegex(ValueError,'restored bank hash mismatch: 00'):trace(p,Path(d))
