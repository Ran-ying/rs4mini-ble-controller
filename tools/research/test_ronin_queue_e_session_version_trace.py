import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from ronin_queue_e_session_version_trace import PREFIX_BANKS, STATUS, scan
from ronin_activation_receive import activation_version_ack_view, source_payload_view

class QueueETests(unittest.TestCase):
    def evidence(self):
        return json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-queue-e-session-version-evidence.json').read_text())
    def test_hash_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); apk=root/'apk'; apk.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'APK hash'): scan(apk, root)
            apk.write_bytes(b'apk'); pin=hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:
                    (root/('business-%02d-prefix-code-restored.dex'%b)).write_bytes(b'bad' if b==bad else b'bank')
                with patch('ronin_queue_e_session_version_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch('ronin_queue_e_session_version_trace.PREFIX_BANKS',{b:pin for b in PREFIX_BANKS}):
                    with self.assertRaisesRegex(ValueError,'bank hash'): scan(apk, root)
    def test_version_view_rejects_mixing_failure(self):
        flags=None
        for f in range(256):
            try:
                if source_payload_view(f, bytes([0,0]), needs_ccode=True).get('isAck'):
                    flags=f; break
            except Exception:
                pass
        self.assertIsNotNone(flags)
        bad=activation_version_ack_view(flags, bytes.fromhex('0101'))
        self.assertFalse(bad['sourceCallbackReportsSuccess'])
        self.assertIsNone(bad.get('versionName'))
    def test_exhausted(self):
        e=self.evidence()
        self.assertEqual(e['status'], STATUS)
        self.assertTrue(e['getVer']['setRecDataUpdatesGimbalActiveStatusVersion'])
        self.assertTrue(e['pushActiveStatus']['setPushRecDataCallsSetRecDataBeforeLengthAndAckGates'])
        self.assertFalse(e['liveSessionTableAndCorrelationVerified'])
        self.assertFalse(e['activationWriteOpened'])
        self.assertTrue(e['versionQueryMustNotBeInterpretedAsActivationStatusWithoutRequestContext'])
