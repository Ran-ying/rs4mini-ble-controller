import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from ronin_inventory_prefix_trace import PREFIX_BANKS, scan

class InventoryPrefixTraceTests(unittest.TestCase):
    def test_hashes_checked_before_parser(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t); p=d/'apk'; p.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'APK hash'): scan(p,d)
            p.write_bytes(b'apk'); pin=hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS: (d/('business-%02d-prefix-code-restored.dex'%b)).write_bytes(b'bad' if b==bad else b'bank')
                with patch('ronin_inventory_prefix_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch('ronin_inventory_prefix_trace.PREFIX_BANKS',{b:pin for b in PREFIX_BANKS}):
                    with self.assertRaisesRegex(ValueError,'bank hash'): scan(p,d)

    def evidence(self):
        return json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-inventory-prefix-evidence.json').read_text())

    def test_inventory_stays_incomplete_without_activation_writes(self):
        r=self.evidence()
        self.assertTrue(r['allNonExcludedGimbalEnumsPresentInCommandsJson'])
        self.assertEqual(r['newlyDiscoveredGimbalWireCommands'], [])
        self.assertTrue(r['inventoryCompleteRemainsFalse'])
        self.assertFalse(r['inventoryCompleteClaimed'])
        self.assertFalse(r['activationOrBindingWriteOpened'])
        self.assertFalse(r['sessionVersionNegotiated'])
        self.assertFalse(r['deviceIdentityVerified'])
        self.assertTrue(r['centerReadOnlyGetAlreadySeparated'])
        self.assertGreaterEqual(len(r['bank01ActivationMethods']), 1)
        self.assertIn('04:0D', r['openUnknownRequestKeys'])
        for flag in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','sdkSendAdded','sdkReceiveAdded']:
            self.assertFalse(r[flag])
