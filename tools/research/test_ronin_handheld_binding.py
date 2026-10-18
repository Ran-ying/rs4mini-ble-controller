import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_handheld_binding import platform_cases,factory_choice,trace,PLATFORM,ARRAY,MOBILE
class HandheldBindingTests(unittest.TestCase):
 def case(self,name='HG724',value=25):
  return [('sget-object','v0, '+ARRAY),('sget-object','v1, '+PLATFORM+'->'+name+' '+PLATFORM),('invoke-virtual','v1, '+PLATFORM+'->ordinal()I'),('move-result','v1'),('const/16','v2, '+str(value)),('aput','v2, v0, v1')]
 def test_case_mapping_uses_assignment_not_ordinal(self):
  self.assertEqual(platform_cases(self.case()),{'HG724':25});self.assertEqual(platform_cases(self.case('Ronin2',18)),{'Ronin2':18})
 def test_from16_register_copy_preserves_literal(self):
  rows=self.case();rows[4:5]=[('const/4','v4, 25'),('move/from16','v2, v4')];self.assertEqual(platform_cases(rows),{'HG724':25})
 def test_other_switch_arrays_are_not_platform_assignments(self):
  rows=[('sget-object','v0, Lx;->other [I'),('const/4','v2, 9'),('aput','v2, v0, v1')]+self.case();self.assertEqual(platform_cases(rows),{'HG724':25})
 def test_conditional_duplicate_unknown_and_wide_producers_reject(self):
  rows=self.case()
  for bad in ([('goto','+002h')]+rows,rows+rows,rows[:4]+rows[5:],rows[:5]+[('move-wide','v1, v8')]+rows[5:],rows[:5]+[('sget','v2, Lx;->v I')]+rows[5:]):
   with self.assertRaises(ValueError):platform_cases(bad)
 def test_intervening_write_discards_pending_ordinal(self):
  rows=self.case();rows.insert(3,('const/4','v3, 1'))
  with self.assertRaises(ValueError):platform_cases(rows)
 def test_factory_distinguishes_mobile_base_and_no_registration(self):
  cases={'HG724':25,'OSMO':16,'Ronin2':18,'Unknown':35};targets={25:48,16:60,18:46}
  self.assertEqual(factory_choice('HG724',cases,targets)['selectedClass'],MOBILE);self.assertTrue(factory_choice('OSMO',cases,targets)['selectedClass'].endswith('/HandheldControllerAbstraction;'));self.assertIsNone(factory_choice('Ronin2',cases,targets)['selectedClass']);self.assertIsNone(factory_choice('Unknown',cases,targets)['selectedClass']);self.assertFalse(factory_choice('missing',cases,targets)['sourcePlatformKnown']);self.assertFalse(factory_choice('HG724',cases,targets)['actualPlatformVerified'])
  with self.assertRaises(ValueError):factory_choice(True,cases,targets)
  with self.assertRaises(ValueError):factory_choice('HG724',cases,{25:88})
 def test_preflight_input_hashes(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'a';p.write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'APK hash'):trace(p,p)
   with patch('ronin_handheld_binding.APK_SHA256',hashlib.sha256(b'bad').hexdigest()):
    with self.assertRaisesRegex(ValueError,'bank hash'):trace(p,p)
 def test_committed_binding_is_explicitly_conditional(self):
  r=json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-handheld-binding-evidence.json').read_text());self.assertEqual(r['platformCases']['HG724'],25);self.assertEqual(r['factoryTargets']['25'],48);self.assertEqual(r['hg724Factory']['selectedClass'],MOBILE);self.assertEqual(r['setter']['annotationKey'],'StickGimbalControlEnabled');self.assertTrue(r['setter']['methodNameDoesNotDefineMicrophoneSemantics']);self.assertTrue(r['scope']['sourceHg724FactoryAndSetterPathEstablished']);self.assertTrue(r['factoryArgument']['argumentOneIsNotReceiverId'])
  self.assertEqual(r['keyFields'][0]['rawAnnotations'][0]['elements']['types'],['Ljava/lang/Boolean;']);self.assertTrue(r['keyFields'][0]['selection']['sourceSupport']);self.assertTrue(r['keyFields'][0]['selection']['selectionUnambiguous'])
  for key in ('actualPlatformVerified','reflectionExecuted','reflectionAndMethodInvocationSucceededVerified','hardwareTested','vendorCodeExecuted','sdkSendAdded'):self.assertFalse(r['scope'][key])
if __name__=='__main__':unittest.main()
