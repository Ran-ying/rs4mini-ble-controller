import asyncio,unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_protocol import factory_reset_spec
class FactoryResetTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_hg724_branch_body(self):
  self.assertEqual(factory_reset_spec('HG724')['payload'].hex(),'010001')
  for p in ['HG702',103,True,None]:
   with self.assertRaises(ValueError):factory_reset_spec(p)
