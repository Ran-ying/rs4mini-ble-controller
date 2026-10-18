import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_component_motor_gate import source_motor_enabled,trace
class ComponentMotorGateTests(unittest.TestCase):
 def test_uint8_motor_gate_inverts_only_bit_zero(self):
  for v in range(256):self.assertEqual(source_motor_enabled(v),v%2==0)
 def test_gate_input_is_explicit_uint8(self):
  for v in (-1,256,True,None,1.5):
   with self.assertRaises(ValueError):source_motor_enabled(v)
 def test_hash_preflight(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'a';p.write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'APK hash'):trace(p,p)
   with patch('ronin_component_motor_gate.APK_SHA256',hashlib.sha256(b'bad').hexdigest()):
    with self.assertRaisesRegex(ValueError,'bank hash'):trace(p,p)
 def test_evidence_maps_source_cache_not_physical_state(self):
  r=json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-component-motor-gate-evidence.json').read_text());self.assertEqual(len(r['methods']),3);self.assertEqual((r['parameter']['index'],r['parameter']['size']),(35,1));self.assertTrue(r['sourceCache']['enabledWhenBit0IsZero']);self.assertFalse(r['sdkPreflight']['autoEnableMotors']);self.assertFalse(r['sdkPreflight']['atomicWithFirmwareCalibration']);self.assertFalse(r['actualMotorPhysicalStateVerified']);self.assertFalse(r['hardwareTested']);self.assertFalse(r['vendorCodeExecuted'])
if __name__=='__main__':unittest.main()
