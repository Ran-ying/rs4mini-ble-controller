import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_stick_trace import source_stick_body,source_enable_body,short_context,trace,BANKS,PUSH
class StickTraceTests(unittest.TestCase):
    def prefix(self,offset=0,width=2,kind='Short'):
        return [('const-class','v0, Ljava/lang/'+kind+';'),('const/4','v1, '+str(offset)),('const/4','v3, '+str(width)),('new-array','v2, v1, [I'),('invoke-virtual','v4, v1, v3, v0, v2, '+PUSH+'->get(I I Ljava/lang/Class; [I)Ljava/lang/Number;')]
    def test_signed_short_boundaries(self):
        r=source_stick_body(bytes.fromhex('0080ff7f0380'));self.assertEqual((r['sourceStickX'],r['sourceStickY']),(-32768,32767));self.assertEqual(r['rawStateWord'],32771);self.assertEqual(r['unknownStateBits'],32768)
    def test_source_flags_unknown_bits_and_owned_tail(self):
        b=bytearray.fromhex('ffff000003ffab');r=source_stick_body(b);b[-1]=0;self.assertTrue(r['sourceTriggerPressed']);self.assertTrue(r['sourceStickControlEnabled']);self.assertEqual(r['bodyHex'],'ffff000003ffab');self.assertEqual(r['unknownStateBits'],65280)
    def test_body_requires_six_known_bytes_without_zero_fill(self):
        for b in (bytes(5),'000000000000',[0]*6,None):
            with self.assertRaises(ValueError):source_stick_body(b)
    def test_enable_source_is_one_explicit_boolean(self):
        self.assertEqual(source_enable_body(False),b'\0');self.assertEqual(source_enable_body(True),b'\1')
        for v in (0,1,255,'yes',None):
            with self.assertRaises(ValueError):source_enable_body(v)
    def test_signed_short_getter_offsets(self):
        for offset in (0,2,4):self.assertEqual(short_context(self.prefix(offset)),(offset,[]))
    def test_other_numeric_widths_classes_or_branches_rejected(self):
        for ops in (self.prefix(width=1),self.prefix(kind='Integer'),[('if-eqz','v1, +003h')]+self.prefix()):
            with self.assertRaises(ValueError):short_context(ops)
    def test_apk_precheck_before_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))
    def test_bank_prechecks_before_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'fixture')
            for bank in BANKS:(Path(d)/('business-%02d-code-restored.dex'%bank)).write_bytes(b'wrong')
            with patch('ronin_stick_trace.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
                with self.assertRaisesRegex(ValueError,'restored bank hash mismatch: 00'):trace(p,Path(d))
