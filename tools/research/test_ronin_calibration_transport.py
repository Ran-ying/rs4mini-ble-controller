import json,tempfile,unittest
from pathlib import Path
from ronin_calibration_transport import (source_need_encrypt,source_send_case,source_receive_case,branch_target,check_need_branches,command_set_values,trace,CONFIG)
class CalibrationTransportTests(unittest.TestCase):
 def test_gimbal_all_command_bytes_need_encrypt(self):
  for command in range(256):self.assertTrue(source_need_encrypt(4,command))
 def test_common_excluded_and_camera_is_two_not_one(self):
  for command in range(256):
   self.assertFalse(source_need_encrypt(0,command));self.assertEqual(source_need_encrypt(2,command),command not in (16,17,112,113));self.assertTrue(source_need_encrypt(1,command))
 def test_explicit_source_state_controls_send(self):
  self.assertFalse(source_send_case(4,8,old_firmware_state=True)['sourceWouldEncrypt']);self.assertTrue(source_send_case(4,8,old_firmware_state=False)['sourceWouldEncrypt']);self.assertFalse(source_send_case(0,8,old_firmware_state=False)['sourceWouldEncrypt'])
  for bad in (None,1,'old'):
   with self.assertRaises(ValueError):source_send_case(4,8,old_firmware_state=bad)
 def test_simple_receive_sets_false_only_under_enabled_event(self):
  for flags in range(256):
   r=source_receive_case(4,8,flags,old_firmware_state=True,need_check=True,enabled_event=True);simple=flags&7==3
   self.assertEqual(r['sourceWouldCallNativeDecrypt'],simple);self.assertEqual(r['sourceOldFirmwareState'],not simple);self.assertFalse(r['deviceModeVerified'])
 def test_disabled_event_does_not_skip_classification(self):
  r=source_receive_case(4,8,3,old_firmware_state=False,need_check=True,enabled_event=False);self.assertTrue(r['sourceOldFirmwareState']);self.assertFalse(r['sourceWouldCallNativeDecrypt'])
 def test_outer_gate_retains_state(self):
  for state in (False,True):
   for enabled in (False,True):
    r=source_receive_case(4,8,3,old_firmware_state=state,need_check=False,enabled_event=enabled);self.assertEqual(r['sourceOldFirmwareState'],state);self.assertFalse(r['sourceWouldCallNativeDecrypt'])
 def test_non_simple_common_preserves_state(self):
  for state in (True,False):self.assertEqual(source_receive_case(0,1,0,old_firmware_state=state,need_check=True,enabled_event=True)['sourceOldFirmwareState'],state)
 def test_domains_are_explicit(self):
  for bad in (-1,256,True,None,1.5):
   with self.assertRaises(ValueError):source_need_encrypt(bad,8)
   with self.assertRaises(ValueError):source_need_encrypt(4,bad)
   with self.assertRaises(ValueError):source_receive_case(4,8,bad,old_firmware_state=True,need_check=True,enabled_event=True)
  with self.assertRaises(ValueError):source_receive_case(4,8,0,old_firmware_state=True,need_check=1,enabled_event=True)
 def test_branch_displacements_use_code_units(self):
  self.assertEqual(branch_target(60,'v0, v1, +01ah'),112);self.assertEqual(branch_target(60,'v0, -002h'),56)
  with self.assertRaises(ValueError):branch_target(60,'v0, v1')
 def test_reviewed_branch_shape_rejects_changed_target_or_return(self):
  rows=[(off,op,'v0, v1, +%03xh'%((target-off)//2)) for off,op,target in ((44,'if-eq',116),(60,'if-ne',112),(76,'if-ne',116),(84,'if-eq',116),(92,'if-eq',116),(100,'if-eq',116),(108,'if-eq',116))]+[(112,'const/4','v3, 1'),(114,'return','v3'),(116,'const/4','v3, 0'),(118,'return','v3')]
  check_need_branches(rows)
  for bad in (rows[1:],rows[:-1],[(o,op,'v3, 0' if o==112 else t) for o,op,t in rows],[(o,op,'v0, v1, +01ch' if o==60 else t) for o,op,t in rows]):
   with self.assertRaises(ValueError):check_need_branches(bad)
 def test_command_set_parser_does_not_use_ordinal(self):
  owner=CONFIG+'CmdSet;';ops=[('const-string/jumbo','v1, CAMERA'),('const/4','v2, 99'),('const/4','v3, 2'),('invoke-direct','v0, v1, v2, v3, v4, '+owner+'-><init>(Ljava/lang/String; I I Ldji/midware/data/config/P3/DJICmdSetBase;)V')]
  self.assertEqual(command_set_values(ops,{'CAMERA'}),{'CAMERA':2})
  for wrong in (ops+ops,[('if-eqz','v0, +002h')]+ops,ops[:2]+[('new-instance','v3, Lx;')]+ops[3:]):
   with self.assertRaises(ValueError):command_set_values(wrong,{'CAMERA'})
 def test_artifact_hash_preflight(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'bad.apk';p.write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'APK hash'):trace(p,Path(tmp))
 def test_committed_evidence_is_source_not_hardware(self):
  r=json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-calibration-transport-evidence.json').read_text())
  self.assertEqual(r['freshCalibration']['preConditionalFlags'],64);self.assertEqual(r['enumValues']['DataConfig$NEEDACK']['YES'],2);self.assertEqual(r['enumValues']['CmdSet']['CAMERA'],2)
  self.assertTrue(r['conditionalReceive']['disabledEventStillRunsPredicate']);self.assertEqual(len(r['directSetterCallers']),1);self.assertEqual(r['directSetterCallers'][0]['invokeCount'],2)
  for key in ('vendorCodeExecuted','hardwareTested','actualBleManagerPolicyVerified','cryptoAlgorithmImplemented'):self.assertFalse(r['scope'][key])
if __name__=='__main__':unittest.main()
