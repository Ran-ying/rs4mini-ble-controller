import asyncio,unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_handle import handle_write_spec
class HandleWriteTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_single_named_fields_and_independent_defaults(self):
  for setting,value,hex_value in [('dualChannelMode',0,'00ffffffffffffff'),('tiltDirection',1,'ff01ffffffffffff'),('panDirection',1,'ffff01ffffffffff')]:self.assertEqual(handle_write_spec(setting,value)['payload'].hex(),hex_value)
  self.assertEqual(handle_write_spec('dualChannelMode',1)['payload'].hex(),'01ffffffffffffff')
