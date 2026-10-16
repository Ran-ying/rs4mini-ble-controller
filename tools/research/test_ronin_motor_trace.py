import tempfile
import unittest
from pathlib import Path
from ronin_motor_trace import trace


class MotorTraceTests(unittest.TestCase):
    def test_unpinned_apk_rejects_before_optional_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input'
            path.write_bytes(b'other app')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):
                trace(path,Path(directory)/'missing')
