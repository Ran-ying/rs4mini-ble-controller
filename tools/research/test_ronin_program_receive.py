import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_program_receive import source_payload_view,delivery_paths,program_policy,trace
from ronin_program_trace import external_status_records
class ProgramReceiveTests(unittest.TestCase):
 def test_request_success_byte_is_not_stripped(self):
  r=source_payload_view(0,bytes.fromhex('01620401020304'),needs_ccode=True)
  self.assertEqual(r['businessOffsetInPayload'],0);self.assertIsNone(r['returnCode']);self.assertEqual(r['businessBodyHex'],'01620401020304')
 def test_ack_outer_code_and_business_success_are_distinct(self):
  r=source_payload_view(128,bytes.fromhex('0001620401020304'),needs_ccode=True)
  self.assertEqual(r['returnCode'],0);self.assertEqual(r['businessBodyHex'],'01620401020304')
  parsed=external_status_records(bytes.fromhex(r['businessBodyHex']));self.assertEqual(parsed['rawSuccessByte'],1);self.assertEqual(parsed['records'][0]['sourceValues']['status'],1)
 def test_business_success_zero_also_retained_after_ack_code(self):
  r=source_payload_view(128,bytes.fromhex('0000620401020304'),needs_ccode=True);self.assertEqual(r['businessBodyHex'],'00620401020304')
 def test_nack_code_does_not_discard_raw_remaining_body(self):
  r=source_payload_view(128,bytes.fromhex('ff012345'),needs_ccode=True);self.assertEqual((r['returnCode'],r['businessBodyHex']),(255,'012345'))
 def test_ack_without_ccode_context_does_not_guess_strip(self):
  r=source_payload_view(128,b'\x01\x02',needs_ccode=False);self.assertEqual(r['businessOffsetInPayload'],0);self.assertEqual(r['businessBodyHex'],'0102')
 def test_missing_ack_ccode_is_rejected(self):
  with self.assertRaises(ValueError):source_payload_view(128,b'',needs_ccode=True)
 def test_empty_business_body_does_not_invent_source_data_assignment(self):
  r=source_payload_view(128,b'\0',needs_ccode=True);self.assertFalse(r['sourceWouldAssignData']);self.assertEqual(r['businessBodyHex'],'')
 def test_request_can_have_empty_business_body(self):self.assertFalse(source_payload_view(0,b'',needs_ccode=True)['sourceWouldAssignData'])
 def test_encrypted_payload_is_not_interpreted(self):
  for flag in (1,7,129):
   with self.assertRaises(ValueError):source_payload_view(flag,b'\0',needs_ccode=True)
 def test_flags_and_ccode_context_require_exact_types(self):
  for flags,context in ((True,True),(256,True),(0,1)):
   with self.assertRaises(ValueError):source_payload_view(flags,b'\0',needs_ccode=context)
 def test_mutable_input_is_snapshotted_to_hex(self):
  b=bytearray.fromhex('0001');r=source_payload_view(128,b,needs_ccode=True);b[:]=b'\xff\xff';self.assertEqual(r['rawPayloadHex'],'0001')
 def test_base6b_mix_takes_both_eligible_paths(self):self.assertEqual(delivery_paths(is_block=False,is_mix=True),dict(processorPathEligible=True,pushPathEligible=True))
 def test_block_and_plain_push_paths_are_different(self):
  self.assertEqual(delivery_paths(is_block=True,is_mix=False),dict(processorPathEligible=True,pushPathEligible=False))
  self.assertEqual(delivery_paths(is_block=False,is_mix=False),dict(processorPathEligible=False,pushPathEligible=True))
 def test_ble_ping_exception_allows_blocked_push_path(self):self.assertTrue(delivery_paths(is_block=True,is_mix=False,is_ble_ping=True)['pushPathEligible'])
 def test_dispatch_flags_do_not_accept_truthy_integer(self):
  with self.assertRaises(ValueError):delivery_paths(is_block=1,is_mix=False)
 def test_three_arg_constructor_defaults_not_ordinal(self):
  r=program_policy(dict(descriptor='(Ljava/lang/String; I I)V',arguments=['SetTrack',31,98]));self.assertEqual((r['commandId'],r['isBlock'],r['isMix'],r['modelClass']),(98,True,False,None))
 def test_five_arg_constructor_has_no_mix(self):
  r=program_policy(dict(descriptor='(Ljava/lang/String; I I Z Ljava/lang/Class;)V',arguments=['Push',28,56,0,'LPush;']));self.assertFalse(r['isBlock']);self.assertFalse(r['isMix'])
 def test_six_arg_constructor_preserves_both_flags(self):
  r=program_policy(dict(descriptor='(Ljava/lang/String; I I Z Z Ljava/lang/Class;)V',arguments=['Mixed',34,107,0,1,'LMixed;']));self.assertFalse(r['isBlock']);self.assertTrue(r['isMix'])
 def test_invalid_constructor_or_flag_is_rejected(self):
  for r in (dict(descriptor='(I)V',arguments=[1]),dict(descriptor='(Ljava/lang/String; I I Z Z Ljava/lang/Class;)V',arguments=['Mixed',34,107,0,2,'LMixed;'])):
   with self.assertRaises(ValueError):program_policy(r)
 def test_non_wire_sentinel_not_narrowed_to_byte(self):
  with self.assertRaises(ValueError):program_policy(dict(descriptor='(Ljava/lang/String; I I)V',arguments=['Other',42,511]))
 def test_unresolved_class_literal_rejected(self):
  with self.assertRaises(ValueError):program_policy(dict(descriptor='(Ljava/lang/String; I I Z Ljava/lang/Class;)V',arguments=['Push',28,56,0,None]))
 def test_apk_hash_checked_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))
 def test_bank_hash_checked_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'fixture');(Path(d)/'business-00-code-restored.dex').write_bytes(b'wrong')
   with patch('ronin_program_receive.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
    with self.assertRaisesRegex(ValueError,'bank hash mismatch'):trace(p,Path(d))
