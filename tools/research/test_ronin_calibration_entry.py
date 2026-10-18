import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_calibration_entry import (canonical_version_number,visibility_case,action_case,threshold_literal,model_predicate,trace,COMMON,SUPPORTED,MODEL,THRESHOLD)
class CalibrationEntryTests(unittest.TestCase):
 def test_version_uses_decimal_components_and_base256(self):
  self.assertEqual(canonical_version_number(THRESHOLD),139289);self.assertEqual(canonical_version_number('00.02.32.26'),139290);self.assertEqual(canonical_version_number(None),0);self.assertEqual(canonical_version_number(''),0)
 def test_canonical_parser_domain_and_long_overflow(self):
  for value in (True,2,'x','1..2','-1.2','1.','2147483648'):
   with self.assertRaises(ValueError):canonical_version_number(value)
  self.assertEqual(canonical_version_number('1.0.0.0.0.0.0.0.0'),0)
 def test_threshold_strict_greater_not_equal(self):
  for version,expected in (('00.02.32.24',False),(THRESHOLD,False),('00.02.32.26',True)):
   self.assertIs(visibility_case('RONINS','RONINS',imu_outcome='success',imu_version=version)['advancedVisible'],expected)
 def test_hg724_branch_bypasses_version_but_normal_is_hidden(self):
  r=visibility_case('HG724','HG724',imu_outcome='failure',imu_version='invalid-but-not-read');self.assertIs(r['advancedVisible'],True);self.assertIs(r['normalVisible'],False);self.assertIs(r['versionQueryRequired'],False);self.assertIs(r['liveVisibilityVerified'],False)
 def test_selected_item_and_cached_product_must_remain_independent(self):
  a=visibility_case('HG724','RONIN2');b=visibility_case('RONIN2','HG724');self.assertIs(a['normalVisible'],True);self.assertIs(a['advancedVisible'],True);self.assertIs(b['normalVisible'],False);self.assertIsNone(b['advancedVisible']);self.assertIs(b['versionQueryRequired'],True)
 def test_second_third_and_newer_branch_sets(self):
  for model in ('HG702','HG710','HG703','HG711','HG720','HG704','HG714','HG724','HG705','HG715'):
   self.assertIs(visibility_case(model,None)['advancedVisible'],True)
  self.assertIs(visibility_case('HG701','RONINSC',imu_outcome='failure')['normalVisible'],True)
 def test_unobserved_version_is_not_assumed_success_or_failure(self):
  self.assertIsNone(visibility_case(None,None)['advancedVisible']);self.assertIs(visibility_case(None,None,imu_outcome='failure')['advancedVisible'],False)
  for args in ((True,None),(None,1)):
   with self.assertRaises(ValueError):visibility_case(*args)
  with self.assertRaises(ValueError):visibility_case(None,None,imu_outcome='guess')
 def test_motor_gate_and_visible_gate_are_distinct(self):
  self.assertIs(visibility_case('HG724','HG724')['normalVisible'],False)
  self.assertEqual(action_case('normal',motor_enabled=True)['bodyHex'],'05');self.assertEqual(action_case('advanced',motor_enabled=True)['bodyHex'],'00');self.assertIsNone(action_case('advanced',motor_enabled=False)['bodyHex'])
  for value in (None,0,1):
   with self.assertRaises(ValueError):action_case('advanced',motor_enabled=value)
  with self.assertRaises(ValueError):action_case('other',motor_enabled=True)
 def test_threshold_field_producer_is_explicit(self):
  ops=[('const-string/jumbo','v1, '+THRESHOLD),('invoke-static','v1, '+COMMON+'->formatVersion(Ljava/lang/String;)J'),('move-result-wide','v1'),('sput-wide','v1, '+SUPPORTED+'->IMU_VERSION_SUPPORT_ADVANCED_CALIBRATION J')]
  self.assertEqual(threshold_literal(ops),THRESHOLD)
  for wrong in (ops+ops,ops[1:],ops[:2]+[('move-result','v1')]+ops[3:]):
   with self.assertRaises(ValueError):threshold_literal(wrong)
 def test_cache_predicate_cannot_be_inferred_from_method_name(self):
  ops=[('const-string/jumbo','v1, ModelName'),('invoke-static','v1, Ldji/sdksharedlib/extension/CacheHelper;->getProduct(Ljava/lang/String;)Ljava/lang/Object;'),('move-result-object','v1'),('sget-object','v0, '+MODEL+'->RONINSC '+MODEL),('if-ne','v1, v0, +004h'),('const/4','v1, 1'),('return','v1'),('const/4','v1, 0'),('return','v1')]
  self.assertEqual(model_predicate(ops),'RONINSC')
  with self.assertRaises(ValueError):model_predicate(ops[:-1])
 def test_apk_hash_guard(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'apk';p.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(tmp))
 def test_both_bank_hashes_checked_before_parser(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'apk';p.write_bytes(b'fixture');pin=hashlib.sha256(b'bank').hexdigest()
   for bad in (3,5):
    for bank in (3,5):(Path(tmp)/('business-%02d-code-restored.dex'%bank)).write_bytes(b'bad' if bank==bad else b'bank')
    with patch('ronin_calibration_entry.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()),patch('ronin_calibration_entry.BANKS',{3:pin,5:pin}):
     with self.assertRaisesRegex(ValueError,'restored bank hash mismatch'):trace(p,Path(tmp))
 def test_evidence_keeps_live_and_firmware_conditions_unproven(self):
  r=json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-calibration-entry-evidence.json').read_text());self.assertEqual(len(r['methods']),63);self.assertEqual(len(r['layouts']),2);self.assertEqual(r['sourceActions']['normal']['bodyHex'],'05');self.assertEqual(r['sourceActions']['advanced']['bodyHex'],'00');self.assertIs(r['sourceActions']['uiSystemCalibrationIsSystemCalc'],False)
  self.assertEqual(r['lifecycle']['advancedAckStartsUiTimerMs'],60000);self.assertIs(r['lifecycle']['transitiveFirmwareStopProven'],False);self.assertIs(r['scope']['fullActivityReachabilityVerified'],False)
  for flag in ('appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded'):self.assertIs(r[flag],False)
