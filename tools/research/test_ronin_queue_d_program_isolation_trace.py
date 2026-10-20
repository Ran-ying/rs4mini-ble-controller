import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from ronin_queue_d_program_isolation_trace import PREFIX_BANKS, STATUS, scan

class QueueDTests(unittest.TestCase):
    def evidence(self):
        return json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-queue-d-program-isolation-evidence.json').read_text())
    def test_hash_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); apk=root/'apk'; apk.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'APK hash'): scan(apk, root)
            apk.write_bytes(b'apk'); pin=hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:
                    (root/('business-%02d-prefix-code-restored.dex'%b)).write_bytes(b'bad' if b==bad else b'bank')
                with patch('ronin_queue_d_program_isolation_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch('ronin_queue_d_program_isolation_trace.PREFIX_BANKS',{b:pin for b in PREFIX_BANKS}):
                    with self.assertRaisesRegex(ValueError,'bank hash'): scan(apk, root)
    def test_not_openable(self):
        e=self.evidence()
        self.assertEqual(e['status'], STATUS)
        self.assertFalse(e['pureGimbalProgramPrimitiveOpenable'])
        self.assertFalse(e['programExecutionOpened'])
        self.assertTrue(e['panoramaHasExposureField'])
        self.assertTrue(e['trackHasRecordOrPreviewField'])
        self.assertIn('mExposure', e['commands']['63']['doPackFields'])
        self.assertIn('mRecordOrPreview', e['commands']['62']['doPackFields'])
        self.assertEqual(e['hg724NamedProgramMethods'], [])
        self.assertTrue(e['missingHg724NamedCallerDoesNotProveNoInheritedEntry'])
        # Would fail if someone claimed 25/37 are camera-isolated solely due to no mExposure name
        self.assertIn('25', e['timelapsePackedInfoBytesUnresolvedForCameraIsolation'])
