import tempfile,unittest
from pathlib import Path
from ronin_standalone_trace import trace

class StandaloneTraceTests(unittest.TestCase):
    def test_wrong_apk_rejected_before_model_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input';p.write_bytes(b'other app')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d)/'sdk',Path(d)/'ui')
