import tempfile
import unittest
from pathlib import Path
from ronin_calibration_trace import trace, require_reference


class CalibrationTraceTests(unittest.TestCase):
    def test_missing_expected_command_reference_rejects(self):
        require_reference([('sget-object','v1, X;->NO Y;')], '->NO ')
        with self.assertRaises(ValueError):
            require_reference([('sget-object','v1, X;->YES Y;')], '->NO ')

    def test_unpinned_input_is_rejected_before_analysis_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input'
            path.write_bytes(b'not the pinned APK')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):
                trace(path,Path(directory)/'missing-dex')
