import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ronin_motion_prefix_trace import (
    PREFIX_BANKS, source_speed_body, source_speed_units, scan, ROOT, CTRL,
)


class MotionPrefixTraceTests(unittest.TestCase):
    def test_speed_body_axis_order_and_flag_bits(self):
        self.assertEqual(source_speed_body(10, 20, 30, permission=True, multi_control=False).hex(), '0a0014001e0080')
        self.assertEqual(source_speed_body(0, 0, 0, permission=False, multi_control=True).hex(), '00000000000001')
        self.assertEqual(source_speed_units(1.9), 10)
        with self.assertRaises(ValueError):
            source_speed_body(True, 0, 0, permission=True, multi_control=False)

    def test_wrong_apk_and_each_bank_hash_rejected_before_parser(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'apk'
            p.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'APK hash'):
                scan(p, Path(t))
            d = Path(t)
            p.write_bytes(b'apk')
            pin = hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:
                    (d / ('business-%02d-prefix-code-restored.dex' % b)).write_bytes(b'bad' if b == bad else b'bank')
                with patch('ronin_motion_prefix_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch(
                    'ronin_motion_prefix_trace.PREFIX_BANKS', {b: pin for b in PREFIX_BANKS}
                ):
                    with self.assertRaisesRegex(ValueError, 'bank hash'):
                        scan(p, d)

    def evidence(self):
        return json.loads(
            (Path(__file__).resolve().parents[2] / 'protocol/research/ronin-motion-prefix-evidence.json').read_text()
        )

    def test_0c_current_app_layout_without_opening_send(self):
        r = self.evidence()['command0C']
        self.assertEqual(r['sourceDoPack']['axisOrder'], ['yaw', 'roll', 'pitch'])
        self.assertEqual(r['sourceDoPack']['bodyBytes'], 7)
        self.assertTrue(r['currentAppSourceLayoutEstablished'])
        self.assertFalse(r['sendOpened'])
        self.assertFalse(r['replacesExistingVelocity04_01'])
        self.assertFalse(r['eyeOrPauseDependencyResolvedForDirectBle'])
        self.assertEqual(r['roninUiController']['className'], CTRL)
        self.assertFalse(r['roninUiController']['send']['setsRoll'])
        self.assertFalse(r['roninUiController']['stop']['zerosAxesBeforeStart'])

    def test_14_still_only_base_rotate_and_4c_has_no_per_axis(self):
        e = self.evidence()
        r14 = e['command14']
        self.assertTrue(r14['onlyBaseRotateCaller'])
        self.assertEqual(r14['externalDirectCallers'][0]['className'], ROOT)
        self.assertFalse(r14['sendOpened'])
        r4c = e['command4C']
        self.assertFalse(r4c['perAxisResetEvidenceFound'])
        self.assertEqual(e['perAxisResetStringHits'], [])
        self.assertEqual(e['hg724OverridesOfRotateOrReset'], [])
        self.assertEqual(len(r4c['externalDirectCallers']), 8)
        self.assertEqual(len(r4c['nonCameraFocusExternalCallers']), 6)
        self.assertFalse(r4c['sendOpened'])
        for flag in ['appCodeExecuted', 'liveUiExecuted', 'targetDeviceVerified', 'wholeProtocolRecovered', 'researchToolProvidesSdkInterface', 'sdkSendAdded', 'sdkReceiveAdded']:
            self.assertFalse(e[flag])
        self.assertEqual(e['newBanks01And07']['externalDirectCallers'], [])
