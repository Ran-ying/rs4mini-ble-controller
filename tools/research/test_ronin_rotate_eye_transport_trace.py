import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ronin_rotate_eye_transport_trace import PREFIX_BANKS, scan


class RotateEyeTransportTraceTests(unittest.TestCase):
    def evidence(self):
        return json.loads(
            (Path(__file__).resolve().parents[2] / 'protocol/research/ronin-rotate-eye-transport-evidence.json').read_text()
        )

    def test_wrong_apk_and_bank_hash_rejected(self):
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
                with patch('ronin_rotate_eye_transport_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch(
                    'ronin_rotate_eye_transport_trace.PREFIX_BANKS', {b: pin for b in PREFIX_BANKS}
                ):
                    with self.assertRaisesRegex(ValueError, 'bank hash'):
                        scan(apk, root)

    def test_chain_separates_static_from_hardware(self):
        e = self.evidence()
        self.assertEqual(e['analysisBank'], 5)
        self.assertFalse(e['sendOpened'])
        self.assertEqual(e['hg724OverridesRotate'], [])
        self.assertTrue(e['chain']['entry']['inheritedByHg724WithoutOverride'])
        eye = e['chain']['eyeTransport']
        self.assertEqual(eye['receiverTypeWire'], 17)
        self.assertEqual(eye['receiverIdLiteral'], 7)
        self.assertEqual(eye['cmdIdWire'], 98)
        self.assertEqual(eye['cmdIdName'], 'AppState')
        self.assertTrue(eye['notGimbalCommandSet'])
        self.assertEqual(eye['body']['sourceNoCallbackBodyWhenStartAndCameraNormal'], '0100')
        angle = e['chain']['angle14']
        self.assertEqual(angle['key'], '04:14')
        self.assertEqual(angle['cmdIdWire'], 20)
        self.assertTrue(angle['onSuccessDoesNotWaitForAckOrMotionComplete'])
        self.assertFalse(e['chain']['returnPath']['completionOrAbortNotificationInThisMethod'])
        self.assertFalse(e['chain']['receiverIndex']['liveDeviceIndexVerified'])
        self.assertGreaterEqual(len(e['staticallyEstablished']), 5)
        self.assertGreaterEqual(len(e['needsHardwareOrLiveSession']), 5)
        for flag in [
            'appCodeExecuted', 'liveUiExecuted', 'targetDeviceVerified', 'wholeProtocolRecovered',
            'researchToolProvidesSdkInterface', 'sdkSendAdded', 'sdkReceiveAdded', 'sendOpened',
        ]:
            self.assertFalse(e[flag])
        self.assertIn('EYE/SINGLE', ' '.join(e['needsHardwareOrLiveSession']))
