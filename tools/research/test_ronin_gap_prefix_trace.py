import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ronin_gap_prefix_trace import PREFIX_BANKS, ONOFF_HYPOTHESIS, DT501, scan


class GapPrefixTraceTests(unittest.TestCase):
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
                with patch('ronin_gap_prefix_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch(
                    'ronin_gap_prefix_trace.PREFIX_BANKS', {b: pin for b in PREFIX_BANKS}
                ):
                    with self.assertRaisesRegex(ValueError, 'bank hash'):
                        scan(p, d)

    def evidence(self):
        return json.loads(
            (Path(__file__).resolve().parents[2] / 'protocol/research/ronin-gap-prefix-evidence.json').read_text()
        )

    def test_0d_remains_enum_only_without_hypothesized_class(self):
        r = self.evidence()['command0D']
        self.assertEqual(r['enumRegistration']['wireCommandId'], 13)
        self.assertTrue(r['enumRegistration']['threeArgConstructorWithoutClass'])
        self.assertFalse(r['enumRegistration']['constructorBindsRequestClass'])
        self.assertFalse(r['hypothesizedClassDefined'])
        self.assertEqual(r['enumOutsideReferences'], [])
        self.assertFalse(r['hg724BusinessEntryEstablished'])
        self.assertFalse(r['equatedToMotorSpecialCmdOrParam35'])
        self.assertFalse(r['sendOpened'])
        self.assertEqual(r['enumRegistration']['hypothesizedClassName'], ONOFF_HYPOTHESIS)

    def test_2c_still_has_no_external_callers_across_eight_banks(self):
        r = self.evidence()['command2C']
        self.assertEqual(r['externalDirectCallers'], [])
        self.assertEqual(r['classesDefinedInBanks'], [5])
        self.assertEqual(len(r['enumOutsideReferences']), 1)
        self.assertEqual(r['enumOutsideReferences'][0]['method'], 'start')
        self.assertFalse(r['hg724BusinessEntryEstablished'])
        self.assertFalse(r['sendOpened'])

    def test_0a_external_callers_remain_dt501_uvc_only(self):
        r = self.evidence()['command0A']
        self.assertTrue(r['onlyDt501UvcExternalCallersInScan'])
        self.assertEqual(r['externalCallerClasses'], [DT501])
        self.assertEqual(len(r['externalDirectCallers']), 2)
        self.assertTrue(all(c['target'].endswith('DataGimbalSetAngle;') for c in r['externalDirectCallers']))
        self.assertFalse(r['hg724BusinessEntryEstablished'])
        self.assertFalse(r['cameraUvcInCurrentScope'])
        self.assertFalse(r['sendOpened'])

    def test_new_banks_01_07_add_no_gap_command_evidence(self):
        r = self.evidence()
        self.assertEqual(len(r['bankSha256']), 8)
        self.assertEqual(r['scannedBanks'], list(range(8)))
        self.assertEqual(r['newBanks01And07']['externalDirectCallers'], [])
        self.assertEqual(r['newBanks01And07']['enumOutsideReferences'], [])
        for banks in r['newBanks01And07']['classDefinitions'].values():
            self.assertEqual(banks, [])
        for flag in [
            'appCodeExecuted', 'liveUiExecuted', 'targetDeviceVerified', 'wholeProtocolRecovered',
            'wholeAppRecovered', 'allScannedBodiesRecovered', 'indirectReflectionResolved',
            'researchToolProvidesSdkInterface', 'sdkSendAdded', 'sdkReceiveAdded',
        ]:
            self.assertFalse(r[flag])
