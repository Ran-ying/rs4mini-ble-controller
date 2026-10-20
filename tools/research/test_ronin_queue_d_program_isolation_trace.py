import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from ronin_queue_d_program_isolation_trace import (
    PREFIX_BANKS, STATUS, STATUS_EXHAUSTED, STATUS_UNRESOLVED, compute_status, scan,
)

class QueueDTests(unittest.TestCase):
    def evidence(self):
        return json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-queue-d-program-isolation-evidence.json').read_text())

    def test_hash_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); apk=root/'apk'; apk.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'APK hash'): scan(apk, root)
            apk.write_bytes(b'apk'); pin=hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:
                    (root/('business-%02d-prefix-code-restored.dex'%b)).write_bytes(b'bad' if b==bad else b'bank')
                with patch('ronin_queue_d_program_isolation_trace.APK_SHA256', hashlib.sha256(b'apk').hexdigest()), patch('ronin_queue_d_program_isolation_trace.PREFIX_BANKS',{b:pin for b in PREFIX_BANKS}):
                    with self.assertRaisesRegex(ValueError,'bank hash'): scan(apk, root)

    def test_status_computed_unresolved_when_bits_missing(self):
        commands = {
            '62': {'cameraOrRecordFieldsInDoPack': ['mRecordOrPreview']},
            '63': {'cameraOrRecordFieldsInDoPack': ['mExposure']},
        }
        self.assertEqual(
            compute_status({'25': {'bitsResolved': False}, '37': {'bitsResolved': True}}, commands, False, False),
            STATUS_UNRESOLVED,
        )
        self.assertEqual(
            compute_status({}, commands, False, False),
            STATUS_UNRESOLVED,
        )

    def test_status_exhausted_only_with_interleave_and_resolved_bits(self):
        commands = {
            '62': {'cameraOrRecordFieldsInDoPack': ['mRecordOrPreview']},
            '63': {'cameraOrRecordFieldsInDoPack': ['mExposure']},
        }
        maps = {
            '25': {
                'bitsResolved': True,
                'cameraPreviewOrExternalBits': [{'bitIndex': 3}, {'bitIndex': 7}],
            },
            '37': {
                'bitsResolved': True,
                'cameraPreviewOrExternalBits': [{'bitIndex': 3}],
            },
        }
        self.assertEqual(compute_status(maps, commands, False, False), STATUS_EXHAUSTED)

    def test_not_openable_and_info_bytes_resolved(self):
        e=self.evidence()
        self.assertEqual(e['status'], STATUS)
        self.assertEqual(e['status'], STATUS_EXHAUSTED)
        self.assertEqual(e.get('statusComputedBy'), 'compute_status(info_byte_maps, commands, reliable_stop, model_entry)')
        self.assertFalse(e['pureGimbalProgramPrimitiveOpenable'])
        self.assertFalse(e['programExecutionOpened'])
        self.assertTrue(e['panoramaHasExposureField'])
        self.assertTrue(e['trackHasRecordOrPreviewField'])
        self.assertIn('mExposure', e['commands']['63']['doPackFields'])
        self.assertIn('mRecordOrPreview', e['commands']['62']['doPackFields'])
        self.assertEqual(e['hg724NamedProgramMethods'], [])
        self.assertTrue(e['missingHg724NamedCallerDoesNotProveNoInheritedEntry'])
        self.assertNotIn('timelapsePackedInfoBytesUnresolvedForCameraIsolation', e)
        for key in ('25', '37'):
            info = e['infoByteMaps'][key]
            self.assertTrue(info['bitsResolved'], key)
            self.assertTrue(info['cameraPreviewOrExternalBits'], key)
        self.assertEqual(sorted(b['bitIndex'] for b in e['infoByteMaps']['25']['setters']), [0, 1, 2, 3, 7])
        self.assertEqual(sorted(b['bitIndex'] for b in e['infoByteMaps']['37']['setters']), [0, 1, 2, 3])
        self.assertTrue(e['timelapseInfoBytePreviewOrExternalBitsInterleaved'])
