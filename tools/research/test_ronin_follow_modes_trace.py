import tempfile
import unittest
from pathlib import Path
from ronin_follow_modes_trace import trace

class FollowModeTraceTests(unittest.TestCase):
    def test_wrong_apk_rejected_before_bank_reads_or_optional_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input';p.write_bytes(b'other app')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d)/'sdk',Path(d)/'ui')
