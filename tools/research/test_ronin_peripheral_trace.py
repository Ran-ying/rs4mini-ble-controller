import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_peripheral_trace import source_int,source_conversion,getter_spec,peripheral_body,trace,TYPE,MODEL
class PeripheralTraceTests(unittest.TestCase):
 def test_all_widths_keep_source_padding_sign_and_narrowing(self):
  self.assertEqual([source_int(bytes([255])*n) for n in range(10)],[0,-1,-1,16777215,-1,-1,-1,-1,-1,-1])
  self.assertEqual(source_int(bytes.fromhex('ffffffff00000000')),-1)
 def test_source_float_and_gps_order(self):
  self.assertEqual(source_conversion(2147483647,'float32-div10'),214748368.0)
  self.assertEqual(source_conversion(-2999999,'int-div1000000-to-double'),-2.0)
  self.assertTrue(source_conversion(-2,'masked3-equals2'))
 def test_unknown_conversion_and_invalid_int_rejected(self):
  for v in (True,2**31):
   with self.assertRaises(ValueError):source_conversion(v,'int32')
  with self.assertRaises(ValueError):source_conversion(1,'guess')
 def test_shared_golden_contracts(self):
  root=Path(__file__).resolve().parents[2];catalog=json.loads((root/'protocol/research/ronin-peripheral-evidence.json').read_text())['catalog']
  for vector in json.loads((root/'node/test/fixtures/peripheral-status.json').read_text()):
   result=peripheral_body(bytes.fromhex(vector['bodyHex']),catalog)
   for k,v in vector['expected'].items():self.assertEqual(result[k],v,vector['name'])
 def test_signed_length_and_truncation_rejected(self):
  for b in (b'',b'\1\2',b'\1\2\2\0',bytes([1,2,128])+bytes(128)):
   with self.assertRaises(ValueError):peripheral_body(b,dict(types=[],getters=[]))
 def getter(self):
  return [('sget-object','v0, '+TYPE+'->Channel1 '+TYPE),('invoke-direct','v1, v0, '+MODEL+'->getIntValue('+TYPE+')I'),('move-result','v0'),('return','v0')]
 def test_integer_getter_binds_exact_type_and_return_register(self):
  self.assertEqual(getter_spec('getChannel1','()I',self.getter(),{'Channel1':0})['sourceId'],0)
  ops=self.getter();ops[-1]=('return','v9')
  with self.assertRaises(ValueError):getter_spec('getChannel1','()I',ops,{'Channel1':0})
 def test_unknown_field_and_nonempty_stub_rejected(self):
  with self.assertRaises(ValueError):getter_spec('getChannel1','()I',self.getter(),{})
  with self.assertRaises(ValueError):getter_spec('stub','()V',[('const/4','v0, 0'),('return-void','')],{})
  self.assertIsNone(getter_spec('stub','()V',[('return-void','')],{}))
 def test_apk_hash_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))
 def test_bank_hash_before_optional_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'fixture');(Path(d)/'business-05-code-restored.dex').write_bytes(b'bad')
   with patch('ronin_peripheral_trace.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
    with self.assertRaisesRegex(ValueError,'bank hash mismatch'):trace(p,Path(d))
