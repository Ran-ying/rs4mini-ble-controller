import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_external_device import external_body,source_enum,trace,BANKS
class ExternalDeviceTests(unittest.TestCase):
 def test_signed_axis_order_and_type(self):
  r=external_body(bytes.fromhex('0207010080ff7f0000'));s=r['records'][0]['speedControl'];self.assertEqual((s['sourcePitchSpeed'],s['sourceRollSpeed'],s['sourceYawSpeed']),(-32768,32767,0));self.assertEqual(s['sourceControlType'],'CommonStick')
 def test_unsigned_type_and_unknown_preserved(self):
  for raw,name in ((0,'Other'),(1,'CommonStick'),(2,'RockWheel'),(3,'Sensor'),(7,'Other'),(128,'Other'),(255,'Other')):
   s=external_body(bytes((2,7,raw))+bytes(6))['records'][0]['speedControl'];self.assertEqual(s['rawControlType'],raw);self.assertEqual(s['sourceControlType'],name);self.assertEqual(s['sourceControlTypeKnown'],raw in (1,2,3,7))
 def test_duplicate_and_unknown_records_are_per_frame(self):
  r=external_body(bytes.fromhex('020701010002000300ff00020803fffffefffdffaa'));self.assertEqual(len(r['records']),3);self.assertEqual(r['records'][1]['sourceSignedTag'],-1);self.assertNotIn('speedControl',r['records'][1]);self.assertEqual(r['records'][2]['speedControl']['sourceYawSpeed'],-3);self.assertEqual(r['records'][2]['speedControl']['trailingHex'],'aa')
 def test_unknown_only_does_not_synthesize_previous_speeds(self):
  r=external_body(bytes.fromhex('0903010203'));self.assertNotIn('speedControl',r['records'][0]);self.assertFalse(r['unitVerified']);self.assertFalse(r['referenceFrameVerified']);self.assertFalse(r['targetDeviceVerified'])
 def test_malformed_headers_lengths_and_short_speed_record_reject(self):
  for body in (None,b'',b'\x02',bytes((2,6))+bytes(6),bytes((2,7))+bytes(6),bytes((9,128))+bytes(128),bytes((9,255)),bytes((9,0,1))):
   with self.assertRaises(ValueError):external_body(body)
 def test_signed_length_boundary_and_input_snapshot(self):
  body=bytearray((9,127))+bytearray(range(127));r=external_body(body);body[-1]=0;self.assertEqual(r['records'][0]['length'],127);self.assertTrue(r['records'][0]['payloadHex'].endswith('7e'))
 def test_enum_wire_id_not_ordinal(self):
  r=source_enum({'RockWheel':dict(arguments=['RockWheel',1,2],descriptor='(Ljava/lang/String; I I)V')});self.assertEqual(r,[dict(name='RockWheel',ordinal=1,sourceId=2)])
 def test_enum_unresolved_and_nonbyte_rejected(self):
  for args in (['Name',0,None],['Name',0,256],['Name',0,True],['Other',0,1]):
   with self.assertRaises(ValueError):source_enum({'Name':dict(arguments=args,descriptor='(Ljava/lang/String; I I)V')})
 def test_wrong_apk_precheck(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'apk';p.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(tmp))
 def test_every_bank_precheck_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'apk';p.write_bytes(b'fixture');pin=hashlib.sha256(b'bank').hexdigest()
   for bad in BANKS:
    for bank in BANKS:(Path(tmp)/('business-%02d-code-restored.dex'%bank)).write_bytes(b'bad' if bank==bad else b'bank')
    with patch('ronin_external_device.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()),patch('ronin_external_device.BANKS',{bank:pin for bank in BANKS}):
     with self.assertRaisesRegex(ValueError,'restored bank hash mismatch'):trace(p,Path(tmp))
 def test_evidence_limits_and_source_reset_distinction(self):
  r=json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-external-device-evidence.json').read_text());self.assertEqual(len(r['sourceTypes']),12);self.assertEqual(len(r['sourceSpeedControlTypes']),4);self.assertEqual(r['basePolicy']['commandId'],105);self.assertFalse(r['basePolicy']['isBlock']);self.assertTrue(r['basePolicy']['isMix']);self.assertEqual(len(r['methods']),36);self.assertEqual(len(r['directCallers']),1);self.assertEqual(r['typedMethodDeclarations'],[]);self.assertFalse(r['request']['ackRequested']);self.assertFalse(r['request']['receiverIdExplicitlyAssigned']);self.assertEqual({v['name']:v['sourceId'] for v in r['sourceSpeedControlTypes']}['Other'],7)
  for flag in ('appCodeExecuted','liveUiExecuted','targetDeviceVerified','modelLayoutVerified','wholeProtocolRecovered','sdkSendAdded','sdkReceiveAdded'):self.assertIs(r[flag],False)
  self.assertIs(r['receive']['sourceResetClearsControlType'],False);self.assertIs(r['receive']['sourceRetainsPreviousFieldsWhenMissing'],True);self.assertIs(r['request']['emptyBodyInActualTransportVerified'],False)
