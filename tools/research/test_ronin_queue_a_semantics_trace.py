import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ronin_queue_a_semantics_trace import (
    PREFIX_BANKS, protocol_gimbal_id, scan, source_need_encrypt, STATUS_EXHAUSTED,
)


class QueueASemanticsTests(unittest.TestCase):
    def evidence(self):
        return json.loads(
            (Path(__file__).resolve().parents[2] / 'protocol/research/ronin-queue-a-semantics-evidence.json').read_text()
        )

    def test_helpers_match_java_contracts(self):
        self.assertEqual(protocol_gimbal_id(1), 2)
        self.assertEqual(protocol_gimbal_id(0), 0)
        self.assertEqual(protocol_gimbal_id(-1), 0)
        self.assertTrue(source_need_encrypt(10, 98))
        self.assertTrue(source_need_encrypt(4, 20))
        self.assertFalse(source_need_encrypt(0, 32))
        self.assertFalse(source_need_encrypt(2, 16))
        # Would fail if someone hardcoded encrypt away for EYE
        self.assertNotEqual(source_need_encrypt(10, 98), False)

    def test_hash_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            apk = root / 'apk'
            apk.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'APK hash'):
                scan(apk, root)
            apk.write_bytes(b'apk')
            pin = hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for bank in PREFIX_BANKS:
                    (root / ('business-%02d-prefix-code-restored.dex' % bank)).write_bytes(
                        b'bad' if bank == bad else b'bank'
                    )
                with patch('ronin_queue_a_semantics_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch(
                    'ronin_queue_a_semantics_trace.PREFIX_BANKS', {b: pin for b in PREFIX_BANKS}
                ):
                    with self.assertRaisesRegex(ValueError, 'bank hash'):
                        scan(apk, root)

    def test_evidence_marks_a_subitems_exhausted_not_verified(self):
        e = self.evidence()
        for key in ['eyeDirectBleNecessity', 'liveIndexAddress', 'finalEncryptPath', 'dynamicCapability']:
            self.assertEqual(e['queueItemStatuses'][key], STATUS_EXHAUSTED)
            self.assertEqual(e[key]['status'], STATUS_EXHAUSTED)
        self.assertFalse(e['eyeDirectBleNecessity']['directBleMustEmitEyeAppStateVerified'])
        self.assertFalse(e['liveIndexAddress']['liveDeviceIndexVerified'])
        self.assertFalse(e['finalEncryptPath']['finalBlePlaintextVerified'])
        self.assertFalse(e['dynamicCapability']['liveDynamicCapabilityChangesVerified'])
        self.assertTrue(e['eyeDirectBleNecessity']['appRotateAlwaysCallsJustSendPauseDataOnSpeedAndAbsBranches'])
        self.assertEqual(e['eyeDirectBleNecessity']['hg724OverridesPauseOrRotate'], [])
        self.assertTrue(e['finalEncryptPath']['eyeAppState']['sourceIsNeedEncrypt'])
        self.assertEqual(e['liveIndexAddress']['ctorDefaultIndex'], 0)
        self.assertFalse(e['sendOpened'])
