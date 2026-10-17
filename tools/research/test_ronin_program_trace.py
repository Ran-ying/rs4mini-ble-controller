import hashlib,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_program_trace import (rounded_tenths,track_body,delay_info_or,delay_body,ronin_timelapse_body,panorama_body,external_request_body,standalone_status,external_status_records,trace)

class ProgramTraceTests(unittest.TestCase):
 def test_float_round_ties_go_toward_positive_infinity(self):
  self.assertEqual([rounded_tenths(v) for v in (1.25,-1.25,.05,-.05)],[13,-12,1,0])
 def test_float_round_saturates_java_int_before_low16(self):
  self.assertEqual(rounded_tenths(1e20),2147483647);self.assertEqual(rounded_tenths(-1e20),-2147483648)
 def test_nonfinite_and_unrepresentable_float_rejected(self):
  for v in (True,float('inf'),float('nan'),1e100,10**1000):
   with self.assertRaises(ValueError):rounded_tenths(v)
 def test_track_point_argument_order_differs_from_wire_order(self):
  body=track_body([(1,2,3,4,5)],tripod=True,phase=0,record_or_preview=1)
  self.assertEqual(body.hex(),'0a010a001400320028001e00')
 def test_track_negative_short_wrap_and_low16(self):
  body=track_body([(6553.6,0,-1.25,-.05,-3276.8)],tripod=False,phase=0,record_or_preview=0)
  self.assertEqual(struct.unpack('<5H',body[2:]),(0,0,32768,0,65524))
 def test_track_stop_is_one_byte_and_does_not_consume_points(self):
  points=[(1,2,3,4,5)];self.assertEqual(track_body(points,tripod=True,phase=1,record_or_preview=1),bytes.fromhex('0e'));self.assertEqual(points,[(1,2,3,4,5)])
 def test_track_maximum_ten_and_empty_start(self):
  self.assertEqual(len(track_body([(0,0,0,0,0)]*10,tripod=False,phase=0,record_or_preview=0)),102)
  self.assertEqual(track_body([],tripod=False,phase=0,record_or_preview=0),b'\0\0')
  with self.assertRaises(ValueError):track_body([(0,0,0,0,0)]*11,tripod=False,phase=0,record_or_preview=0)
 def test_track_other_phase_is_not_silently_turned_into_stop(self):
  with self.assertRaises(ValueError):track_body([],tripod=False,phase=2,record_or_preview=0)
 def test_info_setters_or_and_cannot_clear_existing_bits(self):
  self.assertEqual(delay_info_or(0x8f,'preview',0),0x8f);self.assertEqual(delay_info_or(0x8f,'externalDevice',False),0x8f)
  self.assertEqual(delay_info_or(0,'phase',-1),4);self.assertEqual(delay_info_or(0,'mode',2),0)
 def test_delay_sixth_point_allowed_seventh_rejected(self):
  self.assertEqual(len(delay_body(0,[(0,0,0,0)]*6)),62)
  with self.assertRaises(ValueError):delay_body(0,[(0,0,0,0)]*7)
 def test_delay_signed_fields_and_duration_low32(self):
  self.assertEqual(delay_body(0x8f,[(-1,-32768,32767,-1)]).hex(),'8f01ffffffff0080ff7fffff')
 def test_ronin_mode_one_has_two_bytes_even_with_queued_points(self):
  self.assertEqual(ronin_timelapse_body(1,[(1,2,3,4)]*5,99),b'\x01\x05')
 def test_ronin_total_duration_overwrites_first_duration(self):
  b=ronin_timelapse_body(0,[(0x11223344,1,2,3),(0x55667788,4,5,6)],0x100000001)
  self.assertEqual(b[2:6],b'\1\0\0\0');self.assertEqual(b[12:16],bytes.fromhex('88776655'));self.assertEqual(len(b),22)
 def test_ronin_does_not_repair_source_empty_mode_zero_allocation(self):
  with self.assertRaisesRegex(ValueError,'exceeds'):ronin_timelapse_body(0,[],10)
 def test_ronin_five_point_limit_and_int_low16(self):
  self.assertEqual(ronin_timelapse_body(0,[(1,-1,65536,2147483647)],-1).hex(),'0001ffffffffffff0000ffff')
  with self.assertRaises(ValueError):ronin_timelapse_body(0,[(1,2,3,4)]*6,1)
 def test_panorama_mixed_width_and_setrange_argument_order(self):
  self.assertEqual(panorama_body(-1,256,0x12345678,-2,257,258,259,260).hex(),'ffff785600fe01020304')
 def test_external_request_distinguishes_subscription_stop_and_single(self):
  self.assertEqual([external_request_body(v,98).hex() for v in range(3)],['00000162','00010162','00020162'])
 def test_external_request_rejects_guessed_program_tag(self):
  with self.assertRaises(ValueError):external_request_body(0,37)
 def test_panorama_status_unsigned_counters_and_unknown_tail(self):
  r=standalone_status('panorama',bytes.fromhex('feffff0080abcd'))
  self.assertEqual((r['sourceStatus'],r['currentPictures'],r['totalPictures']),(254,65535,32768));self.assertTrue(r['bodyHex'].endswith('abcd'))
 def test_standalone_timelapse_mask_differs_from_external_mask(self):
  r=standalone_status('timelapse',bytes.fromhex('fcfeff80'))
  self.assertEqual((r['sourceStatus'],r['sourceTakingOrPreview'],r['unknownFlagBits']),(0,1,244))
  e=external_status_records(bytes.fromhex('003704fcfeff80'))['records'][0]['sourceValues'];self.assertEqual(e['status'],4)
 def test_short_standalone_status_is_rejected(self):
  for kind,body in (('panorama',b'\0'*4),('timelapse',b'\0'*3)):
   with self.assertRaises(ValueError):standalone_status(kind,body)
 def test_external_success_zero_and_one_both_accepted(self):
  for prefix in (0,1):self.assertTrue(external_status_records(bytes((prefix,98,4,2,3,4,5)))['sourceSuccess'])
 def test_external_failure_does_not_decode_following_records(self):
  r=external_status_records(bytes.fromhex('ff6204'));self.assertFalse(r['sourceSuccess']);self.assertEqual(r['records'],[])
 def test_external_multiple_and_duplicate_records_are_retained(self):
  r=external_status_records(bytes.fromhex('00620401020304620405060708630509ffff0080'))
  self.assertEqual([x['rawTag'] for x in r['records']],[98,98,99]);self.assertEqual(r['records'][2]['sourceValues']['totalPictures'],32768)
 def test_unknown_tag_and_zero_length_preserved_with_signed_view(self):
  r=external_status_records(bytes.fromhex('00fe00620401020304'))
  self.assertEqual(r['records'][0],dict(rawTag=254,sourceSignedTag=-2,length=0,payloadHex=''));self.assertEqual(len(r['records']),2)
 def test_external_rejects_truncation_not_cross_record_reads(self):
  for b in ('00','0062','006204010203','006203010203','006280'):
   with self.assertRaises(ValueError):external_status_records(bytes.fromhex(b))
 def test_boolean_integer_fields_are_rejected(self):
  with self.assertRaises(ValueError):delay_info_or(True,'mode',1)
  with self.assertRaises(ValueError):panorama_body(True,0,0,0,0,0,0,0)
 def test_apk_hash_checked_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))
 def test_banks_checked_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'fixture');(Path(d)/'business-00-code-restored.dex').write_bytes(b'wrong')
   with patch('ronin_program_trace.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
    with self.assertRaisesRegex(ValueError,'bank hash mismatch'):trace(p,Path(d))
