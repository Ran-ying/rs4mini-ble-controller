import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_save_trace import BANKS,OWNER,ENUM,classify_reference,scan
class SaveTraceTests(unittest.TestCase):
    def test_direct_invoke_scope_differs_from_internal_references(self):
        text='v0, '+OWNER+'->start(Lcallback;)V'
        self.assertEqual(classify_reference('invoke-virtual',text,'Lui;'),'external-direct-invoke')
        self.assertEqual(classify_reference('invoke-virtual',text,OWNER),'internal-invoke')
        self.assertIsNone(classify_reference('invoke-virtual','v0, Lother;->start()V','Lui;'))

    def test_allocations_and_class_literals_are_not_direct_invocations(self):
        self.assertEqual(classify_reference('new-instance','v0, '+OWNER,'Lui;'),'allocation')
        self.assertEqual(classify_reference('const-class','v0, '+OWNER,'Lui;'),'class-literal')

    def test_enum_and_string_candidates_do_not_prove_callers_or_reflection(self):
        self.assertEqual(classify_reference('sget-object','v0, '+ENUM+'->SaveUserParams '+ENUM,'Lui;'),'command-enum-reference')
        self.assertEqual(classify_reference('const-string/jumbo','v0, dji.midware.data.model.P3.DataGimbalSaveUserParams','Lui;'),'string-literal-not-proven-reflection')
        self.assertEqual(classify_reference('iget','v0, v1, Lcontainer;->save LDataGimbalSaveUserParams;','Lui;'),'other-reference')

    def test_bad_apk_hash_rejected_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'other')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):scan(p,Path(d))

    def test_all_bank_hashes_checked_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'fixture')
            for bank in BANKS:(Path(d)/('business-%02d-code-restored.dex'%bank)).write_bytes(b'invalid bank')
            with patch('ronin_save_trace.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
                with self.assertRaisesRegex(ValueError,'restored bank hash mismatch: 00'):scan(p,Path(d))
