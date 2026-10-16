import tempfile
import unittest
from pathlib import Path
from ronin_code_banks import restore_banks, inspect_control_modes

class CodeBanksTests(unittest.TestCase):
    def test_hash_failure_does_not_create_output_or_load_optional_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input';p.write_bytes(b'other app');out=Path(d)/'output'
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):restore_banks(p,out)
            self.assertFalse(out.exists())

    def test_unpinned_ui_view_rejected_before_optional_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'view';p.write_bytes(b'not a pinned restored UI bank')
            with self.assertRaisesRegex(ValueError,'UI bank hash mismatch'):inspect_control_modes(p)
