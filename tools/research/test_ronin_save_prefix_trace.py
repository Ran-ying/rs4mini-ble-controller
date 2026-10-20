import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ronin_save_prefix_trace import (
    OWNER, ENUM, PREFIX_BANKS, classify_reference, scan,
)


class SavePrefixTraceTests(unittest.TestCase):
    def test_direct_invoke_scope_differs_from_internal_and_non_calls(self):
        text = 'v0, ' + OWNER + '->start(Lcallback;)V'
        self.assertEqual(classify_reference('invoke-virtual', text, 'Lui;'), 'external-direct-invoke')
        self.assertEqual(classify_reference('invoke-virtual', text, OWNER), 'internal-invoke')
        self.assertEqual(classify_reference('new-instance', 'v0, ' + OWNER, 'Lui;'), 'allocation')
        self.assertEqual(classify_reference('const-class', 'v0, ' + OWNER, 'Lui;'), 'class-literal')
        self.assertEqual(
            classify_reference('sget-object', 'v0, ' + OWNER + '->instance ' + OWNER, OWNER),
            'field-reference',
        )
        self.assertEqual(
            classify_reference('sput-object', 'v0, ' + ENUM + '->SaveUserParams ' + ENUM, ENUM),
            'enum-registration',
        )
        self.assertEqual(
            classify_reference('sget-object', 'v0, ' + ENUM + '->SaveUserParams ' + ENUM, 'Lui;'),
            'command-enum-reference',
        )
        self.assertEqual(
            classify_reference('const-string/jumbo', 'v0, SaveUserParams', 'Lui;'),
            'string-literal-not-proven-reflection',
        )
        self.assertIsNone(classify_reference('invoke-virtual', 'v0, Lother;->start()V', 'Lui;'))

    def test_wrong_apk_rejected_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'apk'
            p.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'APK hash'):
                scan(p, Path(t))

    def test_all_eight_bank_hashes_checked_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            p = d / 'apk'
            p.write_bytes(b'apk')
            pin = hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:
                    (d / ('business-%02d-prefix-code-restored.dex' % b)).write_bytes(
                        b'bad' if b == bad else b'bank'
                    )
                with patch('ronin_save_prefix_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch(
                    'ronin_save_prefix_trace.PREFIX_BANKS', {b: pin for b in PREFIX_BANKS}
                ):
                    with self.assertRaisesRegex(ValueError, 'bank hash'):
                        scan(p, d)

    def evidence(self):
        return json.loads(
            (Path(__file__).resolve().parents[2] / 'protocol/research/ronin-save-prefix-callers-evidence.json').read_text()
        )

    def test_eight_bank_scan_keeps_empty_external_callers_and_empty_new_banks(self):
        r = self.evidence()
        self.assertEqual(len(r['bankSha256']), 8)
        self.assertEqual(r['scannedBanks'], list(range(8)))
        self.assertEqual(r['externalDirectCallers'], [])
        self.assertEqual(r['externalAllocations'], [])
        self.assertEqual(r['newBanks01And07ReferenceMethods'], [])
        self.assertEqual(len(r['methods']), 4)
        self.assertTrue(all(m['segment'] == 5 for m in r['methods']))
        self.assertFalse(any(m['mentionsHg724Abstraction'] for m in r['methods']))
        self.assertEqual(r['referenceKindCounts'].get('external-direct-invoke'), None)
        self.assertGreaterEqual(r['referenceKindCounts'].get('field-reference', 0), 1)
        self.assertGreaterEqual(r['referenceKindCounts'].get('enum-registration', 0), 1)

    def test_source_pack_and_enum_registration_are_not_persistence_proof(self):
        r = self.evidence()
        self.assertTrue(r['sourceDoPack']['emptyBody'])
        self.assertTrue(r['sourceStartPack']['allMentionsPresent'])
        self.assertEqual(r['sourceStartPack']['needAck'], 'YES')
        self.assertEqual(r['sourceStartPack']['businessEncrypt'], 'NO')
        self.assertFalse(r['sourceStartPack']['finalTransportEncryptionVerified'])
        self.assertEqual(r['enumRegistration']['wireCommandId'], 17)
        self.assertTrue(r['enumRegistration']['threeArgConstructorWithoutClass'])
        self.assertFalse(r['enumRegistration']['constructorBindsRequestClass'])
        for flag in [
            'appCodeExecuted', 'liveUiExecuted', 'targetDeviceVerified', 'wholeProtocolRecovered',
            'wholeAppRecovered', 'allScannedBodiesRecovered', 'indirectReflectionResolved',
            'targetModelCallPathEstablished', 'hg724BusinessEntryEstablished',
            'persistencePathEstablished', 'researchToolProvidesSdkInterface',
            'sdkSendAdded', 'sdkReceiveAdded', 'saveSettingsOpened',
            'parameterWriteEquatedToPersistence',
        ]:
            self.assertFalse(r[flag])

    def test_bank_totals_are_positive_and_pinned(self):
        r = self.evidence()
        self.assertEqual({int(k): v for k, v in r['bankSha256'].items()}, dict(PREFIX_BANKS))
        self.assertEqual(len(r['banks']), 8)
        for b in r['banks']:
            self.assertGreater(b['methodWithCodeCount'], 0)
            self.assertGreater(b['instructionCount'], 0)
            self.assertEqual(b['derivedSha256'], PREFIX_BANKS[b['segment']])
        by = {b['segment']: b['saveReferenceMethodCount'] for b in r['banks']}
        self.assertEqual(by[5], 4)
        self.assertEqual(by[1], 0)
        self.assertEqual(by[7], 0)
