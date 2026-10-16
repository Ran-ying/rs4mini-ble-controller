import tempfile
import unittest
from pathlib import Path
from ronin_system_calibration_trace import OWNER, command_slot, trace

class SystemCalibrationTraceTests(unittest.TestCase):
    def source(self):
        return [('const/16','v0, 24'),('new-array','v0, v0, [Ljava/lang/String;'),('const/16','v1, 22'),
                ('const-string/jumbo','v2, system_calc'),('aput-object','v2, v0, v1'),
                ('sput-object','v0, '+OWNER+'->RONIN_COMMAND [Ljava/lang/String;'),('return-void','')]

    def test_lookup_uses_actual_array_slot_not_nearby_literal(self):
        source=self.source();source.insert(4,('const-string/jumbo','v3, not_the_command'))
        self.assertEqual(command_slot(source,22),'system_calc')
        with self.assertRaisesRegex(ValueError,'unresolved'):command_slot(source,21)

    def test_duplicate_or_branching_array_is_rejected(self):
        source=self.source();source.insert(5,('aput-object','v2, v0, v1'))
        with self.assertRaisesRegex(ValueError,'duplicate'):command_slot(source,22)
        with self.assertRaisesRegex(ValueError,'unsupported'):command_slot([('goto','+2h')],22)

    def test_unpinned_input_rejected_before_optional_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input';p.write_bytes(b'other app')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d)/'missing')
