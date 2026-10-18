import json,tempfile,unittest
from pathlib import Path
from ronin_calibration_ack import calibration_ack_view,source_processor_key,check_receive_offsets,trace,RECV
from ronin_program_receive import source_payload_view,delivery_paths
class CalibrationAckTests(unittest.TestCase):
 def test_ack_offsets_are_not_business_offsets(self):
  r=calibration_ack_view(128,bytes((0,5,1,99)));self.assertEqual(r['returnCode'],0);self.assertEqual(r['businessOffsetInPayload'],1);self.assertEqual(r['calibration']['rawPart'],5);self.assertEqual(r['calibration']['rawStatus'],1);self.assertEqual(r['calibration']['trailingHex'],'63');self.assertTrue(r['sourceCallbackReportsSuccess'])
 def test_callback_success_is_independent_of_business_success(self):
  good_ack_fail=calibration_ack_view(128,bytes((0,0,0)));bad_ack_success=calibration_ack_view(128,bytes((1,0,1)))
  self.assertTrue(good_ack_fail['sourceCallbackReportsSuccess']);self.assertEqual(good_ack_fail['calibration']['sourceStatus'],'FAIL');self.assertFalse(bad_ack_success['sourceCallbackReportsSuccess']);self.assertEqual(bad_ack_success['calibration']['sourceStatus'],'SUCCESS')
  for r in (good_ack_fail,bad_ack_success):self.assertFalse(r['physicalCompletionVerified']);self.assertFalse(r['requestAssociationVerified'])
 def test_short_business_is_incomplete_without_processing_fallback(self):
  for payload in (b'\0',b'\0\5'):
   r=calibration_ack_view(128,payload);self.assertFalse(r['businessComplete']);self.assertIsNone(r['calibration']);self.assertTrue(r['sourceCallbackReportsSuccess'])
  with self.assertRaises(ValueError):calibration_ack_view(128,b'')
 def test_all_byte_values_preserve_raw_domains(self):
  for part in range(256):
   r=calibration_ack_view(128,bytes((0,part,2)))['calibration'];self.assertEqual(r['rawPart'],part);self.assertEqual(r['sourcePartKnown'],part<10)
  for state in range(256):
   r=calibration_ack_view(128,bytes((0,0,state)))['calibration'];self.assertEqual(r['rawStatus'],state);self.assertEqual(r['sourceStatusKnown'],state<3)
 def test_nonzero_return_codes_are_not_unsigned_index_or_success(self):
  for code in range(1,256):
   r=calibration_ack_view(128,bytes((code,0,1)));self.assertEqual(r['returnCode'],code);self.assertFalse(r['sourceCallbackReportsSuccess'])
 def test_encrypted_invalid_and_request_frames_do_not_enter_ack_view(self):
  for flags in list(range(129,136))+[-1,256,True,None,128.5,0,64]:
   with self.assertRaises(ValueError):calibration_ack_view(flags,b'\0\0\1')
  with self.assertRaises(ValueError):calibration_ack_view(128,[0,0,1])
 def test_request_body_is_not_stripped_by_base_view(self):
  r=source_payload_view(64,b'\5\1',needs_ccode=True);self.assertIsNone(r['returnCode']);self.assertEqual(r['businessOffsetInPayload'],0);self.assertEqual(r['businessBodyHex'],'0501')
 def test_source_correlation_key_fields_and_int32(self):
  self.assertEqual(source_processor_key(4,8,1),0x04080001);self.assertEqual(source_processor_key(255,255,65535),-1);self.assertEqual(source_processor_key(0,0,0),0)
  for seq in (0,1,65535):self.assertNotEqual(source_processor_key(4,8,seq),source_processor_key(4,9,seq))
  for args in ((True,8,1),(4,256,1),(4,8,-1),(4,8,65536)):
   with self.assertRaises(ValueError):source_processor_key(*args)
 def test_mixed_dispatch_eligibility_is_not_transaction_completion(self):
  self.assertEqual(delivery_paths(is_block=False,is_mix=True),dict(processorPathEligible=True,pushPathEligible=True))
 def test_offset_checker_rejects_drift(self):
  rows=[(242,'const/16','v4, 11'),(270,'const/16','v4, 12'),(266,'iput','v1, v7, '+RECV+'->ccode I')]+[(o,op,'v1, +%03xh'%((target-o)//2)) for o,op,target in ((246,'if-ne',274),(254,'if-eqz',274),(280,'if-lez',302))]
  check_receive_offsets(rows)
  for bad in (rows[1:],[(o,op,'v4, 11' if o==270 else t) for o,op,t in rows],[(o,'if-eq' if o==246 else op,t) for o,op,t in rows]):
   with self.assertRaises(ValueError):check_receive_offsets(bad)
 def test_pinned_input_preflight(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'bad';p.write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'APK hash'):trace(p,p)
 def test_evidence_keeps_wire_business_and_physical_domains_separate(self):
  r=json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-calibration-ack-evidence.json').read_text());self.assertEqual(r['mapping']['ackBusinessPartInRawPayload'],1);self.assertEqual(r['mapping']['ackBusinessStatusInRawPayload'],2);self.assertEqual(r['callback']['gimbalSuccessReturnCode'],0);self.assertEqual(r['callback']['businessSuccessStatus'],1)
  self.assertFalse(r['sourceProcessor']['ackBitInKey']);self.assertFalse(r['sourceProcessor']['endpointsInKey']);self.assertEqual(r['sourceProcessor']['keyFields'],['cmdSet','cmdId','sequence'])
  for key in ('actualExtensionSelectionVerified','vendorCodeExecuted','hardwareTested','sdkInterfaceAdded','physicalCompletionVerified'):self.assertFalse(r['scope'][key])
if __name__=='__main__':unittest.main()
