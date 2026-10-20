import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from ronin_queue_b_reference_frame_trace import PREFIX_BANKS, STATUS, scan

class QueueBTests(unittest.TestCase):
    def evidence(self):
        return json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-queue-b-reference-frame-evidence.json').read_text())

    def test_hash_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); apk=root/'apk'; apk.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'APK hash'): scan(apk, root)
            apk.write_bytes(b'apk'); pin=hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:
                    (root/('business-%02d-prefix-code-restored.dex'%b)).write_bytes(b'bad' if b==bad else b'bank')
                with patch('ronin_queue_b_reference_frame_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch('ronin_queue_b_reference_frame_trace.PREFIX_BANKS',{b:pin for b in PREFIX_BANKS}):
                    with self.assertRaisesRegex(ValueError,'bank hash'): scan(apk, root)

    def test_exhausted_not_physical(self):
        e=self.evidence()
        self.assertEqual(e['status'], STATUS)
        self.assertTrue(e['sourceActualPoseDistinctFromMotorAngle'])
        self.assertEqual(e['peripheralDataTypeTags']['PActualPose']['wireTag'], 34)
        self.assertEqual(e['peripheralDataTypeTags']['YMotorAngle']['wireTag'], 18)
        self.assertFalse(e['physicalReferenceFrameVerified'])
        self.assertFalse(e['hostJointAnglesMaySubstituteFirmwareTrackAngles'])
        self.assertFalse(e['bytecodeEqualityBetweenActualPoseAnd0405AttitudeOrJointsProven'])
        self.assertEqual(e['methodsReferencingBothActualPoseAndPushParams04_05'], [])
        self.assertFalse(e['sendOpened'])
