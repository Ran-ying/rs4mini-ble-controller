import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from ronin_program_prefix_trace import PREFIX_BANKS, scan

class ProgramPrefixTraceTests(unittest.TestCase):
    def test_hashes_checked_before_parser(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t); p=d/'apk'; p.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'APK hash'): scan(p,d)
            p.write_bytes(b'apk'); pin=hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS: (d/('business-%02d-prefix-code-restored.dex'%b)).write_bytes(b'bad' if b==bad else b'bank')
                with patch('ronin_program_prefix_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch('ronin_program_prefix_trace.PREFIX_BANKS',{b:pin for b in PREFIX_BANKS}):
                    with self.assertRaisesRegex(ValueError,'bank hash'): scan(p,d)

    def evidence(self):
        return json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-program-prefix-evidence.json').read_text())

    def test_no_hg724_named_callers_and_no_program_send(self):
        r=self.evidence()
        self.assertEqual(r['hg724NamedProgramCallers'], [])
        self.assertFalse(r['pureGimbalProgramPrimitiveOpenable'])
        self.assertFalse(r['programExecutionOpened'])
        self.assertTrue(r['cameraFieldsInterleavedWithPanorama'])
        self.assertTrue(r['trackRecordPreviewInterleaved'])
        self.assertFalse(r['reliableStopWithCameraIsolationEstablished'])
        self.assertIn('mExposure', r['panoramaDoPackFields'])
        self.assertEqual(len(r['commands']['25']['externalDirectCallers']), 12)
        self.assertEqual(len(r['commands']['37']['externalDirectCallers']), 3)
        self.assertEqual(len(r['commands']['62']['externalDirectCallers']), 12)
        self.assertEqual(len(r['commands']['63']['externalDirectCallers']), 4)
        self.assertEqual(r['newBanks01And07External'], [])
        for flag in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','sdkSendAdded','sdkReceiveAdded']:
            self.assertFalse(r[flag])
