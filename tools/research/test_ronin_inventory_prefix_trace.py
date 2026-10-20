import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ronin_inventory_prefix_trace import (
    PREFIX_BANKS, CMD_ENUM, extract_cmdid_gimbal_entries, discover_missing_from_commands, scan,
)


class InventoryPrefixTraceTests(unittest.TestCase):
    def test_extract_finds_synthetic_wire_absent_from_commands_map(self):
        """Prove discovery is computed from extraction, not a hard-coded empty list."""
        ops = [
            ('const-string', 'v1, Control'),
            ('const/4', 'v2, 0'),
            ('const/4', 'v3, 1'),
            ('new-instance', 'v0, ' + CMD_ENUM),
            ('invoke-direct', 'v0, v1, v2, v3, ' + CMD_ENUM + '-><init>(Ljava/lang/String; I I)V'),
            ('sput-object', 'v0, ' + CMD_ENUM + '->Control ' + CMD_ENUM),
            ('const-string', 'v1, ExtraProbe'),
            ('const/4', 'v2, 40'),
            ('const/16', 'v3, 200'),
            ('new-instance', 'v0, ' + CMD_ENUM),
            ('invoke-direct', 'v0, v1, v2, v3, ' + CMD_ENUM + '-><init>(Ljava/lang/String; I I)V'),
            ('sput-object', 'v0, ' + CMD_ENUM + '->ExtraProbe ' + CMD_ENUM),
            ('return-void', ''),
        ]
        rows = extract_cmdid_gimbal_entries(ops)
        by_name = {r['name']: r['commandId'] for r in rows}
        self.assertEqual(by_name['Control'], 1)
        self.assertEqual(by_name['ExtraProbe'], 200)
        missing = discover_missing_from_commands(rows, {1: '04:01'})
        self.assertEqual(missing, [dict(name='ExtraProbe', commandId=200, ordinal=40)])

    def test_hashes_checked_before_parser(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            p = d / 'apk'
            p.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'APK hash'):
                scan(p, d)
            p.write_bytes(b'apk')
            pin = hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:
                    (d / ('business-%02d-prefix-code-restored.dex' % b)).write_bytes(b'bad' if b == bad else b'bank')
                with patch('ronin_inventory_prefix_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch(
                    'ronin_inventory_prefix_trace.PREFIX_BANKS', {b: pin for b in PREFIX_BANKS}
                ):
                    with self.assertRaisesRegex(ValueError, 'bank hash'):
                        scan(p, d)

    def evidence(self):
        return json.loads(
            (Path(__file__).resolve().parents[2] / 'protocol/research/ronin-inventory-prefix-evidence.json').read_text()
        )

    def test_live_extraction_covers_commands_without_claiming_firmware_complete(self):
        r = self.evidence()
        self.assertEqual(r['schemaVersion'], 2)
        self.assertEqual(r['extraction']['source'].split()[0], 'PREFIX')
        self.assertEqual(r['extraction']['nonExcludedEntryCount'], 40)
        self.assertTrue(r['allNonExcludedLiveEnumsPresentInCommandsJson'])
        self.assertEqual(r['newlyDiscoveredGimbalWireCommands'], [])
        self.assertTrue(r['priorTableComparison']['priorTableIsNotDiscoverySource'])
        self.assertTrue(r['inventoryCompleteRemainsFalse'])
        self.assertFalse(r['inventoryCompleteClaimed'])
        self.assertFalse(r['activationOrBindingWriteOpened'])
        self.assertFalse(r['eightBankPacketScan']['literalCandidatesProveSend'])
        self.assertEqual(r['eightBankPacketScan']['orphanGimbalLiteralCandidatesOutsideExtractedEnum'], [])
        self.assertGreaterEqual(len(r['bank01ActivationMethods']), 1)
        for flag in ['appCodeExecuted', 'liveUiExecuted', 'targetDeviceVerified', 'sdkSendAdded', 'sdkReceiveAdded']:
            self.assertFalse(r[flag])
