import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ronin_inventory_prefix_trace import (
    PREFIX_BANKS, CMD_ENUM, extract_cmdid_gimbal_entries, discover_missing_from_commands, scan,
    synthetic_gimbal_orphan_operations,
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

    def test_full_scan_finds_synthetic_orphan_wire_200_in_every_bank_00_through_07(self):
        """End-to-end: inject orphan into each bank through scan(); banks 00-04 must not be skipped."""
        import os
        import sys
        root = Path(__file__).resolve().parents[2]
        apk = root / 'work/research/dji-ronin-2.2.2.apk'
        bank_dir = root / 'work/research/prefix-restored-final-b'
        if not apk.is_file() or not bank_dir.is_dir():
            self.skipTest('pinned APK/PREFIX banks unavailable')
        # Accept analysis-venv site-packages, flat analysis-libs, or RONIN_ANALYSIS_PYTHONPATH.
        sites = []
        env = os.environ.get('RONIN_ANALYSIS_PYTHONPATH', '').strip()
        if env:
            sites.extend(Path(p) for p in env.split(os.pathsep) if p)
        sites.extend(sorted(root.glob('work/research/analysis-venv/lib/python*/site-packages')))
        libs = root / 'work/research/analysis-libs'
        if libs.is_dir():
            sites.append(libs)
        for site in sites:
            if site.is_dir() and str(site) not in sys.path:
                sys.path.insert(0, str(site))
        try:
            import loguru  # noqa: F401
            import androguard  # noqa: F401
        except ImportError:
            self.skipTest(
                'androguard/loguru not importable; set RONIN_ANALYSIS_PYTHONPATH or install under '
                'work/research/analysis-venv or work/research/analysis-libs'
            )
        extras = {bank: [synthetic_gimbal_orphan_operations(200)] for bank in PREFIX_BANKS}
        result = scan(apk, bank_dir, synthetic_operations_by_bank=extras)
        orphans = result['eightBankPacketScan']['orphanGimbalLiteralCandidatesOutsideExtractedEnum']
        self.assertEqual(result['eightBankPacketScan']['banksScanned'], list(PREFIX_BANKS))
        by_bank = {}
        for row in orphans:
            if row.get('className') == 'Lsynthetic/InjectedPacketProbe;' and row.get('commandId') == 200:
                by_bank.setdefault(row['segment'], []).append(row)
        self.assertEqual(set(by_bank), set(PREFIX_BANKS), 'missing synthetic orphans in banks: %r' % (set(PREFIX_BANKS) - set(by_bank)))
        for bank in PREFIX_BANKS:
            self.assertGreaterEqual(len(by_bank[bank]), 1)


    def test_active_device_controller_ctor_first_getInstance_byte_offset_is_70(self):
        """Regression: instructionByteOffset must accumulate get_length(), not instruction index."""
        r = self.evidence()
        ctor = next(
            m for m in r['bank01ActivationMethods']
            if m['className'] == 'Lcom/dji/activate/active/ActiveDeviceController;'
            and m['method'] == '<init>'
            and m['instructionSha256'].startswith('aea9c5df')
        )
        self.assertEqual(ctor['instructionSha256'], 'aea9c5dfc47bacce13ed5f4ba3af740e0e9c5b52f7d3c28db8a91f2d57d3319f')
        first = ctor['activationRelatedInvokes'][0]
        self.assertIn('DataBatteryActiveStatus;->getInstance()', first['text'])
        self.assertEqual(first['instructionByteOffset'], 70)
        self.assertNotEqual(first['instructionByteOffset'], 17)

    def test_evidence_packet_scan_lists_all_eight_banks(self):
        r = self.evidence()
        self.assertEqual(r['eightBankPacketScan']['banksScanned'], list(range(8)))
