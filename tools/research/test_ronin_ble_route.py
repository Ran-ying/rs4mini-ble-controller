import json,tempfile,unittest
from pathlib import Path
from ronin_ble_route import literal_boolean_writes,link_switch_value,fresh_ble_receive_case,trace,TYPE,MAIN,MANAGER
FIELD='Ldji/midware/data/manager/P3/DJIPackManagerBase;->needCheckEncrypt Z'
class BleRouteTests(unittest.TestCase):
 def test_literal_writes_preserve_order_and_actual_values(self):
  ops=[('const/4','v0, 1'),('iput-boolean','v0, v1, '+FIELD),('const/4','v0, 0'),('iput-boolean','v0, v1, '+FIELD)]
  self.assertEqual([r['value'] for r in literal_boolean_writes(ops)],[True,False]);self.assertEqual([r['instructionIndex'] for r in literal_boolean_writes(ops)],[1,3])
 def test_moves_keep_literals(self):
  ops=[('const/4','v0, 1'),('move/from16','v2, v0'),('iput-boolean','v2, v1, '+FIELD)]
  self.assertTrue(literal_boolean_writes(ops)[0]['value'])
 def test_branches_and_unknown_destinations_clear_old_values(self):
  for middle in [('if-eqz','v4, +002h'),('goto','+002h'),('move-result','v0'),('sget','v0, Lx;->v I'),('add-int/lit8','v0, v0, 1')]:
   with self.assertRaises(ValueError):literal_boolean_writes([('const/4','v0, 1'),middle,('iput-boolean','v0, v1, '+FIELD)])
 def test_wide_writes_invalidate_adjacent_register(self):
  with self.assertRaises(ValueError):literal_boolean_writes([('const/4','v1, 1'),('move-wide','v0, v4'),('iput-boolean','v1, v2, '+FIELD)])
 def test_boolean_requires_resolved_zero_or_one(self):
  for ops in [[('iput-boolean','v0, v1, '+FIELD)],[('const/4','v0, 2'),('iput-boolean','v0, v1, '+FIELD)]]:
   with self.assertRaises(ValueError):literal_boolean_writes(ops)
  self.assertEqual(literal_boolean_writes([('iput-boolean','v0, v1, Lx;->unrelated Z')]),[])
 def switch(self):
  return [('sget-object','v1, '+TYPE+'->BLE '+TYPE),('invoke-virtual','v1, '+TYPE+'->ordinal()I'),('move-result','v1'),('const/4','v2, 3'),('aput','v2, v0, v1')]
 def test_switch_case_is_literal_not_enum_ordinal(self):
  self.assertEqual(link_switch_value(self.switch(),'BLE'),3)
 def test_switch_rejects_wrong_register_missing_or_duplicate(self):
  s=self.switch()
  for ops in [s[:-1],s+s,[],s[:4]+[('aput','v3, v0, v1')],s[:2]+[('move-result','v2')]+s[3:]]:
   with self.assertRaises(ValueError):link_switch_value(ops,'BLE')
 def test_source_ble_constructor_policy_classifies_all_flag_bytes(self):
  for flags in range(256):
   r=fresh_ble_receive_case(4,8,flags,prior_old_state=True);self.assertEqual(r['sourceWouldCallNativeDecrypt'],flags&7==3);self.assertEqual(r['sourceOldFirmwareState'],flags&7!=3);self.assertFalse(r['deviceModeVerified'])
 def test_source_ble_prior_state_is_explicit_and_common_retains_it(self):
  for state in (True,False):self.assertEqual(fresh_ble_receive_case(0,1,0,prior_old_state=state)['sourceOldFirmwareState'],state)
  for state in (None,0,'old'):
   with self.assertRaises(ValueError):fresh_ble_receive_case(4,8,0,prior_old_state=state)
 def test_hash_preflight(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'a.apk';p.write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'APK hash'):trace(p,Path(tmp))
 def test_committed_evidence_resolves_source_not_live_state(self):
  r=json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-ble-route-evidence.json').read_text());p=r['sourceBlePolicy']
  self.assertEqual((p['managerClass'],p['parseInheritedFrom']),(MAIN,MANAGER));self.assertTrue(p['needCheckEncrypt']);self.assertTrue(p['enabledSetDataEvent']);self.assertTrue(p['encryptionSingletonSharedWithDataBase']);self.assertTrue(p['sourceRouteResolved']);self.assertFalse(p['actualSessionStateVerified'])
  self.assertEqual(len(r['directPolicyFieldWriters']),5);self.assertEqual(r['sourceLinkSelection']['switchCaseValue'],3);self.assertTrue(r['sourceLinkSelection']['requiresAliveDaemon'])
  for key in ('appOrJniExecuted','liveBleOrHardwareTested','peerEncryptionAcceptanceVerified','reflectionOrNativeFieldWritesExcluded'):self.assertFalse(r['scope'][key])
  self.assertEqual(len(r['sourceReceiveRoute']),7);self.assertEqual(len(r['sourceSendRoute']),8)
if __name__=='__main__':unittest.main()
