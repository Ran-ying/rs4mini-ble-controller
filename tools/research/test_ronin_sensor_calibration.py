import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_sensor_calibration import source_start_body,auto_calibration_response_body,sensor_progress_body,trace,BANKS,PARTS,AUTO,PUSH,UNBOUND
from ronin_program_receive import source_payload_view
class SensorCalibrationTests(unittest.TestCase):
 def test_source_parts_are_explicit_single_byte_not_arbitrary_raw_value(self):
  for value,name in enumerate(PARTS):self.assertEqual(source_start_body(name),bytes((value,)))
  for value in (None,0,True,'auto','unknown'):
   with self.assertRaises(ValueError):source_start_body(value)
 def test_known_08_response_states(self):
  for raw,name in enumerate(('FAIL','SUCCESS','PROCESSING')):
   r=auto_calibration_response_body(bytes((5,raw)));self.assertEqual(r['sourcePart'],'GYRO');self.assertEqual(r['sourceStatus'],name);self.assertTrue(r['sourceStatusKnown'])
 def test_unknown_08_fallback_preserves_raw_without_physical_claim(self):
  r=auto_calibration_response_body(bytes.fromhex('fffeaa'));self.assertEqual(r['rawPart'],255);self.assertEqual(r['sourcePart'],'AUTO');self.assertFalse(r['sourcePartKnown']);self.assertEqual(r['rawStatus'],254);self.assertEqual(r['sourceStatus'],'PROCESSING');self.assertFalse(r['sourceStatusKnown']);self.assertEqual(r['trailingHex'],'aa');self.assertFalse(r['physicalCompletionVerified'])
 def test_full_progress_byte_not_clamped(self):
  for value in range(256):
   r=sensor_progress_body(bytes((value,1)));self.assertEqual(r['rawProgressValue'],value);self.assertEqual(r['sourceStatus'],'PROCESSING');self.assertFalse(r['progressUnitVerified'])
 def test_sensor_status_uses_explicit_ids_not_ordinal_or_bool(self):
  known={0:'COMPLETE',1:'PROCESSING',3:'FAIL',9:'OTHER'}
  for raw in range(256):
   r=sensor_progress_body(bytes((50,raw)));self.assertEqual(r['rawStatus'],raw);self.assertEqual(r['sourceStatus'],known.get(raw,'OTHER'));self.assertEqual(r['sourceStatusKnown'],raw in known)
  self.assertEqual(sensor_progress_body(bytes((0,2)))['sourceStatus'],'OTHER');self.assertEqual(sensor_progress_body(bytes((0,3)))['sourceStatus'],'FAIL')
 def test_two_status_domains_must_not_be_conflated(self):
  self.assertEqual(auto_calibration_response_body(bytes((0,1)))['sourceStatus'],'SUCCESS');self.assertEqual(sensor_progress_body(bytes((0,1)))['sourceStatus'],'PROCESSING')
  self.assertEqual(auto_calibration_response_body(bytes((0,0)))['sourceStatus'],'FAIL');self.assertEqual(sensor_progress_body(bytes((0,0)))['sourceStatus'],'COMPLETE')
 def test_ack_return_code_context_is_external_to_business_fields(self):
  for code in (0,7):
   view=source_payload_view(128,bytes((code,5,1)),needs_ccode=True);self.assertEqual(view['returnCode'],code);r=auto_calibration_response_body(bytes.fromhex(view['businessBodyHex']));self.assertEqual(r['sourcePart'],'GYRO');self.assertEqual(r['sourceStatus'],'SUCCESS');self.assertFalse(r['physicalCompletionVerified'])
 def test_short_body_rejected_not_synthetic_processing_or_zero(self):
  for helper in (auto_calibration_response_body,sensor_progress_body):
   for value in (None,[],True,'00',b'',b'\0'):
    with self.assertRaises(ValueError):helper(value)
 def test_tail_and_snapshot(self):
  body=bytearray((255,3,170));r=sensor_progress_body(body);body[0]=0;self.assertEqual(r['bodyHex'],'ff03aa');self.assertEqual(r['trailingHex'],'aa');self.assertFalse(r['targetDeviceVerified']);self.assertFalse(r['physicalCompletionVerified'])
 def test_apk_precheck_before_parser(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'apk';p.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(tmp))
 def test_all_banks_prechecked_before_parser(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'apk';p.write_bytes(b'fixture');pin=hashlib.sha256(b'bank').hexdigest()
   for bad in BANKS:
    for bank in BANKS:(Path(tmp)/('business-%02d-code-restored.dex'%bank)).write_bytes(b'bad' if bank==bad else b'bank')
    with patch('ronin_sensor_calibration.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()),patch('ronin_sensor_calibration.BANKS',{b:pin for b in BANKS}):
     with self.assertRaisesRegex(ValueError,'restored bank hash mismatch'):trace(p,Path(tmp))
 def test_evidence_binds_correct_sensor_class_and_preserves_limits(self):
  r=json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-sensor-calibration-evidence.json').read_text());self.assertEqual(len(r['methods']),48);self.assertEqual(len(r['directCallers']),17);self.assertEqual(len(r['typedMethodDeclarations']),9);self.assertEqual(len(r['externalEnumReferences']),9)
  self.assertEqual(r['basePolicies'][1]['modelClass'],PUSH);self.assertNotEqual(PUSH,UNBOUND);self.assertEqual({v['name']:v['sourceId'] for v in r['sensorStates']},{'COMPLETE':0,'PROCESSING':1,'FAIL':3,'OTHER':9})
  self.assertIs(r['sourceFacts']['pushStartIsInert'],True);self.assertIs(r['sourceFacts']['unboundClassAssignedTo30InBaseTable'],False)
  for flag in ('appCodeExecuted','liveUiExecuted','targetDeviceVerified','modelLayoutVerified','wholeProtocolRecovered','sdkSendAdded','sdkReceiveAdded'):self.assertIs(r[flag],False)
