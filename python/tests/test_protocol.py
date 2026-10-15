import unittest
import importlib.util
from pathlib import Path

protocol_path = Path(__file__).parents[1] / "rs4mini_sdk" / "protocol.py"
spec = importlib.util.spec_from_file_location("rs4mini_protocol", protocol_path)
protocol = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(protocol)

rc_units = protocol.rc_units
recenter_frame = protocol.recenter_frame
stop_frame = protocol.stop_frame
velocity_frame = protocol.velocity_frame


class ProtocolTests(unittest.TestCase):
    def test_stop_golden_vector(self):
        expected = "551604fc020400010004010004000400040000027705"
        self.assertEqual(stop_frame(0x0100).hex(), expected)

    def test_rc_units_and_clamping(self):
        self.assertEqual(rc_units(0), 1024)
        self.assertEqual(rc_units(1), 1684)
        self.assertEqual(rc_units(-1), 364)
        self.assertEqual(rc_units(99), 1684)

    def test_frames_are_distinct_commands(self):
        self.assertEqual(velocity_frame(1, 0, 0, 0)[9:11], b"\x04\x01")
        self.assertEqual(recenter_frame(1)[9:11], b"\x04\x4c")


if __name__ == "__main__":
    unittest.main()
