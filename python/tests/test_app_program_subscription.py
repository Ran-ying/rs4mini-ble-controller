import asyncio,json,pathlib,unittest
import test_controller as fixtures
from test_app_commands import reply
from rs4mini_sdk.app_program_request import program_status_subscription_spec,program_status_subscription_reply
VECTORS=json.loads((pathlib.Path(__file__).resolve().parents[2]/'node/test/fixtures/program-subscription.json').read_text())
class ProgramSubscriptionTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 def incoming(self,r,body=b'\0',flags=128):reply(self.client,r,body,lambda data:data.__setitem__(8,flags))
 async def sent(self,count=1):
  await fixtures.until(lambda:len([f for f in self.client.frames() if f['commandId']==107])==count)
  return [f for f in self.client.frames() if f['commandId']==107][-1]
 async def test_six_shared_vectors(self):
  self.assertEqual(len(VECTORS),6)
  for v in VECTORS:
   spec=program_status_subscription_spec(v['program'],v['enabled']);self.assertEqual(spec['payload'].hex(),v['bodyHex']);self.assertEqual(spec['requestType'],v['requestType']);self.assertEqual(spec['requestedProgramCommandId'],v['programCommand'])
  for enabled in (None,0,1,'true',{}):
   with self.assertRaises(ValueError):program_status_subscription_spec('track',enabled)
 async def test_ack_body_is_opaque_and_remote_state_unknown(self):
  m=dict(sender=4,receiver=2,commandSet=4,commandId=107,flags=128,payload=bytes.fromhex('0001620401020304'),raw=b'x')
  for enabled in (True,False):
   result=program_status_subscription_reply(m,'track',enabled);self.assertEqual(result['bodyHex'],'01620401020304');self.assertEqual(result['requestedEnabled'],enabled);self.assertFalse(result['remoteSubscriptionStateVerified']);self.assertFalse(result['notificationStreamVerified']);self.assertFalse(result['freshStatusVerified'])
  for flags in (129,-128,384):
   with self.assertRaises(Exception) as raised:program_status_subscription_reply(dict(m,flags=flags),'track',True)
   self.assertEqual(raised.exception.code,'RS4MINI_PROTOCOL_ERROR')
