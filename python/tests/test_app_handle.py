import unittest
from rs4mini_sdk.device import BleDevice
class RemovedQueriesTests(unittest.TestCase):
 def test_active_queries_and_aliases_are_absent(self):
  g=BleDevice(client_factory=lambda *a,**k:None)
  for name in ['getHandleSettings','get_handle_settings','queryCalibrationStatus','query_calibration_status']:
   self.assertFalse(hasattr(g.appCommands,name))
  self.assertIsNone(g.appCommands.calibrationStatus)
