import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from ronin_queue_c_completion_abort_trace import PREFIX_BANKS, STATUS, scan

class QueueCTests(unittest.TestCase):
    def evidence(self):
        return json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-queue-c-completion-abort-evidence.json').read_text())
    def test_hash_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); apk=root/'apk'; apk.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'APK hash'): scan(apk, root)
            apk.write_bytes(b'apk'); pin=hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:
                    (root/('business-%02d-prefix-code-restored.dex'%b)).write_bytes(b'bad' if b==bad else b'bank')
                with patch('ronin_queue_c_completion_abort_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch('ronin_queue_c_completion_abort_trace.PREFIX_BANKS',{b:pin for b in PREFIX_BANKS}):
                    with self.assertRaisesRegex(ValueError,'bank hash'): scan(apk, root)
    def test_exhausted(self):
        e=self.evidence()
        self.assertEqual(e['status'], STATUS)
        self.assertTrue(e['rotateCompletion']['usesAbsStartNoCallback'])
        self.assertFalse(e['rotateCompletion']['hostSuccessTiedToAck'])
        self.assertFalse(e['rotateCompletion']['hostSuccessTiedToPhysicalArrival'])
        self.assertFalse(e['firmwareCompletionOrAbortVerified'])
        self.assertEqual(len(e['absStartInvokeSites']), 1)
        self.assertFalse(e['absStartInvokeSites'][0]['usesCallback'])
        self.assertFalse(e['sendOpened'])
