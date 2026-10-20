import asyncio
import unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_system_calibration import system_calibration_fields

class AppSystemCalibrationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.ControllerTests.asyncSetUp
    asyncTearDown=fixtures.ControllerTests.asyncTearDown

    async def test_source_states_beyond_write_range(self):
        self.assertEqual([system_calibration_fields(v)['state'] for v in range(4)],['DEFAULT','START','FAIL','SUCCESS'])
        self.assertEqual(system_calibration_fields(3),dict(rawValue=3,state='SUCCESS'))

    async def test_unknown_states_retained(self):
        for value in range(4,256):self.assertEqual(system_calibration_fields(value),dict(rawValue=value,state=None))
        for value in (-1,True,256):
            with self.assertRaises(ValueError):system_calibration_fields(value)
