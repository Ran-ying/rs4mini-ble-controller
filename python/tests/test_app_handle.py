import unittest
from rs4mini_sdk.device import BleDevice
class RemovedQueriesTests(unittest.TestCase):
 def test_active_queries_and_aliases_are_absent(self):
  g=BleDevice(client_factory=lambda *a,**k:None)
  for name in ['getHandleSettings','get_handle_settings','queryCalibrationStatus','query_calibration_status','sendParameterSubscriptionRequest','send_parameter_subscription_request','sendProgramStatusSubscriptionRequest','send_program_status_subscription_request','sendHandleSettingRequest','send_handle_setting_request','sendHandheldStickControlRequest','send_handheld_stick_control_request','sendFactorySettingsResetRequest','send_factory_settings_reset_request','parameterSubscriptionKeys','parameter_subscription_keys']:
   self.assertFalse(hasattr(g.appCommands,name))
  self.assertIsNone(g.appCommands.calibrationStatus)
