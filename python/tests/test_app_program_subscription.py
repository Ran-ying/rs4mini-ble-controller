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
 async def test_profile_and_invalid_inputs_before_sends(self):
  with self.assertRaises(ValueError):await self.gimbal.appCommands.sendProgramStatusSubscriptionRequest(program='track',enabled=True)
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for spec in (dict(program='delay',enabled=True),dict(program=98,enabled=True),dict(program='track',enabled=1),dict(program='track',enabled=True,timeoutMs=0),dict(program='track',enabled=True,requestType=0)):
   with self.assertRaises((ValueError,TypeError)):await self.gimbal.appCommands.sendProgramStatusSubscriptionRequest(**spec)
  self.assertEqual(self.client.frames(),[])
 async def test_six_requests_ack_only_notification_does_not_resolve(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for count,v in enumerate(VECTORS,1):
   q=asyncio.create_task(self.gimbal.app_commands.send_program_status_subscription_request(program=v['program'],enabled=v['enabled']));r=await self.sent(count);self.assertEqual(r['payload'].hex(),v['bodyHex']);self.assertEqual(r['flags'],64);self.incoming(r,bytes.fromhex('00620401020304'),0);self.assertEqual(len(self.gimbal.experimental.pending),1);before=self.gimbal.appCommands.programStatus;self.incoming(r);result=await q;self.assertEqual(result['requestType'],v['requestType']);self.assertEqual(result['requestedEnabled'],v['enabled']);self.assertEqual(self.gimbal.appCommands.programStatus,before)
  self.assertEqual(len(self.client.frames()),6)
 async def test_concurrent_start_stop_correlate_separately(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');a=asyncio.create_task(self.gimbal.appCommands.sendProgramStatusSubscriptionRequest(program='track',enabled=True));b=asyncio.create_task(self.gimbal.appCommands.sendProgramStatusSubscriptionRequest(program='track',enabled=False));await self.sent(2);frames=self.client.frames();self.incoming(frames[1]);self.assertFalse((await b)['requestedEnabled']);self.incoming(frames[0]);self.assertTrue((await a)['requestedEnabled']);self.assertEqual(len(self.client.frames()),2)
 async def test_bad_ack_no_cache_fallback_or_inverse_write(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for count,(body,flags,code) in enumerate(((b'\7',128,'RS4MINI_DEVICE_ERROR'),(b'',128,'RS4MINI_PROTOCOL_ERROR'),(b'\0',129,'RS4MINI_PROTOCOL_ERROR')),1):
   q=asyncio.create_task(self.gimbal.appCommands.sendProgramStatusSubscriptionRequest(program='track',enabled=True));r=await self.sent(count);self.incoming(r,bytes.fromhex('00620401020304'),0);self.incoming(r,body,flags)
   with self.assertRaises(Exception) as raised:await q
   self.assertEqual(raised.exception.code,code);self.assertEqual(self.gimbal.experimental.pending,{})
  self.assertEqual(len(self.client.frames()),3)
 async def test_timeout_late_ack_disconnect_no_replay(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');q=asyncio.create_task(self.gimbal.appCommands.sendProgramStatusSubscriptionRequest(program='track',enabled=True,timeoutMs=25));r=await self.sent()
  with self.assertRaises(Exception) as raised:await q
  self.assertEqual(raised.exception.code,'RS4MINI_RESPONSE_TIMEOUT');self.incoming(r);self.assertEqual(self.gimbal.experimental.pending,{})
  q=asyncio.create_task(self.gimbal.appCommands.sendProgramStatusSubscriptionRequest(program='track',enabled=False));await self.sent(2);await self.gimbal.disconnect()
  with self.assertRaises(Exception) as raised:await q
  self.assertEqual(raised.exception.code,'RS4MINI_DISCONNECTED');self.assertEqual(len([f for f in self.client.frames() if f['commandId']==107]),2)
 async def test_task_cancel_never_sends_inverse_request(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');q=asyncio.create_task(self.gimbal.appCommands.sendProgramStatusSubscriptionRequest(program='track',enabled=True));await self.sent();q.cancel()
  with self.assertRaises(asyncio.CancelledError):await q
  self.assertEqual(self.gimbal.experimental.pending,{});self.assertEqual(len(self.client.frames()),1)
